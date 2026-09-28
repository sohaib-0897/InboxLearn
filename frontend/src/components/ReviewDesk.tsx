import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  CheckSquare, 
  Filter, 
  ArrowUpDown, 
  Download, 
  Check, 
  AlertCircle, 
  Clock, 
  UserCheck, 
  Calendar, 
  Tag, 
  ChevronDown 
} from 'lucide-react';
import { api, EmailRow } from '../api/client';

export const ReviewDesk: React.FC<{ onFeedbackSaved?: () => void }> = ({ onFeedbackSaved }) => {
  const [emails, setEmails] = useState<EmailRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState('All categories');
  const [priorityFilter, setPriorityFilter] = useState('All priorities');
  const [order, setOrder] = useState('Lowest confidence first');
  const [unresolvedOnly, setUnresolvedOnly] = useState(false);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [saveSuccessId, setSaveSuccessId] = useState<number | null>(null);
  const [expandedHeaders, setExpandedHeaders] = useState<Record<number, boolean>>({});

  // Local draft corrections state
  const [drafts, setDrafts] = useState<Record<number, { category: string; priority: string }>>({});

  const loadEmails = async () => {
    setIsLoading(true);
    try {
      const res = await api.getInbox({
        include_confident: true,
        order,
        category: categoryFilter,
        priority: priorityFilter,
        unresolved: unresolvedOnly,
      });
      setEmails(res.rows);
      // Initialize drafts
      const initialDrafts: Record<number, { category: string; priority: string }> = {};
      res.rows.forEach((r) => {
        initialDrafts[r.id] = {
          category: r.effective_category,
          priority: r.effective_priority,
        };
      });
      setDrafts(initialDrafts);
    } catch (err) {
      console.error('Failed to load inbox emails', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadEmails();
  }, [categoryFilter, priorityFilter, order, unresolvedOnly]);

  const handleImportDemo = async () => {
    setIsLoading(true);
    try {
      await api.importDemo('demo_feedback.csv');
      await loadEmails();
      if (onFeedbackSaved) onFeedbackSaved();
    } catch (err) {
      console.error('Failed to import demonstration sample', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveCorrection = async (emailId: number) => {
    const draft = drafts[emailId];
    if (!draft) return;
    setSavingId(emailId);
    try {
      await api.saveFeedback(emailId, draft.category, draft.priority);
      setSaveSuccessId(emailId);
      setTimeout(() => setSaveSuccessId(null), 2500);
      await loadEmails();
      if (onFeedbackSaved) onFeedbackSaved();
    } catch (err) {
      console.error('Failed to save correction', err);
    } finally {
      setSavingId(null);
    }
  };

  const toggleHeader = (id: number) => {
    setExpandedHeaders((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header and Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="w-2 h-2 rounded-full bg-brand-cyan animate-pulse" />
            <span className="font-mono text-xs text-brand-cyan uppercase tracking-wider">
              HUMAN-IN-THE-LOOP TRIAGE DESK
            </span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            Review Queue & Correction Desk
          </h2>
          <p className="text-sm text-zinc-400 mt-1">
            Low-confidence predictions routed for human verification. Approved corrections train candidate models.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleImportDemo}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-surface-subtle hover:bg-surface-highlight border border-white/10 text-white font-mono text-xs hover:border-brand-cyan/40 transition-all cursor-pointer"
          >
            <Download className="w-3.5 h-3.5 text-brand-cyan" />
            <span>Load Demo Fixture (5 Emails)</span>
          </button>
        </div>
      </div>

      {/* Filter and Sorting Toolbar */}
      <div className="p-4 rounded-xl bg-surface/60 border border-white/5 flex flex-wrap items-center justify-between gap-4 backdrop-blur-md">
        <div className="flex flex-wrap items-center gap-3">
          {/* Category Filter */}
          <div className="flex items-center gap-1.5 text-xs font-mono">
            <Filter className="w-3.5 h-3.5 text-zinc-500" />
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="bg-surface-elevated border border-white/10 rounded-lg px-3 py-1.5 text-zinc-200 text-xs focus:outline-none focus:border-brand-indigo font-mono cursor-pointer"
            >
              <option value="All categories">All categories</option>
              <option value="job opportunities">job opportunities</option>
              <option value="university">university</option>
              <option value="bills">bills</option>
              <option value="promotions">promotions</option>
              <option value="spam">spam</option>
            </select>
          </div>

          {/* Priority Filter */}
          <div className="flex items-center gap-1.5 text-xs font-mono">
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="bg-surface-elevated border border-white/10 rounded-lg px-3 py-1.5 text-zinc-200 text-xs focus:outline-none focus:border-brand-indigo font-mono cursor-pointer"
            >
              <option value="All priorities">All priorities</option>
              <option value="low">low priority</option>
              <option value="normal">normal priority</option>
              <option value="high">high priority</option>
            </select>
          </div>

          {/* Unresolved Checkbox */}
          <label className="flex items-center gap-2 text-xs font-mono text-zinc-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={unresolvedOnly}
              onChange={(e) => setUnresolvedOnly(e.target.checked)}
              className="rounded bg-surface-elevated border-white/10 accent-brand-cyan text-brand-cyan focus:ring-0 cursor-pointer"
            />
            <span>Unresolved only</span>
          </label>
        </div>

        {/* Sorting Order */}
        <div className="flex items-center gap-2 text-xs font-mono">
          <ArrowUpDown className="w-3.5 h-3.5 text-zinc-500" />
          <select
            value={order}
            onChange={(e) => setOrder(e.target.value)}
            className="bg-surface-elevated border border-white/10 rounded-lg px-3 py-1.5 text-zinc-200 text-xs focus:outline-none focus:border-brand-indigo font-mono cursor-pointer"
          >
            <option value="Lowest confidence first">Lowest confidence first</option>
            <option value="Newest first">Newest first</option>
          </select>
        </div>
      </div>

      {/* Email Cards List */}
      {isLoading ? (
        <div className="py-20 text-center flex flex-col items-center justify-center space-y-3">
          <div className="w-8 h-8 border-2 border-brand-cyan/20 border-t-brand-cyan rounded-full animate-spin" />
          <span className="text-xs font-mono text-zinc-400">Loading inbox message ledger...</span>
        </div>
      ) : emails.length === 0 ? (
        <div className="p-16 rounded-2xl bg-surface/40 border border-dashed border-white/10 text-center space-y-4">
          <div className="w-12 h-12 rounded-xl bg-brand-cyan/10 border border-brand-cyan/20 flex items-center justify-center text-brand-cyan mx-auto">
            <CheckSquare className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-semibold text-white">No Review Messages Matching Filter</h3>
            <p className="text-xs text-zinc-400 max-w-sm mx-auto">
              All messages are classified or have feedback saved. Click "Load Demo Fixture" above to import 5 synthetic messages.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {emails.map((row) => {
            const draft = drafts[row.id] || { category: row.effective_category, priority: row.effective_priority };
            const isModified =
              draft.category !== row.predicted_category || draft.priority !== row.predicted_priority;
            const isNeedsReview = row.status === 'needs_review' && !row.feedback_id;

            return (
              <motion.div
                key={row.id}
                layout
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                className={`rounded-2xl border p-6 backdrop-blur-xl transition-all ${
                  isNeedsReview
                    ? 'bg-surface/90 border-brand-amber/30 shadow-tactile'
                    : 'bg-surface/60 border-white/5'
                }`}
              >
                {/* Meta Header */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/5 pb-4 mb-4">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs px-2.5 py-1 rounded bg-white/5 text-zinc-300 border border-white/5">
                      MSG #{row.id}
                    </span>
                    
                    <span className="font-mono text-xs text-zinc-500 uppercase">
                      SOURCE: {row.source_type || 'CSV'}
                    </span>

                    {row.date_header && (
                      <span className="font-mono text-xs text-zinc-500 flex items-center gap-1">
                        <Clock className="w-3 h-3" /> {row.date_header}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {row.status === 'needs_review' && !row.feedback_id && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-mono bg-brand-amber/15 text-brand-amber border border-brand-amber/30">
                        <AlertCircle className="w-3 h-3" />
                        NEEDS REVIEW
                      </span>
                    )}
                    {row.feedback_id && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-mono bg-brand-indigo/15 text-brand-indigo border border-brand-indigo/30">
                        <UserCheck className="w-3 h-3" />
                        FEEDBACK RECORDED
                      </span>
                    )}
                    {row.status === 'classified' && !row.feedback_id && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-mono bg-brand-emerald/15 text-brand-emerald border border-brand-emerald/30">
                        <Check className="w-3 h-3" />
                        AUTO-CLASSIFIED
                      </span>
                    )}
                  </div>
                </div>

                {/* Email Body Content */}
                <div className="space-y-2 mb-6">
                  <h4 className="text-base font-semibold text-white tracking-tight">
                    {row.subject}
                  </h4>
                  <div className="text-xs text-zinc-400 font-mono">
                    From: <span className="text-zinc-300">{row.sender || 'Not supplied'}</span>
                  </div>
                  <p className="text-sm text-zinc-300 leading-relaxed font-sans bg-void/50 p-4 rounded-xl border border-white/5 select-text">
                    {row.body}
                  </p>
                </div>

                {/* Extracted Entities */}
                {row.entities && row.entities.length > 0 && (
                  <div className="mb-6 flex flex-wrap gap-2">
                    {row.entities.map((e, idx) => (
                      <div
                        key={idx}
                        className="px-2 py-0.5 rounded bg-surface-subtle border border-white/5 text-[11px] font-mono text-zinc-300 flex items-center gap-1"
                      >
                        <Tag className="w-3 h-3 text-brand-cyan" />
                        <span className="text-brand-cyan capitalize">{e.type}:</span>
                        <span>{e.value}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Prediction vs Correction Form */}
                <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center p-4 rounded-xl bg-surface-elevated/70 border border-white/5">
                  {/* Left: Original Model Inference */}
                  <div className="md:col-span-5 space-y-1">
                    <div className="text-[11px] font-mono text-zinc-500 uppercase tracking-wider">
                      ORIGINAL PREDICTION (MODEL v{row.model_version_id})
                    </div>
                    <div className="text-sm font-semibold text-zinc-200 capitalize">
                      {row.predicted_category} · {row.predicted_priority} priority
                    </div>
                    <div className="text-xs font-mono text-zinc-500">
                      Category {(row.category_confidence * 100).toFixed(1)}% · Priority{' '}
                      {(row.priority_confidence * 100).toFixed(1)}%
                    </div>
                  </div>

                  {/* Right: Human Operator Correction Controls */}
                  <div className="md:col-span-7 flex flex-wrap items-center justify-end gap-3">
                    {/* Category Selector */}
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-mono text-zinc-500">Correct:</span>
                      <select
                        value={draft.category}
                        onChange={(e) =>
                          setDrafts((prev) => ({
                            ...prev,
                            [row.id]: { ...draft, category: e.target.value },
                          }))
                        }
                        className="bg-surface border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-brand-cyan font-mono cursor-pointer"
                      >
                        <option value="job opportunities">job opportunities</option>
                        <option value="university">university</option>
                        <option value="bills">bills</option>
                        <option value="promotions">promotions</option>
                        <option value="spam">spam</option>
                      </select>
                    </div>

                    {/* Priority Selector */}
                    <select
                      value={draft.priority}
                      onChange={(e) =>
                        setDrafts((prev) => ({
                          ...prev,
                          [row.id]: { ...draft, priority: e.target.value },
                        }))
                      }
                      className="bg-surface border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-brand-cyan font-mono cursor-pointer"
                    >
                      <option value="low">low priority</option>
                      <option value="normal">normal priority</option>
                      <option value="high">high priority</option>
                    </select>

                    {/* Commit Feedback Button */}
                    <button
                      onClick={() => handleSaveCorrection(row.id)}
                      disabled={savingId === row.id}
                      className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-brand-cyan/20 hover:bg-brand-cyan/30 border border-brand-cyan/40 text-brand-cyan text-xs font-mono font-semibold transition-all shadow-glow-cyan disabled:opacity-50 cursor-pointer"
                    >
                      {savingId === row.id ? (
                        <>
                          <span className="w-3 h-3 border border-brand-cyan/30 border-t-brand-cyan rounded-full animate-spin" />
                          <span>Saving...</span>
                        </>
                      ) : saveSuccessId === row.id ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-brand-emerald" />
                          <span className="text-brand-emerald">Feedback Saved!</span>
                        </>
                      ) : (
                        <>
                          <CheckSquare className="w-3.5 h-3.5" />
                          <span>Save Feedback</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Routing Reason */}
                {row.routing_reason && (
                  <div className="mt-3 text-[11px] font-mono text-zinc-500">
                    ℹ️ {row.routing_reason}
                  </div>
                )}
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
};
