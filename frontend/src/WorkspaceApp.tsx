import React, { useState, useEffect } from 'react';
import { api, StatusResponse } from './api/client';
import { Navbar, TabId } from './components/Navbar';
import { ReviewDesk } from './components/ReviewDesk';
import { CandidateDiffGate } from './components/CandidateDiffGate';
import { InferenceStudio } from './components/InferenceStudio';
import { VersionLedger } from './components/VersionLedger';
import { PipelineLifecycle } from './components/PipelineLifecycle';

/**
 * WorkspaceApp — The full operational application.
 * Extracted from the original App component to live at /app route.
 * All triage, inference, candidate gating, and model ledger functionality preserved.
 */
export function WorkspaceApp() {
  const [activeTab, setActiveTab] = useState<TabId>('inbox');
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [statusError, setStatusError] = useState<string | null>(null);

  const refreshStatus = async () => {
    setStatusError(null);
    try {
      const data = await api.getStatus();
      setStatus(data);
    } catch (err) {
      setStatusError(err instanceof Error ? err.message : 'The local API could not be reached.');
    } finally {
      setIsInitializing(false);
    }
  };

  useEffect(() => {
    refreshStatus();
  }, []);

  return (
    <div className="workspace-shell min-h-screen bg-paper text-ink font-sans selection:bg-rust-tint selection:text-rust">
      <a className="workspace-skip-link" href="#main-content">Skip to workspace</a>

      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        status={status}
        statusLoading={isInitializing}
        statusError={statusError}
      />

      <div className="workspace-content">
        {statusError && (
          <div className="workspace-connection" role="status" aria-live="polite">
            <span><strong>Local API unavailable.</strong> {statusError}</span>
            <button type="button" onClick={refreshStatus}>Retry connection</button>
          </div>
        )}

        <main className="workspace-main flex-1 w-full pb-12" id="main-content" tabIndex={-1}>
        {activeTab === 'inbox' && (
            <div key="inbox">
              <ReviewDesk 
                onFeedbackSaved={refreshStatus} 
                status={status}
              />
            </div>
        )}

        {activeTab === 'candidate' && (
            <div key="candidate">
              {status ? (
                <CandidateDiffGate
                  activeVersionId={status.active_version.id}
                  activeLabel={status.active_version.label}
                  candidateInfo={status.candidate}
                  onRefresh={refreshStatus}
                />
              ) : (
                <div className="workspace-unavailable" role="status">
                  <h2 className="font-serif">Candidate preparation</h2>
                  <p>{isInitializing ? 'Connecting to the local model registry…' : 'The model registry is unavailable until the local API reconnects.'}</p>
                </div>
              )}
            </div>
        )}

        {activeTab === 'probe' && (
            <div key="probe">
              <InferenceStudio />
            </div>
        )}

        {activeTab === 'ledger' && (
            <div key="ledger">
              <VersionLedger onRollback={refreshStatus} />
            </div>
        )}

        {activeTab === 'architecture' && (
            <div key="architecture">
              <PipelineLifecycle />
            </div>
        )}
        </main>

      {/* Colophon Footer */}
        <footer className="border-t-2 border-ink bg-paper-subtle py-6 px-4 sm:px-6 lg:px-8 text-xs font-mono text-ink-muted">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-serif font-bold text-ink text-sm">InboxLearn</span>
            <span>·</span>
            <span>Local email triage</span>
            <span>·</span>
            <span>Human-reviewed learning loop</span>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-[11px] text-ink-faint">
            <span>SQLite feedback ledger</span>
            <span>·</span>
            <span>Evaluated model versions</span>
            <span>·</span>
            <span>Reversible activation</span>
          </div>
        </div>
        </footer>
      </div>
    </div>
  );
}

export default WorkspaceApp;
