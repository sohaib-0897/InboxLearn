import React, { lazy, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';

/* Lazy-load both pages for code splitting */
const LandingPage = lazy(() => import('./LandingPage'));
const WorkspaceApp = lazy(() => import('./WorkspaceApp'));

/**
 * App — Top-level router.
 *   /     → Polished landing page with 3D hero and product overview
 *   /app  → Full operational workspace (triage, inference, candidate gate, etc.)
 */
export function App() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-paper flex items-center justify-center">
          <div className="text-center">
            <div className="font-serif text-2xl font-bold text-ink tracking-tight">InboxLearn</div>
            <div className="mt-2 text-xs font-mono text-ink-faint">Loading…</div>
          </div>
        </div>
      }
    >
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/app" element={<WorkspaceApp />} />
      </Routes>
    </Suspense>
  );
}

export default App;
