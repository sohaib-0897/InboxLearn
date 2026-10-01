import React, { useState } from 'react';
import { 
  GitCompare, 
  Cpu, 
  ShieldCheck, 
  CheckCircle2, 
  AlertTriangle, 
  ArrowRight, 
  FileCheck, 
  Check, 
  Lock, 
  Unlock,
  TrendingUp,
  TrendingDown,
  Layers,
  HelpCircle,
  RefreshCw
} from 'lucide-react';
import { api, DiffResponse, EvaluationResponse } from '../api/client';

interface CandidateDiffGateProps {
  activeVersionId: number;
  activeLabel: string;
  candidateInfo: {
    version_id: number;
    label: string;
    parent_id: number;
    mode: string;
    feedback_count: number;
    is_evaluated: boolean;
  } | null;
  onRefresh: () => void;
}

export const CandidateDiffGate: React.FC<CandidateDiffGateProps> = ({
  activeVersionId,
  activeLabel,
  candidateInfo,
  onRefresh,
}) => {
  const [isPreparing, setIsPreparing] = useState(false);
  const [prepareMessage, setPrepareMessage] = useState<string | null>(null);

  const [isDiffing, setIsDiffing] = useState(false);
  const [diffData, setDiffData] = useState<DiffResponse | null>(null);
  const [diffError, setDiffError] = useState<string | null>(null);
  const [showChangedOnly, setShowChangedOnly] = useState(false);

  const [isEvaluating, setIsEvaluating] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState<'demo_eval.csv' | 'demo_eval_expanded.csv'>('demo_eval.csv');
  const [evalData, setEvalData] = useState<EvaluationResponse | null>(null);

  const [isActivating, setIsActivating] = useState(false);
  const [activateError, setActivateError] = useState<string | null>(null);
  const [activateSuccess, setActivateSuccess] = useState<string | null>(null);

  const handlePrepareCandidate = async () => {
    setIsPreparing(true);
    setPrepareMessage(null);
    setActivateError(null);
    try {
      const res = await api.prepareCandidate();
      setPrepareMessage(res.message);
      onRefresh();
    } catch (err: any) {
      setPrepareMessage(`Preparation error: ${err.message}`);
    } finally {
      setIsPreparing(false);
    }
  };

  const handleRunDiff = async () => {
    if (!candidateInfo) return;
    setIsDiffing(true);
    setDiffError(null);
    try {
      const res = await api.diffModels(activeVersionId, candidateInfo.version_id);
      setDiffData(res);
    } catch (err: any) {
      console.error('Diff error', err);
      setDiffError(err.message || 'Inbox predictions could not be compared.');
    } finally {
      setIsDiffing(false);
    }
  };

  const handleRunEvaluation = async () => {
    setIsEvaluating(true);
    setActivateError(null);
    try {
      const versionId = candidateInfo ? candidateInfo.version_id : activeVersionId;
      const res = await api.evaluateModel(versionId, selectedDataset);
      setEvalData(res);
      onRefresh();
    } catch (err: any) {
      console.error('Evaluation error', err);
      setActivateError(`Evaluation failed: ${err.message}`);
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleActivateCandidate = async () => {
    if (!candidateInfo) return;
    setIsActivating(true);
    setActivateError(null);
    setActivateSuccess(null);
    try {
      const res = await api.activateModel(candidateInfo.version_id);
      setActivateSuccess(`Model ${res.active_version.label} activated to production! Candidate registry cleared.`);
      onRefresh();
    } catch (err: any) {
      setActivateError(err.message || 'Activation failed');
    } finally {
      setIsActivating(false);
    }
  };

  const displayedDiffRows = diffData?.rows.filter((r) => (!showChangedOnly ? true : r.changed)) || [];

  return (
    <div className="workspace-candidate space-y-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      
      {/* Editorial Section Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-4 border-b border-paper-border">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-[10px] tracking-wider uppercase text-rust font-semibold">
              02 / MODEL IMPROVEMENT
            </span>
            <span className="text-paper-border">·</span>
            <span className="font-mono text-[10px] text-ink-muted">
              COMPARE · EVALUATE · DECIDE
            </span>
          </div>
          <h2 className="font-serif text-2xl sm:text-3xl font-bold text-ink">
            Candidate & evaluation
          </h2>
          <p className="text-xs text-ink-muted mt-1 max-w-2xl leading-relaxed">
            Prepare from human feedback, compare changed predictions, then evaluate on held-out examples before choosing whether to activate.
          </p>
        </div>

        <div className="flex items-center gap-2 font-mono text-xs text-ink-muted bg-paper-sheet border border-paper-border px-3 py-2 shadow-paper-sm">
          <ShieldCheck className="w-4 h-4 text-emerald-800" />
          <span>Evaluation before activation</span>
        </div>
      </div>

      {/* Global Alerts */}
      {prepareMessage && (
        <div className="p-3.5 bg-paper-sheet border-l-4 border-rust border-y border-r border-paper-border text-xs text-ink flex items-center justify-between shadow-paper-sm">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-rust flex-shrink-0" />
            <span>{prepareMessage}</span>
          </div>
          <button onClick={() => setPrepareMessage(null)} className="text-xs text-ink-muted hover:text-ink underline cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {activateSuccess && (
        <div className="p-3.5 bg-emerald-50 border-l-4 border-emerald-700 border-y border-r border-emerald-200 text-xs text-emerald-950 flex items-center justify-between shadow-paper-sm">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-700 flex-shrink-0" />
            <strong className="font-semibold">{activateSuccess}</strong>
          </div>
          <button onClick={() => setActivateSuccess(null)} className="text-xs text-emerald-800 hover:text-emerald-950 underline cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {activateError && (
        <div className="p-3.5 bg-rose-50 border-l-4 border-rose-700 border-y border-r border-rose-200 text-xs text-rose-950 flex items-center justify-between shadow-paper-sm">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-700 flex-shrink-0" />
            <span>{activateError}</span>
          </div>
          <button onClick={() => setActivateError(null)} className="text-xs text-rose-800 hover:text-rose-950 underline cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {diffError && (
        <div className="workspace-inline-error" role="alert">
          <span><strong>Prediction comparison failed.</strong> {diffError}</span>
          <button type="button" onClick={() => setDiffError(null)}>Dismiss</button>
        </div>
      )}

      {/* ========================================================================= */}
      {/* STEP 1: CANDIDATE MODEL PREPARATION & REGISTRY STATUS                     */}
      {/* ========================================================================= */}
      <div className="bg-paper-sheet border border-paper-border shadow-paper p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-paper-border">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-rust font-bold">01 / PREPARE</span>
              <h3 className="font-serif text-lg font-bold text-ink">
                Prepare Candidate Snapshot
              </h3>
            </div>
            <p className="text-xs text-ink-muted mt-0.5">
              Prepare a candidate from saved feedback. Your active model stays in place until you choose to activate.
            </p>
          </div>

          <button
            onClick={handlePrepareCandidate}
            disabled={isPreparing}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-rust text-white text-xs font-sans font-semibold hover:bg-rust-hover transition-colors cursor-pointer shadow-paper-sm disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isPreparing ? 'animate-spin' : ''}`} />
            <span>{isPreparing ? 'Training Snapshot...' : 'Prepare Candidate Snapshot'}</span>
          </button>
        </div>

        {/* Snapshot Status Ledger Strip */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs font-mono">
          <div className="p-3 bg-paper-canvas border border-paper-border">
            <span className="text-[10px] text-ink-faint block uppercase">Active Parent</span>
            <strong className="text-sm font-bold text-ink mt-0.5 block">{activeLabel}</strong>
            <span className="text-[10px] text-ink-muted">Current model</span>
          </div>

          <div className="p-3 bg-paper-canvas border border-paper-border">
            <span className="text-[10px] text-ink-faint block uppercase">Candidate Snapshot</span>
            <strong className="text-sm font-bold text-ink mt-0.5 block">
              {candidateInfo ? candidateInfo.label : 'None Prepared'}
            </strong>
            <span className="text-[10px] text-ink-muted">
              {candidateInfo ? `${candidateInfo.mode} mode` : 'Click Prepare above'}
            </span>
          </div>

          <div className="p-3 bg-paper-canvas border border-paper-border">
            <span className="text-[10px] text-ink-faint block uppercase">Trained Feedback</span>
            <strong className="text-sm font-bold text-ink mt-0.5 block">
              {candidateInfo ? candidateInfo.feedback_count : 0} items
            </strong>
            <span className="text-[10px] text-ink-muted">Model ancestry</span>
          </div>

          <div className="p-3 bg-paper-canvas border border-paper-border">
            <span className="text-[10px] text-ink-faint block uppercase">Gate Status</span>
            <div className="flex items-center gap-1.5 mt-0.5">
              {candidateInfo?.is_evaluated ? (
                <>
                  <Unlock className="w-3.5 h-3.5 text-emerald-700" />
                  <span className="font-bold text-emerald-800">Evaluated</span>
                </>
              ) : (
                <>
                  <Lock className="w-3.5 h-3.5 text-amber-800" />
                  <span className="font-bold text-amber-800">Evaluation Needed</span>
                </>
              )}
            </div>
            <span className="text-[10px] text-ink-muted">
              {candidateInfo?.is_evaluated ? 'Activation Unlocked' : 'Gate Locked'}
            </span>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* STEP 2: PRE-ACTIVATION PREDICTION DIFFING (Side-by-Side)                  */}
      {/* ========================================================================= */}
      <div className="bg-paper-sheet border border-paper-border shadow-paper p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-paper-border">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-rust font-bold">02 / COMPARE</span>
              <h3 className="font-serif text-lg font-bold text-ink">
                Compare predictions
              </h3>
            </div>
            <p className="text-xs text-ink-muted mt-0.5">
              Inspect inbox prediction changes between <strong className="text-ink">{activeLabel}</strong> and{' '}
              <strong className="text-ink">{candidateInfo?.label || 'Candidate'}</strong> before making decisions.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {diffData && (
              <label className="flex items-center gap-1.5 text-xs text-ink cursor-pointer mr-2 select-none">
                <input
                  type="checkbox"
                  checked={showChangedOnly}
                  onChange={(e) => setShowChangedOnly(e.target.checked)}
                  className="rounded-none border-paper-border text-rust focus:ring-rust"
                />
                <span>Changed only ({diffData.changed}/{diffData.total})</span>
              </label>
            )}

            <button
              onClick={handleRunDiff}
              disabled={!candidateInfo || isDiffing}
              className="inline-flex items-center gap-2 px-3 py-2 bg-paper-canvas hover:bg-paper-subtle border border-paper-border text-xs font-sans font-medium text-ink transition-colors cursor-pointer disabled:opacity-50"
            >
              <GitCompare className={`w-3.5 h-3.5 text-rust ${isDiffing ? 'animate-spin' : ''}`} />
              <span>{isDiffing ? 'Diffing Inbox...' : 'Diff Inbox Predictions'}</span>
            </button>
          </div>
        </div>

        {/* Diff Result Table */}
        {diffData ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs font-mono p-2 bg-paper-canvas border border-paper-border">
              <span>Total Compared: <strong className="text-ink">{diffData.total}</strong></span>
              <span>Category Changed: <strong className="text-rust">{diffData.category_changed}</strong></span>
              <span>Priority Changed: <strong className="text-rust">{diffData.priority_changed}</strong></span>
              <span>Overall Changed: <strong className="text-ink">{diffData.changed}</strong></span>
            </div>

            <div className="overflow-x-auto border border-paper-border">
              <table className="w-full text-left text-xs editorial-table">
                <thead className="bg-paper-subtle">
                  <tr>
                    <th className="p-2.5">ID / Subject</th>
                    <th className="p-2.5">Active ({activeLabel})</th>
                    <th className="p-2.5">Candidate ({candidateInfo?.label})</th>
                    <th className="p-2.5">Diff Status</th>
                    <th className="p-2.5">Training Set Member</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-paper-border bg-paper-sheet">
                  {displayedDiffRows.map((row) => (
                    <tr key={row.id} className={row.changed ? 'bg-[#fdfcf9]' : ''}>
                      {/* Subject */}
                      <td className="p-2.5 font-sans">
                        <span className="font-mono text-[10px] text-ink-faint block">#{row.id}</span>
                        <strong className="text-ink font-semibold">{row.subject}</strong>
                      </td>

                      {/* Active Prediction */}
                      <td className="p-2.5 font-mono">
                        <div>
                          <span className="font-medium text-ink">{row.before_category}</span>
                          <span className="text-paper-border mx-1">/</span>
                          <span className="text-ink-muted">{row.before_priority}</span>
                        </div>
                        <span className="text-[10px] text-ink-faint block">
                          {(row.before_category_confidence * 100).toFixed(0)}% cat · {(row.before_priority_confidence * 100).toFixed(0)}% pri
                        </span>
                      </td>

                      {/* Candidate Prediction */}
                      <td className="p-2.5 font-mono">
                        <div>
                          <span className={`font-medium ${row.category_changed ? 'text-rust font-bold' : 'text-ink'}`}>
                            {row.after_category}
                          </span>
                          <span className="text-paper-border mx-1">/</span>
                          <span className={`font-medium ${row.priority_changed ? 'text-rust font-bold' : 'text-ink-muted'}`}>
                            {row.after_priority}
                          </span>
                        </div>
                        <span className="text-[10px] text-ink-faint block">
                          {(row.after_category_confidence * 100).toFixed(0)}% cat · {(row.after_priority_confidence * 100).toFixed(0)}% pri
                        </span>
                      </td>

                      {/* Diff Status */}
                      <td className="p-2.5 font-mono text-[11px]">
                        {row.changed ? (
                          <span className="px-1.5 py-0.5 bg-amber-50 text-amber-900 border border-amber-300 font-semibold">
                            {row.category_changed && row.priority_changed ? 'Both Changed' : row.category_changed ? 'Category Changed' : 'Priority Changed'}
                          </span>
                        ) : (
                          <span className="text-ink-faint">Unchanged</span>
                        )}
                      </td>

                      {/* Training-set membership badge */}
                      <td className="p-2.5 font-mono text-[11px]">
                        {row.after_training_member ? (
                          <span className="px-2 py-0.5 bg-purple-50 text-purple-900 border border-purple-300 font-bold" title="Part of training corrections; do not confuse with held-out generalization">
                            In Training Set
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 bg-paper-subtle text-ink-muted border border-paper-border" title="Held-out or unseen email; represents real generalization">
                            Unseen Probe
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="p-6 bg-paper-canvas border border-dashed border-paper-border text-center text-xs text-ink-muted">
            <p>
              {candidateInfo 
                ? 'Click "Diff Inbox Predictions" to inspect side-by-side changes across all messages.' 
                : 'Prepare a candidate snapshot above to unlock prediction diffing.'}
            </p>
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* STEP 3: HELD-OUT EVALUATION GATE & CONFUSION MATRICES                     */}
      {/* ========================================================================= */}
      <div className="bg-paper-sheet border border-paper-border shadow-paper p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-paper-border">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-rust font-bold">03 / EVALUATE</span>
              <h3 className="font-serif text-lg font-bold text-ink">
                Held-Out Evaluation Gate
              </h3>
            </div>
            <p className="text-xs text-ink-muted mt-0.5">
              Use examples the candidate has not trained on. Review category and priority results before deciding whether to activate.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <select
              aria-label="Held-out evaluation dataset"
              value={selectedDataset}
              onChange={(e) => setSelectedDataset(e.target.value as any)}
              className="bg-paper-canvas border border-paper-border px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:border-rust"
            >
              <option value="demo_eval.csv">demo_eval.csv (10 Held-Out)</option>
              <option value="demo_eval_expanded.csv">demo_eval_expanded.csv (25 Scenarios)</option>
            </select>

            <button
              onClick={handleRunEvaluation}
              disabled={isEvaluating}
              className="inline-flex items-center gap-2 px-4 py-2 bg-rust text-white text-xs font-sans font-semibold hover:bg-rust-hover transition-colors cursor-pointer shadow-paper-sm disabled:opacity-50"
            >
              <FileCheck className={`w-3.5 h-3.5 ${isEvaluating ? 'animate-spin' : ''}`} />
              <span>{isEvaluating ? 'Evaluating Metrics...' : 'Run Held-Out Evaluation'}</span>
            </button>
          </div>
        </div>

        {/* Evaluation Metrics Cards */}
        {evalData ? (
          <div className="space-y-4">
            <div className="p-3 bg-paper-canvas border border-paper-border text-xs flex flex-wrap items-center justify-between gap-2 font-mono">
              <span>Dataset: <strong className="text-ink">{selectedDataset}</strong></span>
              <span>Dataset Hash: <strong className="text-ink">{evalData.heldout_hash.slice(0, 12)}...</strong></span>
              <span>Baseline: <strong className="text-ink">{evalData.baseline_version}</strong></span>
              <span>Candidate: <strong className="text-rust">{evalData.updated_version}</strong></span>
            </div>

            {/* Score Delta Grid */}
            {(() => {
              const catAccDelta = evalData.updated.category_accuracy - evalData.baseline.category_accuracy;
              const catF1Delta = evalData.updated.category_macro_f1 - evalData.baseline.category_macro_f1;
              const priAccDelta = evalData.updated.priority_accuracy - evalData.baseline.priority_accuracy;
              const priF1Delta = evalData.updated.priority_macro_f1 - evalData.baseline.priority_macro_f1;

              const catMatrix = evalData.updated.category_confusion_matrix;
              const catLabels = evalData.updated.category_labels || [];
              const priMatrix = evalData.updated.priority_confusion_matrix;
              const priLabels = evalData.updated.priority_labels || [];

              return (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs font-mono">
                    {/* Category Accuracy */}
                    <div className="p-3.5 bg-paper-sheet border border-paper-border">
                      <span className="text-[10px] uppercase text-ink-faint block">Category Accuracy</span>
                      <div className="flex items-baseline gap-2 mt-1">
                        <span className="text-lg font-bold text-ink">
                          {(evalData.updated.category_accuracy * 100).toFixed(1)}%
                        </span>
                        <span className="text-xs text-ink-muted">
                          (was {(evalData.baseline.category_accuracy * 100).toFixed(1)}%)
                        </span>
                      </div>
                      <div className={`mt-1 text-xs font-semibold flex items-center gap-1 ${catAccDelta >= 0 ? 'text-emerald-800' : 'text-rose-800'}`}>
                        {catAccDelta >= 0 ? '+' : ''}
                        {(catAccDelta * 100).toFixed(1)}% delta
                      </div>
                    </div>

                    {/* Category Macro-F1 */}
                    <div className="p-3.5 bg-paper-sheet border border-paper-border">
                      <span className="text-[10px] uppercase text-ink-faint block">Category Macro-F1</span>
                      <div className="flex items-baseline gap-2 mt-1">
                        <span className="text-lg font-bold text-ink">
                          {evalData.updated.category_macro_f1.toFixed(3)}
                        </span>
                        <span className="text-xs text-ink-muted">
                          (was {evalData.baseline.category_macro_f1.toFixed(3)})
                        </span>
                      </div>
                      <div className={`mt-1 text-xs font-semibold flex items-center gap-1 ${catF1Delta >= 0 ? 'text-emerald-800' : 'text-rose-800'}`}>
                        {catF1Delta >= 0 ? '+' : ''}
                        {catF1Delta.toFixed(3)} delta
                      </div>
                    </div>

                    {/* Priority Accuracy */}
                    <div className="p-3.5 bg-paper-sheet border border-paper-border">
                      <span className="text-[10px] uppercase text-ink-faint block">Priority Accuracy</span>
                      <div className="flex items-baseline gap-2 mt-1">
                        <span className="text-lg font-bold text-ink">
                          {(evalData.updated.priority_accuracy * 100).toFixed(1)}%
                        </span>
                        <span className="text-xs text-ink-muted">
                          (was {(evalData.baseline.priority_accuracy * 100).toFixed(1)}%)
                        </span>
                      </div>
                      <div className={`mt-1 text-xs font-semibold flex items-center gap-1 ${priAccDelta >= 0 ? 'text-emerald-800' : 'text-rose-800'}`}>
                        {priAccDelta >= 0 ? '+' : ''}
                        {(priAccDelta * 100).toFixed(1)}% delta
                      </div>
                    </div>

                    {/* Priority Macro-F1 */}
                    <div className="p-3.5 bg-paper-sheet border border-paper-border">
                      <span className="text-[10px] uppercase text-ink-faint block">Priority Macro-F1</span>
                      <div className="flex items-baseline gap-2 mt-1">
                        <span className="text-lg font-bold text-ink">
                          {evalData.updated.priority_macro_f1.toFixed(3)}
                        </span>
                        <span className="text-xs text-ink-muted">
                          (was {evalData.baseline.priority_macro_f1.toFixed(3)})
                        </span>
                      </div>
                      <div className={`mt-1 text-xs font-semibold flex items-center gap-1 ${priF1Delta >= 0 ? 'text-emerald-800' : 'text-rose-800'}`}>
                        {priF1Delta >= 0 ? '+' : ''}
                        {priF1Delta.toFixed(3)} delta
                      </div>
                    </div>
                  </div>

                  {/* Confusion Matrices (Side-by-Side Category and Priority) */}
                  {catMatrix && priMatrix && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                      {/* Category Confusion Matrix */}
                      <div className="p-3.5 bg-paper-canvas border border-paper-border space-y-2">
                        <span className="text-[10px] font-mono uppercase text-ink font-bold block">
                          Candidate Category Confusion Matrix
                        </span>
                        <div className="overflow-x-auto">
                          <table className="w-full text-center text-[10px] font-mono">
                            <thead>
                              <tr>
                                <th className="p-1 text-left text-ink-faint">True \ Pred</th>
                                {catLabels.map((l) => (
                                  <th key={l} className="p-1 truncate max-w-[50px] text-ink">{l.slice(0, 4)}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-paper-border">
                              {catMatrix.map((row, rIdx) => (
                                <tr key={rIdx}>
                                  <td className="p-1 text-left font-bold text-ink truncate max-w-[60px]">
                                    {catLabels[rIdx]?.slice(0, 6) || `Class ${rIdx}`}
                                  </td>
                                  {row.map((cell, cIdx) => (
                                    <td
                                      key={cIdx}
                                      className={`p-1 ${rIdx === cIdx && cell > 0 ? 'bg-emerald-100 font-bold text-emerald-900' : cell > 0 ? 'bg-amber-100 text-amber-900' : 'text-ink-faint'}`}
                                    >
                                      {cell}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      {/* Priority Confusion Matrix */}
                      <div className="p-3.5 bg-paper-canvas border border-paper-border space-y-2">
                        <span className="text-[10px] font-mono uppercase text-ink font-bold block">
                          Candidate Priority Confusion Matrix
                        </span>
                        <div className="overflow-x-auto">
                          <table className="w-full text-center text-[10px] font-mono">
                            <thead>
                              <tr>
                                <th className="p-1 text-left text-ink-faint">True \ Pred</th>
                                {priLabels.map((l) => (
                                  <th key={l} className="p-1 text-ink">{l}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-paper-border">
                              {priMatrix.map((row, rIdx) => (
                                <tr key={rIdx}>
                                  <td className="p-1 text-left font-bold text-ink">
                                    {priLabels[rIdx] || `Pri ${rIdx}`}
                                  </td>
                                  {row.map((cell, cIdx) => (
                                    <td
                                      key={cIdx}
                                      className={`p-1 ${rIdx === cIdx && cell > 0 ? 'bg-emerald-100 font-bold text-emerald-900' : cell > 0 ? 'bg-amber-100 text-amber-900' : 'text-ink-faint'}`}
                                    >
                                      {cell}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  )}
                </>
              );
            })()}
          </div>
        ) : (
          <div className="p-6 bg-paper-canvas border border-dashed border-paper-border text-center text-xs text-ink-muted">
            <p>Click "Run Held-Out Evaluation" to execute verification against {selectedDataset}.</p>
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* STEP 4: PRODUCTION ACTIVATION GATE                                        */}
      {/* ========================================================================= */}
      <div className="bg-paper-sheet border-2 border-ink p-5 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-rust font-bold">04 / DECIDE</span>
              <h3 className="font-serif text-lg font-bold text-ink">
                Choose whether to activate
              </h3>
            </div>
            <p className="text-xs text-ink-muted mt-0.5">
              Activation requires evaluation on the current demo_eval.csv dataset. The expanded dataset adds context but does not unlock activation. Evaluation does not guarantee improvement.
            </p>
          </div>

          <button
            onClick={handleActivateCandidate}
            disabled={!candidateInfo || !candidateInfo.is_evaluated || isActivating}
            className={`inline-flex items-center gap-2 px-5 py-2.5 text-xs font-sans font-bold text-white transition-colors cursor-pointer shadow-paper-sm ${
              candidateInfo && candidateInfo.is_evaluated
                ? 'bg-rust hover:bg-rust-hover'
                : 'bg-ink-muted opacity-50 cursor-not-allowed'
            }`}
          >
            {candidateInfo?.is_evaluated ? <Unlock className="w-4 h-4" /> : <Lock className="w-4 h-4" />}
            <span>
              {isActivating
                ? 'Activating...'
                : candidateInfo?.is_evaluated
                ? `Activate ${candidateInfo.label} to Production`
                : 'Evaluation Required to Activate'}
            </span>
          </button>
        </div>

        <div className="pt-2 border-t border-paper-border flex items-center justify-between text-[11px] font-mono text-ink-muted">
          <span>Active Pointer: <strong className="text-ink">{activeLabel}</strong></span>
          <span>
            {candidateInfo?.is_evaluated
              ? '✓ Held-out criteria met; candidate cleared for deployment.'
              : '✗ Run evaluation above to unlock candidate activation.'}
          </span>
        </div>
      </div>

    </div>
  );
};
