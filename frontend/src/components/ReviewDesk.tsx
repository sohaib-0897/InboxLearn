import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'motion/react';
import { useMotionPreference } from '../useMotionPreference';
import { 
  Inbox, 
  AlertCircle, 
  CheckCircle2, 
  Edit3, 
  ArrowUpDown, 
  Filter, 
  Download, 
  Upload,
  FileText, 
  Calendar, 
  DollarSign, 
  Tag, 
  Check, 
  ChevronRight, 
  ArrowLeft,
  RefreshCw,
  Sparkles,
  Info
} from 'lucide-react';
import { api, EmailRow, StatusResponse } from '../api/client';

interface ReviewDeskProps {
  onFeedbackSaved?: () => void;
  onOpenCandidate?: () => void;
  status?: StatusResponse | null;
}

export const ReviewDesk: React.FC<ReviewDeskProps> = ({ onFeedbackSaved, onOpenCandidate, status }) => {
  const reducedMotion = useMotionPreference();
  const [emails, setEmails] = useState<EmailRow[]>([]);
  const [selectedEmailId, setSelectedEmailId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState('All categories');
  const [priorityFilter, setPriorityFilter] = useState('All priorities');
  const [order, setOrder] = useState('Lowest confidence first');
  const [queueView, setQueueView] = useState<'all' | 'review' | 'resolved'>('all');
  
  // Feedback draft and save state
  const [drafts, setDrafts] = useState<Record<number, { category: string; priority: string }>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccessNotice, setSaveSuccessNotice] = useState<string | null>(null);
  const [saveErrorNotice, setSaveErrorNotice] = useState<string | null>(null);
  const [demoNotice, setDemoNotice] = useState<string | null>(null);

  // Mobile view state: list vs detail
  const [mobileDetailOpen, setMobileDetailOpen] = useState(false);
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const detailHeadingRef = useRef<HTMLHeadingElement>(null);
  const rowRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const focusDetail = useRef(false);
  const loadSequence = useRef(0);
  const returnFrame = useRef<number>();
  const saveButtonRef = useRef<HTMLButtonElement>(null);
  const saveFocusFrame = useRef<number>();

  useEffect(() => () => {
    if (returnFrame.current !== undefined) cancelAnimationFrame(returnFrame.current);
    if (saveFocusFrame.current !== undefined) cancelAnimationFrame(saveFocusFrame.current);
    loadSequence.current++;
  }, []);

  const selectEmail = (emailId: number) => {
    focusDetail.current = window.matchMedia('(max-width: 1023px)').matches;
    setSelectedEmailId(emailId);
    setMobileDetailOpen(true);
  };

  useEffect(() => {
    if (!focusDetail.current || !mobileDetailOpen) return;
    focusDetail.current = false;
    detailHeadingRef.current?.focus();
  }, [mobileDetailOpen, selectedEmailId]);

  const returnToList = () => {
    setMobileDetailOpen(false);
    if (returnFrame.current !== undefined) cancelAnimationFrame(returnFrame.current);
    returnFrame.current = requestAnimationFrame(() => {
      if (selectedEmailId) rowRefs.current[selectedEmailId]?.focus();
    });
  };

  const loadEmails = async () => {
    const sequence = ++loadSequence.current;
    setIsLoading(true);
    try {
      const res = await api.getInbox({
        include_confident: true,
        order,
        category: categoryFilter,
        priority: priorityFilter,
        unresolved: queueView === 'review',
      });
      if (sequence !== loadSequence.current) return;
      setLoadError(null);
      // Inbox responses expose the original prediction as category/priority.
      // Keep the API contract intact and normalize only the reading view.
      const rows = res.rows.map((row) => {
        const original = row as EmailRow & { category?: string; priority?: string };
        return {
          ...row,
          predicted_category: row.predicted_category ?? original.category ?? 'Unavailable',
          predicted_priority: row.predicted_priority ?? original.priority ?? 'Unavailable',
          entities: row.entities?.map((entity) => {
            const stored = entity as typeof entity & { entity_type?: string; entity_value?: string; source_phrase?: string };
            return {
              ...entity,
              type: entity.type ?? stored.entity_type ?? 'Unavailable',
              value: entity.value ?? stored.entity_value ?? 'Unavailable',
              raw_phrase: entity.raw_phrase ?? stored.source_phrase ?? '',
            };
          }),
        };
      });
      const visibleRows = queueView === 'review'
        ? rows.filter((row) => row.status === 'needs_review' && !row.feedback_id)
        : queueView === 'resolved'
          ? rows.filter((row) => row.status !== 'needs_review' || Boolean(row.feedback_id))
          : rows;
      setEmails(visibleRows);

      // Initialize drafts for each row
      const initialDrafts: Record<number, { category: string; priority: string }> = {};
      visibleRows.forEach((r) => {
        initialDrafts[r.id] = {
          category: r.effective_category,
          priority: r.effective_priority,
        };
      });
      setDrafts((previous) => ({ ...initialDrafts, ...previous }));

      // Auto-select first email if none selected or if selected is no longer in list
      if (visibleRows.length > 0) {
        if (!selectedEmailId || !visibleRows.some((r) => r.id === selectedEmailId)) {
          setSelectedEmailId(visibleRows[0].id);
        }
      } else {
        setSelectedEmailId(null);
      }
    } catch (err) {
      if (sequence !== loadSequence.current) return;
      console.error('Failed to load inbox emails', err);
      setLoadError(err instanceof Error ? err.message : 'Inbox could not be loaded.');
    } finally {
      if (sequence === loadSequence.current) setIsLoading(false);
    }
  };

  useEffect(() => {
    loadEmails();
  }, [categoryFilter, priorityFilter, order, queueView]);

  const handleImportDemo = async () => {
    setIsLoading(true);
    setDemoNotice(null);
    try {
      const res = await api.importDemo('demo_feedback.csv');
      setDemoNotice(`Successfully imported ${res.imported} demo emails (${res.duplicates} duplicates skipped).`);
      await loadEmails();
      if (onFeedbackSaved) onFeedbackSaved();
    } catch (err: any) {
      setDemoNotice(`Import failed: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUploadFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setIsLoading(true);
    setDemoNotice(null);
    try {
      const res = await api.uploadEmailFile(file);
      const { result } = res;
      setDemoNotice(`Imported ${result.new} new ${result.new === 1 ? 'message' : 'messages'} from ${file.name}; ${result.duplicates} duplicate${result.duplicates === 1 ? '' : 's'} skipped${result.warnings ? `, ${result.warnings} parser warning${result.warnings === 1 ? '' : 's'}` : ''}.`);
      await loadEmails();
      onFeedbackSaved?.();
    } catch (err) {
      setDemoNotice(`Import failed: ${err instanceof Error ? err.message : 'The file could not be imported.'}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveCorrection = async (emailId: number) => {
    const draft = drafts[emailId];
    if (!draft) return;
    const restoreFocus = document.activeElement === saveButtonRef.current;
    setIsSaving(true);
    setSaveSuccessNotice(null);
    setSaveErrorNotice(null);
    try {
      const res = await api.saveFeedback(emailId, draft.category, draft.priority);
      const isRev = res.is_revision ? 'Revision updated' : 'Correction saved';
      setSaveSuccessNotice(`${isRev} for message #${emailId}. Stored in feedback ledger for candidate training.`);
      await loadEmails();
      if (onFeedbackSaved) onFeedbackSaved();
    } catch (err: any) {
      console.error('Failed to save correction', err);
      setSaveErrorNotice(err.message || 'Correction could not be saved.');
    } finally {
      setIsSaving(false);
      if (restoreFocus) {
        saveFocusFrame.current = requestAnimationFrame(() => {
          if (document.activeElement === document.body && saveButtonRef.current?.dataset.emailId === String(emailId)) {
            saveButtonRef.current.focus({ preventScroll: true });
          }
        });
      }
    }
  };

  const selectedEmail = emails.find((e) => e.id === selectedEmailId) || null;
  const currentDraft = selectedEmailId ? drafts[selectedEmailId] : null;

  const categories = status?.categories || ['job opportunities', 'university', 'bills', 'promotions', 'spam'];
  const priorities = status?.priorities || ['high', 'normal', 'low'];

  return (
    <div className={`workspace-review-desk space-y-6 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6${mobileDetailOpen ? " is-reading" : ""}`}>
      
      {/* Editorial Section Header */}
      <div className="workspace-review-heading flex flex-col md:flex-row md:items-end justify-between gap-4 pb-4 border-b border-paper-border">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-[10px] tracking-wider uppercase text-rust font-semibold">
            YOUR DAILY CORRESPONDENCE
            </span>
            <span className="text-paper-border">·</span>
            <span className="font-mono text-[10px] text-ink-muted">
            REVIEW DESK
            </span>
          </div>
          <h2 className="font-serif text-2xl sm:text-3xl font-bold text-ink">
            Your review desk.
          </h2>
          <p className="text-xs text-ink-muted mt-1 max-w-2xl leading-relaxed">
            Read, confirm, or correct. Every saved decision is useful feedback for your next model.
          </p>
        </div>

        {/* Global Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5">
          <input
            ref={uploadInputRef}
            className="sr-only"
            tabIndex={-1}
            type="file"
            accept=".eml,.mbox,.csv,message/rfc822,text/csv"
            aria-label="Choose email file to import"
            onChange={handleUploadFile}
          />
          <button
            type="button"
            onClick={() => uploadInputRef.current?.click()}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-sans font-medium bg-paper-sheet hover:bg-paper-subtle border border-paper-border text-ink shadow-paper-sm transition-colors cursor-pointer disabled:opacity-50"
          >
            <Upload className="w-3.5 h-3.5 text-rust" />
            <span>Import email file</span>
          </button>
          <button
            onClick={handleImportDemo}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-sans font-medium bg-paper-sheet hover:bg-paper-subtle border border-paper-border text-ink shadow-paper-sm transition-colors cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-rust ${isLoading ? 'animate-spin' : ''}`} />
            <span>Try 5 demo emails</span>
          </button>

          <a
            href="/api/export/csv"
            download="inboxlearn_export.csv"
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-sans font-medium bg-paper-sheet hover:bg-paper-subtle border border-paper-border text-ink shadow-paper-sm transition-colors cursor-pointer"
          >
            <Download className="w-3.5 h-3.5 text-ink-muted" />
            <span>Export CSV</span>
          </a>
        </div>
      </div>

      {/* Notifications */}
      {demoNotice && (
        <div className="p-3 bg-paper-sheet border-l-3 border-rust border-y border-r border-paper-border text-xs text-ink flex items-center justify-between shadow-paper-sm">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-rust flex-shrink-0" />
            <span>{demoNotice}</span>
          </div>
          <button onClick={() => setDemoNotice(null)} className="text-ink-muted hover:text-ink text-xs underline cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {saveSuccessNotice && (
        <motion.div role="status" initial={{ opacity: reducedMotion ? 1 : .4 }} animate={{ opacity: 1 }} className="desk-save-notice">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-700 flex-shrink-0" />
            <span>{saveSuccessNotice}</span>
          </div>
          <button onClick={() => setSaveSuccessNotice(null)} className="text-emerald-800 hover:text-emerald-950 text-xs underline cursor-pointer">
            Dismiss
          </button>
          <div className="desk-followup"><span>Keep reviewing, or see what your feedback could change.</span>{emails.some(e => e.id !== selectedEmailId && !e.feedback_id) && <button type="button" onClick={() => { const next = emails.find(e => e.id !== selectedEmailId && !e.feedback_id); if (next) selectEmail(next.id); }}>Next unreviewed message <ChevronRight size={15} aria-hidden="true" /></button>}<button type="button" onClick={onOpenCandidate}>Compare a candidate <ChevronRight size={15} aria-hidden="true" /></button></div>
        </motion.div>
      )}

      {saveErrorNotice && (
        <div className="workspace-inline-error" role="alert">
          <span>{saveErrorNotice}</span>
          <button onClick={() => setSaveErrorNotice(null)}>Dismiss</button>
        </div>
      )}

      {loadError && (
        <div className="workspace-inline-error" role="alert">
          <span><strong>Inbox unavailable.</strong> {loadError}</span>
          <button type="button" onClick={loadEmails} disabled={isLoading}>{isLoading ? 'Retrying…' : 'Retry'}</button>
        </div>
      )}

      {/* Filter & Sort Bar */}
      <div className="workspace-inbox-controls">
        <div className="workspace-queue-tabs" role="group" aria-label="Filter messages by review status">
          <button type="button" aria-pressed={queueView === 'all'} className={queueView === 'all' ? 'is-active' : ''} onClick={() => setQueueView('all')}>
            All <span>{status?.metrics.emails_stored ?? '—'}</span>
          </button>
          <button type="button" aria-pressed={queueView === 'review'} className={queueView === 'review' ? 'is-active' : ''} onClick={() => setQueueView('review')}>
            Needs review <span>{status?.metrics.pending_reviews ?? '—'}</span>
          </button>
          <button type="button" aria-pressed={queueView === 'resolved'} className={queueView === 'resolved' ? 'is-active' : ''} onClick={() => setQueueView('resolved')}>
            Resolved <span>{status ? Math.max(0, status.metrics.emails_stored - status.metrics.pending_reviews) : '—'}</span>
          </button>
        </div>
        <div className="workspace-inbox-filters">
        <div className="flex flex-wrap items-center gap-3">
          {/* Order Selector */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="inbox-order" className="text-ink-faint font-mono text-[11px]">Order</label>
            <select
              id="inbox-order"
              value={order}
              onChange={(e) => setOrder(e.target.value)}
              className="bg-paper-canvas border border-paper-border px-2 py-1 text-xs text-ink focus:outline-none focus:border-rust"
            >
              <option value="Lowest confidence first">Lowest confidence first (Triage)</option>
              <option value="Newest first">Most recent</option>
            </select>
          </div>

          {/* Category Filter */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="inbox-category" className="text-ink-faint font-mono text-[11px]">Category</label>
            <select
              id="inbox-category"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="bg-paper-canvas border border-paper-border px-2 py-1 text-xs text-ink focus:outline-none focus:border-rust"
            >
              <option value="All categories">All categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          {/* Priority Filter */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="inbox-priority" className="text-ink-faint font-mono text-[11px]">Priority</label>
            <select
              id="inbox-priority"
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="bg-paper-canvas border border-paper-border px-2 py-1 text-xs text-ink focus:outline-none focus:border-rust"
            >
              <option value="All priorities">All priorities</option>
              {priorities.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>

        </div>

        <div className="workspace-inbox-count" aria-live="polite">
          {loadError ? 'Message count unavailable' : isLoading ? 'Refreshing messages…' : <>Showing <strong>{emails.length}</strong> message{emails.length === 1 ? '' : 's'}</>}
        </div>
        </div>
      </div>

      {/* Main Two-Column Triage Console (Desktop & Mobile) */}
      <div className="workspace-inbox-grid grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* ========================================================================= */}
        {/* LEFT COLUMN: EMAIL TRIAGE LIST TABLE (7 Cols on LG)                      */}
        {/* ========================================================================= */}
        <div className={`lg:col-span-6 space-y-3 ${mobileDetailOpen ? 'hidden lg:block' : 'block'}`}>
          <div className="workspace-message-list">
            
            {/* Table Header Strip */}
            <div className="workspace-message-list-heading">
              <div className="flex items-center gap-2">
                <span>Inbox Messages</span>
                <span className="text-ink-muted font-normal">{loadError ? '(unavailable)' : isLoading ? '(loading)' : `(${emails.length})`}</span>
              </div>
              <span className="text-[10px] text-ink-faint lowercase tracking-normal">click to inspect & confirm</span>
            </div>

            {/* Empty State */}
            {loadError && emails.length === 0 && <div className="workspace-empty-state">Messages could not be reached. Retry the inbox request above.</div>}
            {loadError && emails.length > 0 && <p className="workspace-empty-state">Showing the last loaded messages. Refresh failed; labels may be out of date.</p>}
            {isLoading && emails.length === 0 && (
              <div className="workspace-empty-state" role="status">Loading messages from the local inbox…</div>
            )}

            {emails.length === 0 && !isLoading && !loadError && (
              <div className="p-8 text-center space-y-3">
                <Inbox className="w-8 h-8 text-ink-faint mx-auto" />
                <p className="font-serif text-lg text-ink font-semibold">{status?.metrics.emails_stored === 0 ? 'Your desk is ready for its first message.' : 'No messages in this view.'}</p>
                <p className="text-xs text-ink-muted max-w-md mx-auto">
                  {queueView === 'review'
                    ? 'No uncertain messages are waiting for a human decision.'
                    : queueView === 'resolved'
                      ? 'No classified or corrected messages in this view yet.'
                      : status?.metrics.emails_stored === 0 ? 'Import an email file above, or get a feel for the workflow with five synthetic emails.' : 'Try another category or priority to find the message you need.'}
                </p>
                <button
                  onClick={handleImportDemo}
                  className="mt-2 inline-flex items-center gap-2 px-4 py-2 text-xs font-sans font-medium bg-rust text-white hover:bg-rust-hover transition-colors cursor-pointer"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Explore with synthetic emails</span>
                </button>
              </div>
            )}

            {/* Email Rows */}
            <div className="divide-y divide-paper-border max-h-[640px] overflow-y-auto">
              {emails.map((email) => {
                const isSelected = email.id === selectedEmailId;
                const isNeedsReview = email.status === 'needs_review';
                const isCorrected = email.status === 'corrected';

                return (
                  <div
                    key={email.id}
                    ref={(element) => { rowRefs.current[email.id] = element; }}
                    onClick={() => selectEmail(email.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        selectEmail(email.id);
                      }
                    }}
                    tabIndex={0}
                    role="button"
                    aria-pressed={isSelected}
                    className={`workspace-message-row p-3.5 text-left transition-colors cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-rust ${
                      isSelected
                        ? 'bg-paper-canvas border-l-4 border-l-rust border-y border-y-paper-border'
                        : 'hover:bg-[#fbfaf8] border-l-4 border-l-transparent'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      {/* Left: Status tag + ID */}
                      <div className="flex items-center gap-2 flex-wrap">
                        {isNeedsReview && (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-mono font-bold uppercase bg-amber-100 text-amber-900 border border-amber-300">
                            <AlertCircle className="w-3 h-3 text-amber-700" />
                            <span>Needs Review</span>
                          </span>
                        )}
                        {isCorrected && (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-mono font-bold uppercase bg-emerald-100 text-emerald-900 border border-emerald-300">
                            <CheckCircle2 className="w-3 h-3 text-emerald-700" />
                            <span>Corrected</span>
                          </span>
                        )}
                        {!isNeedsReview && !isCorrected && (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-mono uppercase bg-paper-subtle text-ink-muted border border-paper-border">
                            <span>Classified</span>
                          </span>
                        )}

                        <span className="font-mono text-[10px] text-ink-faint">
                          #{email.id}
                        </span>
                      </div>

                      {/* Right: Confidence Score Indicators */}
                      <div className="workspace-row-confidence flex items-center gap-2 text-[11px] font-mono text-ink-muted">
                        <span>
                          Cat: <strong className={email.category_confidence < 0.70 ? 'text-amber-800' : 'text-ink'}>
                            {(email.category_confidence * 100).toFixed(0)}%
                          </strong>
                        </span>
                        <span className="text-paper-border">·</span>
                        <span>
                          Pri: <strong className={email.priority_confidence < 0.70 ? 'text-amber-800' : 'text-ink'}>
                            {(email.priority_confidence * 100).toFixed(0)}%
                          </strong>
                        </span>
                      </div>
                    </div>

                    <div className="workspace-confidence-meter" aria-hidden="true">
                      <i><b style={{ width: `${Math.max(0, Math.min(100, email.category_confidence * 100))}%` }} /></i>
                      <i><b style={{ width: `${Math.max(0, Math.min(100, email.priority_confidence * 100))}%` }} /></i>
                    </div>

                    {/* Subject Line */}
                    <div className="mt-1.5 font-sans font-semibold text-sm text-ink line-clamp-1">
                      {email.subject}
                    </div>

                    {/* Sender & Preview snippet */}
                    <div className="mt-0.5 flex items-center justify-between text-xs text-ink-muted">
                      <span className="truncate max-w-[280px]">From: {email.sender || 'unknown'}</span>
                      <span className="text-[10px] font-mono uppercase text-ink-faint">{email.source}</span>
                    </div>

                    {/* Model Suggestions / Current Labels */}
                    <div className="mt-2.5 pt-2 border-t border-dashed border-paper-border flex flex-wrap items-center justify-between gap-2 text-xs">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] font-mono uppercase text-ink-faint">{email.feedback_id ? 'Human:' : 'Model:'}</span>
                        <span className="px-1.5 py-0.5 bg-paper-sheet border border-paper-border font-mono text-[11px] text-ink font-medium">
                          {email.effective_category}
                        </span>
                        <span className="px-1.5 py-0.5 bg-paper-sheet border border-paper-border font-mono text-[11px] text-ink font-medium">
                          {email.effective_priority}
                        </span>
                      </div>

                      <div className="text-[11px] text-rust flex items-center gap-1 font-sans">
                        <span>Inspect & confirm</span>
                        <ChevronRight className="w-3 h-3" />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* RIGHT COLUMN: READING PANE & HUMAN CONFIRMATION DESK (5 Cols on LG)      */}
        {/* ========================================================================= */}
        <div className={`lg:col-span-6 space-y-4 ${mobileDetailOpen ? 'block' : 'hidden lg:block'}`}>
          {selectedEmail ? (
            <div className="workspace-reading-pane bg-paper-sheet border border-paper-border shadow-paper p-5 space-y-5">
              
              {/* Mobile Back Button */}
              <div className="lg:hidden pb-3 border-b border-paper-border">
                <button
                  onClick={returnToList}
                  className="inline-flex items-center gap-1 text-xs font-mono text-rust hover:underline cursor-pointer"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Back to Message List</span>
                </button>
              </div>

              {/* Message Header & Meta */}
              <div className="workspace-message-meta space-y-2 pb-4 border-b border-paper-border">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-ink-muted">
                    MESSAGE #{selectedEmail.id}
                  </span>
                  
                  {/* Status Badge */}
                  {selectedEmail.status === 'needs_review' && (
                    <span className="px-2 py-0.5 bg-amber-100 text-amber-900 border border-amber-300 font-mono text-[10px] font-bold uppercase">
                      Needs Review
                    </span>
                  )}
                  {selectedEmail.status === 'corrected' && (
                    <span className="px-2 py-0.5 bg-emerald-100 text-emerald-900 border border-emerald-300 font-mono text-[10px] font-bold uppercase">
                      Human Feedback Saved
                    </span>
                  )}
                  {selectedEmail.status === 'classified' && (
                    <span className="px-2 py-0.5 bg-paper-subtle text-ink-muted border border-paper-border font-mono text-[10px] uppercase">
                      Model Confident
                    </span>
                  )}
                </div>

                <h3 ref={detailHeadingRef} tabIndex={-1} className="font-serif text-xl sm:text-2xl font-bold text-ink leading-snug">
                  {selectedEmail.subject}
                </h3>

                <div className="text-xs text-ink-muted space-y-0.5 font-sans pt-1">
                  <div>
                    <span className="font-semibold text-ink">From:</span> {selectedEmail.sender || 'Unknown Sender'}
                  </div>
                  {selectedEmail.date_header && (
                    <div>
                      <span className="font-semibold text-ink">Date:</span> {selectedEmail.date_header}
                    </div>
                  )}
                  <div>
                    <span className="font-semibold text-ink">Source:</span> {selectedEmail.source} ({selectedEmail.source_type})
                  </div>
                </div>
              </div>

              {/* Email Body Content */}
              <div className="workspace-message-body space-y-2">
                <span className="text-[10px] font-mono uppercase text-ink-faint block">
                  THE MESSAGE
                </span>
                <div className="workspace-message-copy p-3.5 bg-paper-canvas border border-paper-border text-xs sm:text-sm text-ink-light font-sans whitespace-pre-wrap leading-relaxed select-text max-h-60 overflow-y-auto">
                  {selectedEmail.body}
                </div>
              </div>

              {/* Extracted Entities (Dates, Money, Calendar) */}
              {selectedEmail.entities && selectedEmail.entities.length > 0 && (
                <div className="workspace-extracted-entities p-3 bg-paper-subtle border border-paper-border space-y-1.5 text-xs">
                  <span className="text-[10px] font-mono uppercase text-ink font-semibold flex items-center gap-1.5">
                    <Tag className="w-3 h-3 text-rust" />
                    <span>Dates &amp; details found</span>
                  </span>
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {selectedEmail.entities.map((ent, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-0.5 bg-paper-sheet border border-paper-border font-mono text-[11px] text-ink"
                      >
                        <strong className="text-rust">{ent.type}:</strong> {ent.value}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Model Suggestion Rationale */}
              <div className="workspace-model-suggestion p-3 bg-paper-canvas border border-paper-border text-xs space-y-1.5">
                <div className="flex items-center justify-between text-[11px] font-mono">
                  <span className="text-ink-muted">MODEL SUGGESTIONS · VERSION #{selectedEmail.model_version_id}</span>
                  <span className="text-ink-faint">review thresholds {status ? `${Math.round(status.thresholds.category * 100)}% / ${Math.round(status.thresholds.priority * 100)}%` : 'set by local API'}</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs font-sans">
                  <div>
                    <span className="text-ink-faint text-[10px] block">CATEGORY:</span>
                    <strong className="font-mono text-ink">{selectedEmail.predicted_category}</strong>
                    <span className={`block font-mono text-[11px] ${selectedEmail.category_confidence < 0.70 ? 'text-amber-800 font-bold' : 'text-ink-muted'}`}>
                      {(selectedEmail.category_confidence * 100).toFixed(1)}% confidence
                    </span>
                  </div>
                  <div>
                    <span className="text-ink-faint text-[10px] block">PRIORITY:</span>
                    <strong className="font-mono text-ink">{selectedEmail.predicted_priority}</strong>
                    <span className={`block font-mono text-[11px] ${selectedEmail.priority_confidence < 0.70 ? 'text-amber-800 font-bold' : 'text-ink-muted'}`}>
                      {(selectedEmail.priority_confidence * 100).toFixed(1)}% confidence
                    </span>
                  </div>
                </div>
                {selectedEmail.routing_reason && (
                  <p className="text-[11px] text-ink-muted pt-1 border-t border-paper-border italic">
                    Reason: {selectedEmail.routing_reason}
                  </p>
                )}
              </div>

              {/* ================================================================= */}
              {/* HUMAN CONFIRMATION & FEEDBACK DESK CONTROLS                      */}
              {/* ================================================================= */}
              <div className="workspace-correction-panel p-4 bg-paper-subtle border-2 border-ink space-y-3.5">
                {selectedEmail.feedback_id && <p className="workspace-saved-labels">Saved human labels: <strong>{selectedEmail.effective_category} / {selectedEmail.effective_priority}</strong></p>}
                <div className="flex items-center justify-between pb-2 border-b border-paper-border">
                  <span className="font-serif text-sm font-bold text-ink">
                    Your judgment
                  </span>
                  <span className="text-[10px] font-mono text-rust uppercase font-semibold">
                    {selectedEmail.status === 'corrected' ? 'Revising Feedback' : 'Confirming Label'}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {/* Category Selection */}
                  <div className="space-y-1">
                    <label htmlFor={`category-${selectedEmail.id}`} className="text-[10px] font-mono uppercase text-ink-muted block font-semibold">
                      Confirmed Category:
                    </label>
                    <select
                      id={`category-${selectedEmail.id}`}
                      value={currentDraft?.category || selectedEmail.effective_category}
                      onChange={(e) => {
                        const val = e.target.value;
                        setDrafts((prev) => ({
                          ...prev,
                          [selectedEmail.id]: {
                            ...prev[selectedEmail.id],
                            category: val,
                            priority: prev[selectedEmail.id]?.priority || selectedEmail.effective_priority,
                          },
                        }));
                      }}
                      className="w-full bg-paper-sheet border border-paper-border px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:border-rust"
                    >
                      {categories.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>

                  {/* Priority Selection */}
                  <div className="space-y-1">
                    <label htmlFor={`priority-${selectedEmail.id}`} className="text-[10px] font-mono uppercase text-ink-muted block font-semibold">
                      Confirmed Priority:
                    </label>
                    <select
                      id={`priority-${selectedEmail.id}`}
                      value={currentDraft?.priority || selectedEmail.effective_priority}
                      onChange={(e) => {
                        const val = e.target.value;
                        setDrafts((prev) => ({
                          ...prev,
                          [selectedEmail.id]: {
                            ...prev[selectedEmail.id],
                            priority: val,
                            category: prev[selectedEmail.id]?.category || selectedEmail.effective_category,
                          },
                        }));
                      }}
                      className="w-full bg-paper-sheet border border-paper-border px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:border-rust"
                    >
                      {priorities.map((p) => (
                        <option key={p} value={p}>{p}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Save Feedback Action Button */}
                <div className="pt-1">
                  <button
                    ref={saveButtonRef}
                    data-email-id={selectedEmail.id}
                    onClick={() => handleSaveCorrection(selectedEmail.id)}
                    disabled={isSaving}
                    className="w-full py-2.5 px-4 text-xs font-sans font-semibold text-white bg-rust hover:bg-rust-hover transition-colors flex items-center justify-center gap-2 cursor-pointer shadow-paper-sm disabled:opacity-50"
                  >
                    <Check className="w-4 h-4" />
                    <span>
                      {isSaving ? 'Saving to Feedback Ledger...' : 'Save my review'}
                    </span>
                  </button>
                  <p className="text-[10px] text-ink-faint text-center mt-1.5">
                    Your review is saved as feedback. Prepare a candidate when you’re ready to compare what changes.
                  </p>
                </div>
              </div>

            </div>
          ) : (
            <div className="p-8 bg-paper-sheet border border-paper-border text-center space-y-2 text-ink-muted">
              <FileText className="w-8 h-8 text-ink-faint mx-auto" />
              <p className="font-serif text-base font-semibold text-ink">No email selected</p>
              <p className="text-xs">Select an email from the left triage list to read and confirm its labels.</p>
            </div>
          )}
        </div>

      </div>

    </div>
  );
};
