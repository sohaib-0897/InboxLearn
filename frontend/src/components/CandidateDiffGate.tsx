import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  GitCompare, 
  Cpu, 
  ShieldCheck, 
  CheckCircle2, 
  AlertTriangle, 
  ArrowRight, 
  TrendingUp, 
  TrendingDown, 
  Layers, 
  FileCheck, 
  Check 
} from 'lucide-react';
import { api, DiffResponse, EvaluationResponse } from '../api/client';
import { MetricCounter } from './MetricCounter';

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
    try {
      const res = await api.diffModels(activeVersionId, candidateInfo.version_id);
      setDiffData(res);
    } catch (err: any) {
      console.error('Diff error', err);
    } finally {
      setIsDiffing(false);
    }
  };

  const handleRunEvaluation = async () => {
    if (!candidateInfo) return;
    setIsEvaluating(true);
    setActivateError(null);
    try {
      const res = await api.evaluateModel(candidateInfo.version_id, selectedDataset);
      setEvalData(res);
      onRefresh();
    } catch (err: any) {
      console.error('Evaluation error', err);
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleActivate = async () => {
    if (!candidateInfo) return;
    setIsActivating(true);
    setActivateError(null);
    setActivateSuccess(null);
    try {
      await api.activateModel(candidateInfo.version_id);
      setActivateSuccess(`Model ${candidateInfo.label} successfully activated!`);
      onRefresh();
    } catch (err: any) {
      setActivateError(err.message || 'Activation blocked by quality gate.');
    } finally {
      setIsActivating(false);
    }
  };

  const filteredDiffRows = diffData?.rows.filter((r) => !showChangedOnly || r.changed) || [];

  return (
    <div className="space-y-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="w-2 h-2 rounded-full bg-brand-violet animate-pulse" />
            <span className="font-mono text-xs text-brand-violet uppercase tracking-wider">
              SAFE DEPLOYMENT LIFECYCLE
            </span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            Candidate Preparation & Evaluation Gate
          </h2>
          <p className="text-sm text-zinc-400 mt-1">
            Pre-activation prediction diffing and strict held-out evaluation gating before model activation.
          </p>
        </div>

        {/* Preparation Button */}
        <div className="flex items-center gap-3">
          <button
            onClick={handlePrepareCandidate}
            disabled={isPreparing}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-brand-violet hover:bg-brand-violet/90 text-white font-mono text-xs font-semibold shadow-tactile transition-all disabled:opacity-50 cursor-pointer"
          >
            {isPreparing ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Training Safe Candidate...</span>
              </>
            ) : (
              <>
                <Cpu className="w-4 h-4" />
                <span>Prepare Candidate Snapshot</span>
              </>
            )}
          </button>
        </div>
      </div>

      {prepareMessage && (
        <div className="p-4 rounded-xl bg-surface border border-brand-violet/30 text-xs font-mono text-zinc-300 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-brand-violet shrink-0" />
          <span>{prepareMessage}</span>
        </div>
      )}

      {/* Candidate Status Panel */}
      <div className="rounded-2xl bg-surface/80 border border-white/10 p-6 backdrop-blur-xl shadow-tactile">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/5 pb-4 mb-6">
          <div>
            <span className="font-mono text-xs text-zinc-400 font-semibold tracking-wider">
              CURRENT CANDIDATE REGISTER
            </span>
            <div className="text-lg font-bold text-white mt-1 flex items-center gap-3">
              {candidateInfo ? (
                <>
                  <span>Candidate {candidateInfo.label}</span>
                  <span className="text-xs font-mono px-2.5 py-0.5 rounded bg-brand-violet/20 text-brand-violet border border-brand-violet/30">
                    INACTIVE SNAPSHOT
                  </span>
                </>
              ) : (
                <span className="text-zinc-500 font-normal text-sm">
                  No candidate snapshot prepared. Save feedback in the Review Desk, then click "Prepare Candidate".
                </span>
              )}
            </div>
          </div>

          {candidateInfo && (
            <div className="flex items-center gap-3">
              <button
                onClick={handleRunDiff}
                disabled={isDiffing}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-surface-subtle hover:bg-surface-highlight border border-white/10 text-white font-mono text-xs transition-colors cursor-pointer"
              >
                <GitCompare className="w-3.5 h-3.5 text-brand-cyan" />
                <span>{isDiffing ? 'Diffing...' : 'Diff Inbox Predictions'}</span>
              </button>

              <button
                onClick={handleRunEvaluation}
                disabled={isEvaluating}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-surface-subtle hover:bg-surface-highlight border border-white/10 text-white font-mono text-xs transition-colors cursor-pointer"
              >
                <FileCheck className="w-3.5 h-3.5 text-brand-emerald" />
                <span>{isEvaluating ? 'Evaluating...' : 'Run Held-Out Eval'}</span>
              </button>
            </div>
          )}
        </div>

        {candidateInfo && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
            <div className="p-3 rounded-xl bg-void/50 border border-white/5">
              <span className="text-zinc-500">PARENT VERSION</span>
              <div className="text-sm font-semibold text-white mt-1">v{candidateInfo.parent_id}</div>
            </div>
            <div className="p-3 rounded-xl bg-void/50 border border-white/5">
              <span className="text-zinc-500">TRAINING MODE</span>
              <div className="text-sm font-semibold text-white mt-1 capitalize truncate">
                {candidateInfo.mode.replace(/_/g, ' ')}
              </div>
            </div>
            <div className="p-3 rounded-xl bg-void/50 border border-white/5">
              <span className="text-zinc-500">TRAINED FEEDBACK</span>
              <div className="text-sm font-semibold text-white mt-1">{candidateInfo.feedback_count} corrections</div>
            </div>
            <div className="p-3 rounded-xl bg-void/50 border border-white/5">
              <span className="text-zinc-500">EVALUATION GATE</span>
              <div className="text-sm font-semibold mt-1 flex items-center gap-1.5">
                {candidateInfo.is_evaluated ? (
                  <span className="text-brand-emerald flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> PASSED
                  </span>
                ) : (
                  <span className="text-brand-amber flex items-center gap-1">
                    <AlertTriangle className="w-3.5 h-3.5" /> UNTESTED
                  </span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Pre-Activation Evaluation Gate Block */}
      {evalData && (
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl bg-surface-elevated border border-brand-emerald/30 p-6 backdrop-blur-xl shadow-tactile space-y-6"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/5 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-brand-emerald" />
                <h3 className="text-lg font-bold text-white">
                  Held-Out Evaluation Gate Results
                </h3>
              </div>
              <p className="text-xs text-zinc-400 font-mono mt-1">
                Comparing Baseline {evalData.baseline_version} vs Candidate {evalData.updated_version} on {selectedDataset}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <select
                value={selectedDataset}
                onChange={(e) => setSelectedDataset(e.target.value as any)}
                className="bg-surface border border-white/10 rounded-lg px-3 py-1.5 text-xs text-zinc-300 font-mono"
              >
                <option value="demo_eval.csv">demo_eval.csv (10 examples)</option>
                <option value="demo_eval_expanded.csv">demo_eval_expanded.csv (25 scenarios)</option>
              </select>
            </div>
          </div>

          {/* Metric Comparison Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* Category Accuracy */}
            <div className="p-4 rounded-xl bg-surface/70 border border-white/5 space-y-1">
              <div className="text-[11px] font-mono text-zinc-400">Category Accuracy</div>
              <div className="text-xl font-bold font-mono text-white">
                {(evalData.updated.category_accuracy * 100).toFixed(1)}%
              </div>
              <div className="flex items-center gap-1 text-xs font-mono">
                {evalData.delta.category_accuracy >= 0 ? (
                  <span className="text-brand-emerald flex items-center">
                    <TrendingUp className="w-3.5 h-3.5 mr-0.5" /> +
                    {(evalData.delta.category_accuracy * 100).toFixed(1)}%
                  </span>
                ) : (
                  <span className="text-brand-rose flex items-center">
                    <TrendingDown className="w-3.5 h-3.5 mr-0.5" />
                    {(evalData.delta.category_accuracy * 100).toFixed(1)}%
                  </span>
                )}
                <span className="text-zinc-500">from {(evalData.baseline.category_accuracy * 100).toFixed(1)}%</span>
              </div>
            </div>

            {/* Category Macro-F1 */}
            <div className="p-4 rounded-xl bg-surface/70 border border-white/5 space-y-1">
              <div className="text-[11px] font-mono text-zinc-400">Category Macro-F1</div>
              <div className="text-xl font-bold font-mono text-white">
                {evalData.updated.category_macro_f1.toFixed(3)}
              </div>
              <div className="flex items-center gap-1 text-xs font-mono">
                {evalData.delta.category_macro_f1 >= 0 ? (
                  <span className="text-brand-emerald flex items-center">
                    <TrendingUp className="w-3.5 h-3.5 mr-0.5" /> +
                    {evalData.delta.category_macro_f1.toFixed(3)}
                  </span>
                ) : (
                  <span className="text-brand-rose flex items-center">
                    <TrendingDown className="w-3.5 h-3.5 mr-0.5" />
                    {evalData.delta.category_macro_f1.toFixed(3)}
                  </span>
                )}
                <span className="text-zinc-500">from {evalData.baseline.category_macro_f1.toFixed(3)}</span>
              </div>
            </div>

            {/* Priority Accuracy */}
            <div className="p-4 rounded-xl bg-surface/70 border border-white/5 space-y-1">
              <div className="text-[11px] font-mono text-zinc-400">Priority Accuracy</div>
              <div className="text-xl font-bold font-mono text-white">
                {(evalData.updated.priority_accuracy * 100).toFixed(1)}%
              </div>
              <div className="flex items-center gap-1 text-xs font-mono">
                {evalData.delta.priority_accuracy >= 0 ? (
                  <span className="text-brand-emerald flex items-center">
                    <TrendingUp className="w-3.5 h-3.5 mr-0.5" /> +
                    {(evalData.delta.priority_accuracy * 100).toFixed(1)}%
                  </span>
                ) : (
                  <span className="text-brand-rose flex items-center">
                    <TrendingDown className="w-3.5 h-3.5 mr-0.5" />
                    {(evalData.delta.priority_accuracy * 100).toFixed(1)}%
                  </span>
                )}
                <span className="text-zinc-500">from {(evalData.baseline.priority_accuracy * 100).toFixed(1)}%</span>
              </div>
            </div>

            {/* Priority Macro-F1 */}
            <div className="p-4 rounded-xl bg-surface/70 border border-white/5 space-y-1">
              <div className="text-[11px] font-mono text-zinc-400">Priority Macro-F1</div>
              <div className="text-xl font-bold font-mono text-white">
                {evalData.updated.priority_macro_f1.toFixed(3)}
              </div>
              <div className="flex items-center gap-1 text-xs font-mono">
                {evalData.delta.priority_macro_f1 >= 0 ? (
                  <span className="text-brand-emerald flex items-center">
                    <TrendingUp className="w-3.5 h-3.5 mr-0.5" /> +
                    {evalData.delta.priority_macro_f1.toFixed(3)}
                  </span>
                ) : (
                  <span className="text-brand-rose flex items-center">
                    <TrendingDown className="w-3.5 h-3.5 mr-0.5" />
                    {evalData.delta.priority_macro_f1.toFixed(3)}
                  </span>
                )}
                <span className="text-zinc-500">from {evalData.baseline.priority_macro_f1.toFixed(3)}</span>
              </div>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-void/50 border border-white/5 text-[11px] font-mono text-zinc-400">
            {evalData.note} Heldout dataset SHA-256: <span className="text-zinc-300">{evalData.heldout_hash.slice(0, 16)}...</span>
          </div>
        </motion.div>
      )}

      {/* Pre-Activation Prediction Diff Table */}
      {diffData && (
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl bg-surface/80 border border-white/10 p-6 backdrop-blur-xl shadow-tactile space-y-6"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/5 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <GitCompare className="w-5 h-5 text-brand-cyan" />
                <h3 className="text-lg font-bold text-white">
                  Pre-Activation Prediction Diffing
                </h3>
              </div>
              <p className="text-xs text-zinc-400 font-mono mt-1">
                Comparing {diffData.total} stored inbox emails between Baseline {activeLabel} and Candidate {candidateInfo?.label}.
              </p>
            </div>

            <div className="flex items-center gap-4">
              <span className="text-xs font-mono px-3 py-1 rounded bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/20">
                {diffData.changed} / {diffData.total} Predictions Changed
              </span>

              <label className="flex items-center gap-2 text-xs font-mono text-zinc-400 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={showChangedOnly}
                  onChange={(e) => setShowChangedOnly(e.target.checked)}
                  className="rounded bg-surface-elevated border-white/10 accent-brand-cyan cursor-pointer"
                />
                <span>Changed only</span>
              </label>
            </div>
          </div>

          {/* Diff Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono border-collapse">
              <thead>
                <tr className="border-b border-white/10 text-zinc-500 uppercase tracking-wider text-[11px]">
                  <th className="py-3 px-3">Email ID</th>
                  <th className="py-3 px-4">Subject</th>
                  <th className="py-3 px-3">Split Membership</th>
                  <th className="py-3 px-4">Baseline ({activeLabel})</th>
                  <th className="py-3 px-4">Candidate ({candidateInfo?.label})</th>
                  <th className="py-3 px-3">Diff Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {filteredDiffRows.map((row) => (
                  <tr key={row.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-3 px-3 text-zinc-400 font-mono">#{row.id}</td>
                    <td className="py-3 px-4 text-zinc-200 max-w-xs truncate" title={row.subject}>
                      {row.subject}
                    </td>
                    <td className="py-3 px-3">
                      {row.after_training_member ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-brand-violet/20 text-brand-violet border border-brand-violet/30">
                          TRAINING MEMBER
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-zinc-800 text-zinc-400 border border-zinc-700">
                          HELD-OUT / INBOX
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="capitalize text-zinc-300">
                        {row.before_category}
                      </div>
                      <div className="text-[10px] text-zinc-500">
                        {row.before_priority} · {(row.before_category_confidence * 100).toFixed(0)}%
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className={`capitalize ${row.category_changed ? 'text-brand-cyan font-bold' : 'text-zinc-300'}`}>
                        {row.after_category}
                      </div>
                      <div className={`text-[10px] ${row.priority_changed ? 'text-brand-cyan font-bold' : 'text-zinc-500'}`}>
                        {row.after_priority} · {(row.after_category_confidence * 100).toFixed(0)}%
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      {row.changed ? (
                        <span className="px-2 py-0.5 rounded bg-brand-cyan/15 text-brand-cyan border border-brand-cyan/30 text-[10px]">
                          CHANGED
                        </span>
                      ) : (
                        <span className="text-zinc-600 text-[10px]">UNALTERED</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}

      {/* Activation Action Gate Banner */}
      {candidateInfo && (
        <div className="p-6 rounded-2xl bg-gradient-to-r from-brand-indigo/10 via-surface to-brand-emerald/10 border border-white/10 flex flex-col md:flex-row items-center justify-between gap-6 backdrop-blur-xl">
          <div className="space-y-1">
            <h4 className="text-base font-bold text-white flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-brand-emerald" />
              Evaluation-Gated Candidate Activation
            </h4>
            <p className="text-xs text-zinc-400 max-w-xl">
              Candidates must be evaluated on the current held-out dataset before activation. The application service enforces this gate at the Python and SQLite layers.
            </p>
          </div>

          <div className="flex flex-col items-end gap-2 w-full md:w-auto">
            <button
              onClick={handleActivate}
              disabled={isActivating || !candidateInfo.is_evaluated}
              className="w-full md:w-auto flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-brand-emerald hover:bg-brand-emerald/90 text-white font-mono text-xs font-bold shadow-glow-emerald transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              {isActivating ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Validating Quality Gate & Flipping Pointer...</span>
                </>
              ) : (
                <>
                  <Check className="w-4 h-4" />
                  <span>Activate {candidateInfo.label} to Production</span>
                </>
              )}
            </button>

            {!candidateInfo.is_evaluated && (
              <span className="text-[11px] font-mono text-brand-amber flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> Run held-out evaluation first to unlock
              </span>
            )}
          </div>
        </div>
      )}

      {activateError && (
        <div className="p-4 rounded-xl bg-brand-rose/10 border border-brand-rose/30 text-brand-rose text-xs font-mono flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{activateError}</span>
        </div>
      )}

      {activateSuccess && (
        <div className="p-4 rounded-xl bg-brand-emerald/10 border border-brand-emerald/30 text-brand-emerald text-xs font-mono flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{activateSuccess}</span>
        </div>
      )}
    </div>
  );
};
