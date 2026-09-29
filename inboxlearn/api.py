"""FastAPI HTTP service exposing real InboxLearn inference, training, evaluation, and lifecycle operations."""
from __future__ import annotations

import time
import json
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from .config import CATEGORIES, PRIORITIES, Settings
from .service import InboxLearnService, ACTION_SUGGESTIONS
from .demo import load_demo_rows
from .classifier import deserialize_bundle, row_text
from .entities import extract_entities
from .calendar_export import create_event, event_to_ics_bytes
from .evaluation import dataset_hash


# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------

class PredictRequest(BaseModel):
    subject: str = Field(..., description="Email subject line")
    sender: str = Field(default="", description="Sender name or email address")
    body: str = Field(..., description="Email text body")
    category_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    priority_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class PredictResponse(BaseModel):
    category: str
    priority: str
    category_confidence: float
    priority_confidence: float
    all_category_scores: Dict[str, float]
    all_priority_scores: Dict[str, float]
    status: str
    needs_review: bool
    routing_reason: str
    suggested_action: str
    latency_ms: float
    model_version_id: int
    model_label: str
    feature_dimensions: int
    extracted_entities: List[Dict[str, Any]]
    has_calendar_event: bool


class FeedbackRequest(BaseModel):
    email_id: int
    category: str
    priority: str


class PrepareCandidateResponse(BaseModel):
    version_id: Optional[int] = None
    parent_id: Optional[int] = None
    mode: Optional[str] = None
    feedback_count: Optional[int] = None
    reused: bool = False
    message: str


class DiffRequest(BaseModel):
    before_id: int
    after_id: int


class EvaluateRequest(BaseModel):
    version_id: Optional[int] = None
    dataset_name: str = "demo_eval.csv"


class ActivateRequest(BaseModel):
    version_id: int


class RollbackRequest(BaseModel):
    version_id: int


# -----------------------------------------------------------------------------
# Factory
# -----------------------------------------------------------------------------

def _clean_version_dict(v) -> dict:
    d = dict(v)
    d.pop("model_blob", None)
    return d


def create_app(service: Optional[InboxLearnService] = None) -> FastAPI:
    app = FastAPI(
        title="InboxLearn API",
        description="High-performance REST API for local, human-in-the-loop email triage inference & model lifecycle.",
        version="2.4.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Lazily or explicitly bind service
    svc_instance = service or InboxLearnService()

    def get_service() -> InboxLearnService:
        return svc_instance

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "inboxlearn", "version": "2.4.0"}

    @app.get("/api/status")
    def get_status(svc: InboxLearnService = Depends(get_service)):
        active = svc.active_version()
        if not active:
            svc.ensure_baseline()
            active = svc.active_version()

        all_versions = svc.repo.versions()
        inbox_rows = svc.repo.inbox_rows(review_only=False, include_confident=True)
        total_emails = len(inbox_rows)
        pending_reviews = sum(1 for r in inbox_rows if r["status"] == "needs_review" and r["feedback_id"] is None)
        feedback_status = svc.feedback_status(int(active["id"]))

        # Check candidate registry
        candidate_row = svc.repo._one("SELECT version_id, parent_id, recipe_version FROM candidate_registry LIMIT 1")
        candidate_info = None
        if candidate_row:
            cand_version = svc.repo.version(candidate_row["version_id"])
            if cand_version:
                cand_meta = json.loads(cand_version["metadata_json"])
                eval_row = svc.current_evaluation(int(candidate_row["version_id"]))
                candidate_info = {
                    "version_id": int(candidate_row["version_id"]),
                    "label": cand_version["label"],
                    "parent_id": candidate_row["parent_id"],
                    "mode": cand_meta.get("training_mode"),
                    "feedback_count": cand_meta.get("trained_feedback_count", 0),
                    "is_evaluated": eval_row is not None,
                }

        meta = json.loads(active["metadata_json"])

        return {
            "active_version": {
                "id": int(active["id"]),
                "label": active["label"],
                "kind": active["kind"],
                "parent_id": active["parent_id"],
                "created_at": active["created_at"],
                "training_mode": meta.get("training_mode", "seed"),
                "seed_count": meta.get("seed_count", 0),
                "feedback_count": meta.get("trained_feedback_count", 0),
            },
            "metrics": {
                "emails_stored": total_emails,
                "pending_reviews": pending_reviews,
                "available_feedback": feedback_status["total"],
                "uncommitted_feedback": feedback_status["omitted"],
                "total_models": len(all_versions),
            },
            "candidate": candidate_info,
            "thresholds": {
                "category": svc.settings.category_threshold,
                "priority": svc.settings.priority_threshold,
            },
            "datasets": {
                "seed": len(load_demo_rows("demo_seed.csv")),
                "validation": len(load_demo_rows("demo_validation.csv")),
                "eval": len(load_demo_rows("demo_eval.csv")),
                "eval_expanded": len(load_demo_rows("demo_eval_expanded.csv")),
            },
            "categories": list(CATEGORIES),
            "priorities": list(PRIORITIES),
        }

    @app.post("/api/predict", response_model=PredictResponse)
    def predict(req: PredictRequest, svc: InboxLearnService = Depends(get_service)):
        active = svc.active_version()
        if not active:
            svc.ensure_baseline()
            active = svc.active_version()

        bundle = deserialize_bundle(active["model_blob"])
        cat_thresh = req.category_threshold if req.category_threshold is not None else svc.settings.category_threshold
        prio_thresh = req.priority_threshold if req.priority_threshold is not None else svc.settings.priority_threshold

        row_data = {"subject": req.subject, "sender": req.sender, "body": req.body}
        
        t0 = time.perf_counter()
        features = bundle.vectorizer.transform([row_text(row_data)])
        cat_probs = bundle.category_model.predict_proba(features)[0]
        prio_probs = bundle.priority_model.predict_proba(features)[0]
        latency_ms = (time.perf_counter() - t0) * 1000.0

        cat_idx = int(np.argmax(cat_probs))
        prio_idx = int(np.argmax(prio_probs))
        category = str(bundle.category_model.classes_[cat_idx])
        priority = str(bundle.priority_model.classes_[prio_idx])
        cat_conf = float(cat_probs[cat_idx])
        prio_conf = float(prio_probs[prio_idx])

        all_cat_scores = {str(c): round(float(p), 4) for c, p in zip(bundle.category_model.classes_, cat_probs)}
        all_prio_scores = {str(p): round(float(pr), 4) for p, pr in zip(bundle.priority_model.classes_, prio_probs)}

        needs_review = (cat_conf < cat_thresh) or (prio_conf < prio_thresh)
        status = "needs_review" if needs_review else "classified"

        # Build routing reason
        row_with_scores = {
            "status": status,
            "category_confidence": cat_conf,
            "priority_confidence": prio_conf,
        }
        routing_reason = svc.routing_reason(row_with_scores)
        suggested_action = ACTION_SUGGESTIONS.get(category, "Review this message manually.")

        # Extract entities
        extracted = extract_entities(f"{req.subject} {req.body}")
        entity_dicts = [
            {
                "type": e.entity_type,
                "value": e.value,
                "raw_phrase": e.raw_phrase,
                "confidence": e.confidence,
            }
            for e in extracted
        ]
        has_calendar = any(e.entity_type in ("date", "deadline") for e in extracted)

        return PredictResponse(
            category=category,
            priority=priority,
            category_confidence=round(cat_conf, 4),
            priority_confidence=round(prio_conf, 4),
            all_category_scores=all_cat_scores,
            all_priority_scores=all_prio_scores,
            status=status,
            needs_review=needs_review,
            routing_reason=routing_reason,
            suggested_action=suggested_action,
            latency_ms=round(latency_ms, 2),
            model_version_id=int(active["id"]),
            model_label=active["label"],
            feature_dimensions=bundle.vectorizer.n_features,
            extracted_entities=entity_dicts,
            has_calendar_event=has_calendar,
        )

    @app.get("/api/inbox")
    def get_inbox(
        include_confident: bool = Query(True),
        order: str = Query("Lowest confidence first"),
        category: str = Query("All categories"),
        priority: str = Query("All priorities"),
        import_batch: str = Query("All batches"),
        unresolved: bool = Query(False),
        svc: InboxLearnService = Depends(get_service),
    ):
        rows = svc.review_rows(
            include_confident=include_confident,
            order=order,
            category=category,
            priority=priority,
            import_batch=import_batch,
            unresolved=unresolved,
        )
        # Attach entities
        for r in rows:
            r["entities"] = svc.entities_for_email(int(r["id"]))
            r["suggested_action"] = ACTION_SUGGESTIONS.get(r["effective_category"], "")
        return {"total": len(rows), "rows": rows}

    @app.post("/api/inbox/demo-import")
    def import_demo_emails(dataset: str = Query("demo_feedback.csv"), svc: InboxLearnService = Depends(get_service)):
        payload_path = Path("data") / dataset
        if not payload_path.exists():
            raise HTTPException(status_code=404, detail=f"Dataset {dataset} not found")
        data_bytes = payload_path.read_bytes()
        res = svc.classify_upload(data_bytes, source=f"demo:{dataset}")
        return {"status": "success", "imported": res["new"], "duplicates": res["duplicates"]}

    @app.post("/api/inbox/upload")
    async def upload_file(
        file: UploadFile = File(...),
        svc: InboxLearnService = Depends(get_service),
    ):
        content = await file.read()
        try:
            res = svc.classify_email_file(content, filename=file.filename or "", source="upload")
            return {"status": "success", "result": res}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/feedback")
    def record_feedback(req: FeedbackRequest, svc: InboxLearnService = Depends(get_service)):
        try:
            feedback_id, is_revision = svc.save_feedback(req.email_id, req.category, req.priority)
            return {
                "status": "success",
                "feedback_id": feedback_id,
                "is_revision": is_revision,
                "email_id": req.email_id,
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/models")
    def list_models(svc: InboxLearnService = Depends(get_service)):
        versions = [_clean_version_dict(v) for v in svc.repo.versions()]
        for v in versions:
            v["metadata"] = json.loads(v["metadata_json"])
            eval_row = svc.current_evaluation(v["id"])
            v["has_evaluation"] = eval_row is not None
            if eval_row:
                try:
                    eval_data = json.loads(eval_row["results_json"])
                    updated_metrics = eval_data.get("updated", {})
                    v["evaluation_summary"] = {
                        "category_accuracy": updated_metrics.get("category_accuracy"),
                        "priority_accuracy": updated_metrics.get("priority_accuracy"),
                    }
                except Exception:
                    v["evaluation_summary"] = None
        return {"versions": versions}

    @app.post("/api/models/prepare")
    def prepare_candidate(svc: InboxLearnService = Depends(get_service)):
        try:
            result = svc.train()
            if result is None:
                return {
                    "status": "noop",
                    "reused": False,
                    "message": "No new human feedback corrections found to train.",
                }
            return {
                "status": "success",
                "version_id": result["version_id"],
                "parent_id": result["parent_id"],
                "mode": result["mode"],
                "feedback_count": result["feedback_count"],
                "reused": result["reused"],
                "message": f"Candidate model prepared ({result['mode']}).",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/models/diff")
    def diff_candidate(req: DiffRequest, svc: InboxLearnService = Depends(get_service)):
        try:
            diff = svc.prediction_preview(req.before_id, req.after_id)
            return diff
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/models/evaluate")
    def evaluate_model(req: EvaluateRequest, svc: InboxLearnService = Depends(get_service)):
        try:
            result = svc.compare_versions(req.version_id, dataset_name=req.dataset_name)
            return result
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/models/activate")
    def activate_model(req: ActivateRequest, svc: InboxLearnService = Depends(get_service)):
        try:
            svc.activate(req.version_id)
            active = svc.active_version()
            return {"status": "success", "active_version": _clean_version_dict(active)}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/models/rollback")
    def rollback_model(req: RollbackRequest, svc: InboxLearnService = Depends(get_service)):
        try:
            svc.rollback(req.version_id)
            active = svc.active_version()
            return {"status": "success", "rolled_back_to": _clean_version_dict(active)}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/actions/follow-ups")
    def get_follow_ups(svc: InboxLearnService = Depends(get_service)):
        return {"follow_ups": svc.follow_ups()}

    @app.get("/api/export/csv")
    def export_csv(svc: InboxLearnService = Depends(get_service)):
        csv_bytes = svc.export_csv()
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="inboxlearn_export.csv"'},
        )

    @app.get("/api/tuning")
    def get_tuning(target_precision: float = Query(0.80), svc: InboxLearnService = Depends(get_service)):
        try:
            return svc.validation_tuning(target_precision=target_precision)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # Mount frontend production build if present
    dist_dir = Path(__file__).parent.parent / "frontend" / "dist"
    if dist_dir.exists():
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import FileResponse

        index_file = dist_dir / "index.html"

        class SPAStaticFiles(StaticFiles):
            async def get_response(self, path: str, scope):
                try:
                    response = await super().get_response(path, scope)
                    if response.status_code == 404 and index_file.exists():
                        return FileResponse(index_file)
                    return response
                except Exception:
                    if index_file.exists():
                        return FileResponse(index_file)
                    raise

        app.mount("/", SPAStaticFiles(directory=str(dist_dir), html=True), name="frontend")

    return app


# Default ASGI application instance
app = create_app()
