import React, { useState, useEffect } from 'react';
import { 
  History, 
  RotateCcw, 
  ShieldCheck, 
  CheckCircle2, 
  GitCommit, 
  Clock, 
  Cpu, 
  Check, 
  AlertTriangle,
  RefreshCw,
  FileCheck
} from 'lucide-react';
import { api, ModelVersion } from '../api/client';

export const VersionLedger: React.FC<{ onRollback?: () => void }> = ({ onRollback }) => {
  const [versions, setVersions] = useState<ModelVersion[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [rollingBackId, setRollingBackId] = useState<number | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadVersions = async () => {
    setIsLoading(true);
    try {
      const res = await api.getModels();
      setVersions(res.versions);
      setLoadError(null);
    } catch (err) {
      console.error('Failed to load model versions', err);
      setLoadError(err instanceof Error ? err.message : 'Model versions could not be loaded.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadVersions();
  }, []);

  const handleRollback = async (versionId: number) => {
    setRollingBackId(versionId);
    setSuccessMessage(null);
    setErrorMessage(null);
    try {
      const res = await api.rollbackModel(versionId);
      setSuccessMessage(`Successfully rolled back active model pointer to ${res.rolled_back_to.label}! All probe predictions and confidence estimates return to historical state.`);
      await loadVersions();
      if (onRollback) onRollback();
    } catch (err: any) {
      setErrorMessage(err.message || 'Rollback failed.');
    } finally {
      setRollingBackId(null);
    }
  };

  return (
    <div className="workspace-ledger space-y-6 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-4 border-b border-paper-border">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-[10px] tracking-wider uppercase text-rust font-semibold">
              04 / YOUR MODEL HISTORY
            </span>
            <span className="text-paper-border">·</span>
            <span className="font-mono text-[10px] text-ink-muted">
              A RECORD OF EVERY STEP
            </span>
          </div>
          <h2 className="font-serif text-2xl sm:text-3xl font-bold text-ink">
            Version history & rollback
          </h2>
          <p className="text-xs text-ink-muted mt-1 max-w-2xl leading-relaxed">
            Inspect saved model snapshots and their evaluation records. Restore a previous version when you need to reverse an activation; your feedback stays in the ledger.
          </p>
        </div>

        <div className="flex items-center gap-2 font-mono text-xs text-ink-muted bg-paper-sheet border border-paper-border px-3 py-2 shadow-paper-sm">
          <ShieldCheck className="w-4 h-4 text-emerald-800" />
          <span>Saved versions. A way back.</span>
        </div>
      </div>

      {/* Notifications */}
      {successMessage && (
        <div className="p-3.5 bg-emerald-50 border-l-4 border-emerald-700 border-y border-r border-emerald-200 text-xs text-emerald-950 flex items-center justify-between shadow-paper-sm">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-700 flex-shrink-0" />
            <span>{successMessage}</span>
          </div>
          <button onClick={() => setSuccessMessage(null)} className="text-xs text-emerald-800 hover:text-emerald-950 underline cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {errorMessage && (
        <div className="p-3.5 bg-rose-50 border-l-4 border-rose-700 border-y border-r border-rose-200 text-xs text-rose-950 flex items-center justify-between shadow-paper-sm">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-700 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button onClick={() => setErrorMessage(null)} className="text-xs text-rose-800 hover:text-rose-950 underline cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {loadError && (
        <div className="workspace-inline-error" role="alert">
          <span><strong>Version history unavailable.</strong> {loadError}</span>
          <button type="button" onClick={loadVersions} disabled={isLoading}>{isLoading ? 'Retrying…' : 'Retry'}</button>
        </div>
      )}

      {/* Ledger Table Container */}
      <div className="bg-paper-sheet border border-paper-border shadow-paper overflow-hidden">
        <div className="px-4 py-2.5 bg-paper-subtle border-b-2 border-ink flex items-center justify-between text-[11px] font-mono uppercase tracking-wider text-ink font-semibold">
          <span>Snapshot Version History ({loadError ? 'unavailable' : isLoading ? 'loading' : versions.length})</span>
          <span className="text-[10px] text-ink-faint lowercase tracking-normal">Scroll for details and rollback</span>
        </div>

        {isLoading && <div className="workspace-empty-state" role="status">Loading saved model versions…</div>}
        {!isLoading && loadError && versions.length === 0 && <div className="workspace-empty-state">Version history could not be reached.</div>}
        {!isLoading && !loadError && versions.length === 0 && <div className="workspace-empty-state">No saved model versions are available yet.</div>}
        {versions.length > 0 && <div className="overflow-x-auto">
          <table className="w-full text-left text-xs editorial-table">
            <thead className="bg-paper-subtle">
              <tr>
                <th className="p-3">Version</th>
                <th className="p-3">Status</th>
                <th className="p-3">Training Mode</th>
                <th className="p-3">Composition</th>
                <th className="p-3">Created</th>
                <th className="p-3">Evaluation Record</th>
                <th className="p-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-paper-border bg-paper-sheet">
              {versions.map((ver) => {
                const isActive = Boolean(ver.is_active);
                const isRolling = rollingBackId === ver.id;

                return (
                  <tr key={ver.id} className={isActive ? 'bg-[#fcfaf7]' : ''}>
                    {/* Version Label */}
                    <td className="p-3 font-mono">
                      <div className="flex items-center gap-2">
                        <strong className="text-sm font-bold text-ink">{ver.label}</strong>
                        <span className="text-[10px] text-ink-muted capitalize">({ver.kind})</span>
                      </div>
                    </td>

                    {/* Status Badge */}
                    <td className="p-3 font-mono text-[11px]">
                      {isActive ? (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 bg-emerald-100 text-emerald-900 border border-emerald-300 font-bold uppercase">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-700" />
                          <span>Active Pointer</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 bg-paper-subtle text-ink-muted border border-paper-border uppercase">
                          <span>Inactive Snapshot</span>
                        </span>
                      )}
                    </td>

                    {/* Training Mode */}
                    <td className="p-3 font-mono text-ink">
                      <span>{ver.metadata?.training_mode?.replace(/_/g, ' ') || 'Not recorded'}</span>
                    </td>

                    {/* Composition */}
                    <td className="p-3 font-mono text-ink-muted">
                      <span>{ver.metadata?.seed_count ?? '—'} seed · {ver.metadata?.feedback_count ?? '—'} feedback</span>
                    </td>

                    {/* Timestamp */}
                    <td className="p-3 font-mono text-[11px] text-ink-faint">
                      <span>{ver.created_at ? new Date(ver.created_at).toLocaleString() : '—'}</span>
                    </td>

                    {/* Evaluation Summary */}
                    <td className="p-3 font-mono text-[11px]">
                      {ver.evaluation_summary ? (
                        <div className="text-ink">
                          <span>Cat: {(ver.evaluation_summary.category_accuracy * 100).toFixed(0)}%</span>
                          <span className="text-paper-border mx-1">·</span>
                          <span>Pri: {(ver.evaluation_summary.priority_accuracy * 100).toFixed(0)}%</span>
                        </div>
                      ) : (
                        <span className="text-ink-faint italic">No evaluation logged</span>
                      )}
                    </td>

                    {/* Action */}
                    <td className="p-3 text-right">
                      {isActive ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-mono text-emerald-800 font-semibold">
                          <Check className="w-3.5 h-3.5" />
                          <span>Active</span>
                        </span>
                      ) : (
                        <button
                          onClick={() => handleRollback(ver.id)}
                          disabled={isRolling}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-paper-canvas hover:bg-paper-subtle border border-paper-border text-ink text-xs font-sans font-medium transition-colors cursor-pointer shadow-paper-sm disabled:opacity-50"
                        >
                          <RotateCcw className={`w-3 h-3 text-rust ${isRolling ? 'animate-spin' : ''}`} />
                          <span>{isRolling ? 'Restoring...' : 'Roll Back to this Version'}</span>
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>}
      </div>

    </div>
  );
};
