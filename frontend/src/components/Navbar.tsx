import React from 'react';
import { Link } from 'react-router-dom';
import { Inbox, GitCompare, History, Terminal, BookOpen, ArrowUpRight } from 'lucide-react';
import { StatusResponse } from '../api/client';

export type TabId = 'inbox' | 'candidate' | 'probe' | 'ledger' | 'architecture';

interface NavbarProps {
  activeTab: TabId;
  setActiveTab: (tab: TabId) => void;
  status: StatusResponse | null;
  statusLoading: boolean;
  statusError: string | null;
}

const NAV_ITEMS: { id: TabId; number: string; label: string; icon: React.FC<{ className?: string }> }[] = [
  { id: 'inbox', number: '01', label: 'Inbox & review', icon: Inbox },
  { id: 'candidate', number: '02', label: 'Candidate & gate', icon: GitCompare },
  { id: 'probe', number: '03', label: 'Inference probe', icon: Terminal },
  { id: 'ledger', number: '04', label: 'Version ledger', icon: History },
  { id: 'architecture', number: '05', label: 'How it works', icon: BookOpen },
];

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab, status, statusLoading, statusError }) => {
  const activeModel = status?.active_version;
  const metrics = status?.metrics;
  const connectedLabel = status ? 'API connected' : statusLoading ? 'Connecting to local API' : 'Local API unavailable';

  return (
    <aside className="workspace-rail" aria-label="Workspace navigation">
      <div className="workspace-rail-top">
        <Link to="/" className="workspace-brand" aria-label="InboxLearn home">
          <span className="workspace-brand-mark" aria-hidden="true"><Inbox /></span>
          <span>InboxLearn</span>
        </Link>
        <p className="workspace-rail-caption">LOCAL EMAIL TRIAGE<br />HUMAN REVIEW · MODEL CONTROL</p>
      </div>

      <nav className="workspace-nav" aria-label="Workspace sections">
        <span className="workspace-nav-label">WORKSPACE</span>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setActiveTab(item.id)}
              aria-current={isActive ? 'page' : undefined}
              className={`workspace-nav-item${isActive ? ' is-active' : ''}`}
            >
              <Icon aria-hidden="true" />
              <span>{item.label}</span>
              <small>{item.number}</small>
            </button>
          );
        })}
      </nav>

      <div className="workspace-rail-note" aria-hidden="true">
        <div className="workspace-rail-orbit"><span /><span /><i /></div>
        <p>Better inbox decisions,<br /><strong>smarter models.</strong></p>
        <span className="workspace-rail-note-index">A HUMAN-LED LEARNING LOOP</span>
      </div>

      <section className="workspace-model-status" aria-label="Live workspace status">
        <div className="workspace-model-status-heading">
          <span className={`workspace-connection-dot ${status ? 'is-connected' : statusError ? 'is-offline' : 'is-pending'}`} aria-hidden="true" />
          <span>{connectedLabel}</span>
        </div>
        <div className="workspace-model-line">
          <span>ACTIVE MODEL</span>
          <strong>{activeModel?.label ?? (statusLoading ? 'Connecting…' : 'Unavailable')}</strong>
        </div>
        <div className="workspace-model-counts">
          <div><span>INBOX</span><strong>{metrics?.emails_stored ?? '—'}</strong></div>
          <div><span>TO REVIEW</span><strong>{metrics?.pending_reviews ?? '—'}</strong></div>
        </div>
        <Link to="/" className="workspace-home-link">Back to overview <ArrowUpRight aria-hidden="true" /></Link>
      </section>
    </aside>
  );
};
