"""Evaluate baseline and candidate models on the expanded synthetic evaluation set.

Runs independently from scripts/experiment.py to preserve the historical 10-example report.
Generates reports/expanded_evaluation.json and reports/expanded_evaluation.md.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from sklearn.metrics import classification_report, confusion_matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inboxlearn.classifier import train_bundle, row_text
from inboxlearn.config import CATEGORIES, PRIORITIES
from inboxlearn.demo import load_demo_rows
from inboxlearn.evaluation import assert_split_isolated, evaluate_bundle


def per_class_metrics(actual, predicted, labels):
    rep = classification_report(actual, predicted, labels=labels, output_dict=True, zero_division=0)
    return {
        label: {
            "precision": float(rep[label]["precision"]),
            "recall": float(rep[label]["recall"]),
            "f1": float(rep[label]["f1-score"]),
            "support": int(rep[label]["support"]),
        }
        for label in labels
    }


def run_expanded_evaluation():
    seed = load_demo_rows("demo_seed.csv")
    feedback = load_demo_rows("demo_feedback.csv")
    eval_hist = load_demo_rows("demo_eval.csv")
    validation = load_demo_rows("demo_validation.csv")
    expanded = load_demo_rows("demo_eval_expanded.csv")

    # Strict split isolation
    for split_name, split_rows in [("seed", seed), ("feedback", feedback),
                                   ("validation", validation), ("eval_historical", eval_hist)]:
        assert_split_isolated(expanded, split_rows)

    v1 = train_bundle(seed, random_state=42)
    v2 = train_bundle(feedback, base=v1, incremental=True)

    features = v1.vectorizer.transform([row_text(r) for r in expanded])
    actual_cat = [r["category"] for r in expanded]
    actual_prio = [r["priority"] for r in expanded]

    v1_cat_pred = v1.category_model.predict(features)
    v1_prio_pred = v1.priority_model.predict(features)
    v2_cat_pred = v2.category_model.predict(features)
    v2_prio_pred = v2.priority_model.predict(features)

    res_v1 = evaluate_bundle(v1, expanded)
    res_v2 = evaluate_bundle(v2, expanded)

    v1_cat_class = per_class_metrics(actual_cat, v1_cat_pred, CATEGORIES)
    v2_cat_class = per_class_metrics(actual_cat, v2_cat_pred, CATEGORIES)
    v1_prio_class = per_class_metrics(actual_prio, v1_prio_pred, PRIORITIES)
    v2_prio_class = per_class_metrics(actual_prio, v2_prio_pred, PRIORITIES)

    report_data = {
        "dataset": "data/demo_eval_expanded.csv",
        "rows": len(expanded),
        "disclaimer": "Synthetic evaluation data only; not a real-world accuracy claim. Confidence estimates are uncalibrated.",
        "category_distribution": dict(Counter(actual_cat)),
        "priority_distribution": dict(Counter(actual_prio)),
        "overall": {
            "baseline_v1": {
                "category_accuracy": res_v1["category_accuracy"],
                "category_macro_f1": res_v1["category_macro_f1"],
                "priority_accuracy": res_v1["priority_accuracy"],
                "priority_macro_f1": res_v1["priority_macro_f1"],
            },
            "candidate_v2": {
                "category_accuracy": res_v2["category_accuracy"],
                "category_macro_f1": res_v2["category_macro_f1"],
                "priority_accuracy": res_v2["priority_accuracy"],
                "priority_macro_f1": res_v2["priority_macro_f1"],
            },
            "absolute_changes": {
                "category_accuracy": res_v2["category_accuracy"] - res_v1["category_accuracy"],
                "category_macro_f1": res_v2["category_macro_f1"] - res_v1["category_macro_f1"],
                "priority_accuracy": res_v2["priority_accuracy"] - res_v1["priority_accuracy"],
                "priority_macro_f1": res_v2["priority_macro_f1"] - res_v1["priority_macro_f1"],
            },
        },
        "per_class": {
            "category": {
                label: {
                    "support": v1_cat_class[label]["support"],
                    "v1_f1": v1_cat_class[label]["f1"],
                    "v2_f1": v2_cat_class[label]["f1"],
                    "delta_f1": v2_cat_class[label]["f1"] - v1_cat_class[label]["f1"],
                }
                for label in CATEGORIES
            },
            "priority": {
                label: {
                    "support": v1_prio_class[label]["support"],
                    "v1_f1": v1_prio_class[label]["f1"],
                    "v2_f1": v2_prio_class[label]["f1"],
                    "delta_f1": v2_prio_class[label]["f1"] - v1_prio_class[label]["f1"],
                }
                for label in PRIORITIES
            },
        },
    }

    # Write JSON report
    out_dir = ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "expanded_evaluation.json").write_text(json.dumps(report_data, indent=2), encoding="utf-8")

    # Generate Markdown report
    md_lines = [
        "# Expanded Synthetic Evaluation Report",
        "",
        "> **Notice:** This evaluation uses synthetic demonstration fixtures only; it is not a claim of real-world accuracy on arbitrary email distributions. Confidence estimates are uncalibrated.",
        "",
        f"**Dataset:** `data/demo_eval_expanded.csv` ({len(expanded)} synthetic rows across diverse categories, priorities, and boundary scenarios).",
        "**Split Isolation:** 0 normalized subject/body overlap against seed, feedback, validation, and historical evaluation splits.",
        "",
        "## Overall Metrics",
        "",
        "| Metric | Baseline v1 | Candidate v2 | Absolute Change | Outcome |",
        "|---|---:|---:|---:|---|",
        f"| Category accuracy | {res_v1['category_accuracy']:.1%} ({int(res_v1['category_accuracy']*len(expanded))}/{len(expanded)}) | {res_v2['category_accuracy']:.1%} ({int(res_v2['category_accuracy']*len(expanded))}/{len(expanded)}) | {report_data['overall']['absolute_changes']['category_accuracy']:+.1%} | {'Increase' if report_data['overall']['absolute_changes']['category_accuracy'] > 0 else 'Decrease'} |",
        f"| Category macro-F1 | {res_v1['category_macro_f1']:.4f} | {res_v2['category_macro_f1']:.4f} | {report_data['overall']['absolute_changes']['category_macro_f1']:+.4f} | {'Increase' if report_data['overall']['absolute_changes']['category_macro_f1'] > 0 else 'Decrease'} |",
        f"| Priority accuracy | {res_v1['priority_accuracy']:.1%} ({int(res_v1['priority_accuracy']*len(expanded))}/{len(expanded)}) | {res_v2['priority_accuracy']:.1%} ({int(res_v2['priority_accuracy']*len(expanded))}/{len(expanded)}) | {report_data['overall']['absolute_changes']['priority_accuracy']:+.1%} | {'Increase' if report_data['overall']['absolute_changes']['priority_accuracy'] > 0 else 'Decrease'} |",
        f"| Priority macro-F1 | {res_v1['priority_macro_f1']:.4f} | {res_v2['priority_macro_f1']:.4f} | {report_data['overall']['absolute_changes']['priority_macro_f1']:+.4f} | {'Increase' if report_data['overall']['absolute_changes']['priority_macro_f1'] > 0 else 'Decrease'} |",
        "",
        "## Per-Class Breakdown",
        "",
        "### Categories",
        "",
        "| Category | Support | Baseline v1 F1 | Candidate v2 F1 | Delta F1 |",
        "|---|---:|---:|---:|---:|",
    ]
    for c in CATEGORIES:
        info = report_data["per_class"]["category"][c]
        md_lines.append(f"| {c} | {info['support']} | {info['v1_f1']:.4f} | {info['v2_f1']:.4f} | {info['delta_f1']:+.4f} |")

    md_lines.extend([
        "",
        "### Priorities",
        "",
        "| Priority | Support | Baseline v1 F1 | Candidate v2 F1 | Delta F1 |",
        "|---|---:|---:|---:|---:|",
    ])
    for p in PRIORITIES:
        info = report_data["per_class"]["priority"][p]
        md_lines.append(f"| {p} | {info['support']} | {info['v1_f1']:.4f} | {info['v2_f1']:.4f} | {info['delta_f1']:+.4f} |")

    (out_dir / "expanded_evaluation.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Expanded evaluation completed. Reports written to reports/expanded_evaluation.{{json,md}}")


if __name__ == "__main__":
    run_expanded_evaluation()
