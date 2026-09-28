import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  History, 
  RotateCcw, 
  ShieldCheck, 
  CheckCircle2, 
  GitCommit, 
  Binary, 
  Clock, 
  Cpu, 
  Check 
} from 'lucide-react';
import { api, ModelVersion } from '../api/client';

export const VersionLedger: React.FC<{ onRollback?: () => void }> = ({ onRollback }) => {
  const [versions, setVersions] = useState<ModelVersion[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [rollingBackId, setRollingBackId] = useState<number | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadVersions = async () => {
    setIsLoading(true);
    try {
      const res = await api.getModels();
      setVersions(res.versions);
    } catch (err) {
      console.error('Failed to load model versions', err);
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
      setSuccessMessage(`Successfully restored active model pointer to ${res.rolled_back_to.label}!`);
      await loadVersions();
      if (onRollback) onRollback();
    } catch (err: any) {
      setErrorMessage(err.message || 'Rollback failed.');
    } finally {
      setRollingBackId(null);
    }
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="w-2 h-2 rounded-full bg-brand-emerald animate-pulse" />
            <span className="font-mono text-xs text-brand-emerald uppercase tracking-wider">
              IMMUTABLE SNAPSHOT LEDGER
            </span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            Model Lineage & One-Click Rollback
          </h2>
          <p className="text-sm text-zinc-400 mt-1">
            Historical models are stored as immutable snapshots in SQLite using safe IBL1 serialization. Any version can be restored instantly with exact bit-level reproduction.
          </p>
        </div>

        <div className="flex items-center gap-2 font-mono text-xs text-zinc-400">
          <ShieldCheck className="w-4 h-4 text-brand-emerald" />
          <span>Zero Pickle Blobs · IBL1 Explicit Array Format</span>
        </div>
      </div>

      {successMessage && (
        <div className="p-4 rounded-xl bg-brand-emerald/10 border border-brand-emerald/30 text-brand-emerald text-xs font-mono flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div className="p-4 rounded-xl bg-brand-rose/10 border border-brand-rose/30 text-brand-rose text-xs font-mono flex items-center gap-2">
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Ledger Table / Cards */}
      {isLoading ? (
        <div className="py-20 text-center flex flex-col items-center justify-center space-y-3">
          <div className="w-8 h-8 border-2 border-brand-emerald/20 border-t-brand-emerald rounded-full animate-spin" />
          <span className="text-xs font-mono text-zinc-400">Loading version lineage...</span>
        </div>
      ) : (
        <div className="space-y-4">
          {versions.map((ver) => {
            const isActive = Boolean(ver.is_active);
            const meta = ver.metadata || {};

            return (
              <motion.div
                key={ver.id}
                layout
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`rounded-2xl border p-6 backdrop-blur-xl transition-all ${
                  isActive
                    ? 'bg-surface-elevated/90 border-brand-emerald/40 shadow-tactile'
                    : 'bg-surface/60 border-white/5 hover:border-white/10'
                }`}
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  {/* Left: Version Identity & Tag */}
                  <div className="flex items-start gap-4">
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center font-mono font-bold text-base border shrink-0 ${
                      isActive
                        ? 'bg-brand-emerald/15 text-brand-emerald border-brand-emerald/30 shadow-glow-emerald'
                        : 'bg-surface-subtle text-zinc-400 border-white/10'
                    }`}>
                      {ver.label.toUpperCase()}
                    </div>

                    <div className="space-y-1">
                      <div className="flex items-center gap-2.5">
                        <h4 className="text-base font-bold text-white font-mono">
                          Model Version {ver.label}
                        </h4>
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-white/5 text-zinc-400 border border-white/5 capitalize">
                          {ver.kind}
                        </span>
                        {isActive && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-mono bg-brand-emerald/15 text-brand-emerald border border-brand-emerald/30">
                            <Check className="w-3 h-3" />
                            ACTIVE DEPLOYMENT
                          </span>
                        )}
                      </div>

                      <div className="text-xs text-zinc-400 font-mono flex flex-wrap items-center gap-3">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3 text-zinc-500" /> {ver.created_at}
                        </span>
                        <span>·</span>
                        <span>Parent: {ver.parent_id ? `v${ver.parent_id}` : 'None (Root)'}</span>
                        <span>·</span>
                        <span className="text-brand-indigo capitalize">
                          {meta.training_mode ? meta.training_mode.replace(/_/g, ' ') : 'Seed baseline'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Right: Rollback / Active CTA */}
                  <div className="flex items-center gap-3 self-end md:self-auto">
                    {isActive ? (
                      <div className="px-4 py-2 rounded-xl bg-brand-emerald/10 border border-brand-emerald/30 text-brand-emerald font-mono text-xs flex items-center gap-1.5">
                        <CheckCircle2 className="w-4 h-4" />
                        <span>Currently Serving Predictions</span>
                      </div>
                    ) : (
                      <button
                        onClick={() => handleRollback(ver.id)}
                        disabled={rollingBackId === ver.id}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl bg-surface-subtle hover:bg-surface-highlight border border-white/10 text-white font-mono text-xs transition-all hover:border-brand-emerald/40 cursor-pointer disabled:opacity-50"
                      >
                        {rollingBackId === ver.id ? (
                          <>
                            <span className="w-3.5 h-3.5 border border-white/30 border-t-white rounded-full animate-spin" />
                            <span>Restoring Snapshot...</span>
                          </>
                        ) : (
                          <>
                            <RotateCcw className="w-3.5 h-3.5 text-brand-emerald" />
                            <span>Roll Back to {ver.label}</span>
                          </>
                        )}
                      </button>
                    )}
                  </div>
                </div>

                {/* Metadata Details & Composition */}
                <div className="mt-4 pt-4 border-t border-white/5 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                  <div className="p-2.5 rounded-lg bg-void/50 border border-white/5">
                    <span className="text-zinc-500 text-[10px]">SEED CORPUS</span>
                    <div className="text-zinc-200 mt-0.5">{meta.seed_count || 15} examples</div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-void/50 border border-white/5">
                    <span className="text-zinc-500 text-[10px]">TRAINED FEEDBACK</span>
                    <div className="text-zinc-200 mt-0.5">{meta.trained_feedback_count || 0} corrections</div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-void/50 border border-white/5">
                    <span className="text-zinc-500 text-[10px]">SERIALIZATION</span>
                    <div className="text-brand-emerald mt-0.5">IBL1 Binary Float64</div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-void/50 border border-white/5">
                    <span className="text-zinc-500 text-[10px]">RECIPE VERSION</span>
                    <div className="text-zinc-400 mt-0.5 truncate">{meta.recipe_version || 'sgd-feedback-v1'}</div>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
};
