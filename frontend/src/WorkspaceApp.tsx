import React, { useState, useEffect } from 'react';
import './redesign.css';
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
      setStatus(null);
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
        <header className="desk-topbar"><span>Your workspace <span aria-hidden="true">/</span> <strong>{{inbox: 'Inbox & review', candidate: 'Candidate & evaluation', probe: 'Inference probe', ledger: 'Version history', architecture: 'How it works'}[activeTab]}</strong></span><span className="desk-topbar-status">{status ? `${status.metrics.available_feedback} saved feedback ${status.metrics.available_feedback === 1 ? 'record' : 'records'}` : isInitializing ? 'Connecting…' : 'Connection unavailable'}</span></header>
        {statusError && (
          <div className="workspace-connection" role="status" aria-live="polite">
            <span><strong>Local API unavailable.</strong> {statusError}</span>
            <button type="button" onClick={refreshStatus}>Retry connection</button>
          </div>
        )}

        <main className="workspace-main flex-1 w-full pb-12" id="main-content" tabIndex={-1}>
        <h1 className="sr-only">InboxLearn workspace</h1>
        {activeTab === 'inbox' && (
            <div key="inbox">
              <ReviewDesk 
                onFeedbackSaved={refreshStatus}
                onOpenCandidate={() => { setActiveTab('candidate'); document.getElementById('main-content')?.focus(); }}
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

        <footer className="desk-footer"><span>InboxLearn<span className="brand-period">.</span></span><p>Human judgment, at the heart of the loop.</p><span>Review · Evaluate · Decide</span></footer>
      </div>
    </div>
  );
}

export default WorkspaceApp;
