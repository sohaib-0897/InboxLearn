import React from 'react';
import { 
  ShieldCheck, 
  Cpu, 
  GitBranch, 
  FileCheck, 
  RotateCcw, 
  Lock, 
  Terminal, 
  CheckCircle2,
  AlertCircle,
  Database,
  Layers,
  ArrowRight
} from 'lucide-react';

const STAGES = [
  {
    step: '01',
    title: 'Intake & Boundary Sanitization',
    desc: 'RFC 822 / MIME parsing with strict 5MB EML / 20MB MBOX bounds and 10-level nesting limits. Strips HTML to plain text, neutralizes formula injection (=, +, -, @), and skips binary attachments.',
    tag: 'Boundary Security',
  },
  {
    step: '02',
    title: 'Stateless Hashing Vectorization',
    desc: 'Transforms text using HashingVectorizer(n_features=4096, ngram_range=(1,2)) with L2 normalization. Because hashing is purely mathematical and stateless, vocabulary drift is eliminated across retraining iterations.',
    tag: 'Stateless Projection',
  },
  {
    step: '03',
    title: 'Confidence-Threshold Routing',
    desc: 'Dual SGDClassifier solvers output uncalibrated log-loss estimates. Any prediction below category threshold (0.70) or priority threshold (0.70) is routed to the human Review Desk for verification.',
    tag: 'Human Triage',
  },
  {
    step: '04',
    title: 'Deduplicated Candidate Preparation',
    desc: 'Retraining occurs in an isolated write transaction. Requests are deduplicated in candidate_registry via compound key (parent_id, seed_hash, feedback_revision_ids, recipe_version).',
    tag: 'Safe Retraining',
  },
  {
    step: '05',
    title: 'Pre-Activation Prediction Diffing',
    desc: 'Operators inspect side-by-side prediction diffs across all stored emails. Training-set membership is explicitly marked so operators never confuse training memorization with generalization.',
    tag: 'Regression Prevention',
  },
  {
    step: '06',
    title: 'Evaluation Gate & Safe Rollback',
    desc: 'Activation strictly checks SQLite for a verified evaluation run matching the held-out dataset hash (demo_eval.csv). Safe IBL1 array serialization allows instantaneous bit-exact rollback to any prior version.',
    tag: 'Quality Enforcement',
  },
];

const ENGINEERING_GUARANTEES = [
  {
    problem: 'Silent Deployment Regressions',
    solution: 'Pre-activation prediction diffing across all inbox emails with explicit training-set membership markers before activating candidate models.',
  },
  {
    problem: 'Bypassing Quality Gates',
    solution: 'The Python service layer (InboxLearnService.activate) verifies held-out evaluation in SQLite before updating the active pointer.',
  },
  {
    problem: 'Arbitrary Code Execution via Deserialization',
    solution: 'Safe explicit IBL1 binary serialization replaces Python pickle. Weights are strictly validated float64 arrays with SHA-256 integrity digests.',
  },
  {
    problem: 'Train / Test Data Leakage',
    solution: 'Evaluation routines enforce assert_split_isolated(), normalizing text (NFKC, case-folding, whitespace collapsing) and asserting zero split overlap.',
  },
  {
    problem: 'Vocabulary Synchronization Drift',
    solution: 'Stateless 4,096-dimensional hashing vectorization guarantees identical feature projection without mutable dictionary files.',
  },
  {
    problem: 'Feedback Revision Stale Gradients',
    solution: 'When an operator edits an existing feedback record, the system detects the revision and triggers a clean rebuild from baseline seed plus latest corrections.',
  },
];

export const PipelineLifecycle: React.FC = () => {
  return (
    <div className="space-y-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-4 border-b border-paper-border">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-[10px] tracking-wider uppercase text-rust font-semibold">
              05 SYSTEM ARCHITECTURE
            </span>
            <span className="text-paper-border">·</span>
            <span className="font-mono text-[10px] text-ink-muted">
              SYSTEM GUARANTEES & CONTINUOUS LEARNING
            </span>
          </div>
          <h2 className="font-serif text-2xl sm:text-3xl font-bold text-ink">
            Architecture & Engineering Principles
          </h2>
          <p className="text-xs text-ink-muted mt-1 max-w-2xl leading-relaxed">
            InboxLearn runs entirely on local hardware with zero external cloud dependencies. Below is the 6-stage lifecycle and the explicit guarantees that ensure reliability, data isolation, and safety.
          </p>
        </div>

        <div className="font-mono text-xs text-ink-muted bg-paper-sheet border border-paper-border px-3 py-2 shadow-paper-sm">
          <span>Python 3.12 · scikit-learn · SQLite · FastAPI</span>
        </div>
      </div>

      {/* 6-Stage Lifecycle Grid */}
      <div className="space-y-3">
        <h3 className="font-serif text-lg font-bold text-ink">
          The Six-Stage Continuous Learning Lifecycle
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {STAGES.map((s) => (
            <div key={s.step} className="p-4 bg-paper-sheet border border-paper-border shadow-paper space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-rust font-bold">{s.step}</span>
                <span className="px-1.5 py-0.5 bg-paper-subtle border border-paper-border font-mono text-[10px] text-ink-muted">
                  {s.tag}
                </span>
              </div>
              <h4 className="font-serif text-base font-bold text-ink leading-snug">
                {s.title}
              </h4>
              <p className="text-xs text-ink-muted leading-relaxed font-sans">
                {s.desc}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Engineering Guarantees Table */}
      <div className="bg-paper-sheet border border-paper-border shadow-paper p-5 space-y-4">
        <div className="pb-3 border-b border-paper-border">
          <h3 className="font-serif text-lg font-bold text-ink">
            Core Engineering & Safety Guarantees
          </h3>
          <p className="text-xs text-ink-muted mt-0.5">
            How production machine learning risks are systematically mitigated at the application layer.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs editorial-table">
            <thead className="bg-paper-subtle">
              <tr>
                <th className="p-3 w-1/3">Production Problem</th>
                <th className="p-3 w-2/3">InboxLearn Architecture Implementation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-paper-border bg-paper-sheet">
              {ENGINEERING_GUARANTEES.map((g, idx) => (
                <tr key={idx}>
                  <td className="p-3 font-serif font-bold text-ink align-top">
                    {g.problem}
                  </td>
                  <td className="p-3 text-ink-light font-sans leading-relaxed align-top">
                    {g.solution}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
};
