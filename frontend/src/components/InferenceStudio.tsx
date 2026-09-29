import React, { useState } from 'react';
import { 
  Play, 
  RotateCcw, 
  Tag, 
  Calendar, 
  DollarSign, 
  CheckCircle2, 
  AlertCircle, 
  ExternalLink,
  Cpu,
  Layers,
  Sparkles,
  Download
} from 'lucide-react';
import { api, PredictResponse, ExtractedEntity } from '../api/client';

const PRESETS = [
  {
    name: 'Staff AI Offer',
    subject: 'Offer Letter - Staff Machine Learning Systems Engineer',
    sender: 'recruiting@deepmind-careers.internal',
    body: 'Dear Candidate, We are delighted to formally offer you the role of Staff ML Systems Engineer. Your compensation package, equity allocation, and team charter are detailed in the attached summary. Please sign and return the documents before October 15, 2026.',
    expected: 'job opportunities / high',
  },
  {
    name: 'Thesis Defense Notice',
    subject: 'Doctoral Dissertation Defense Scheduled: Distributed Convex Optimization',
    sender: 'registrar@cs.stanford.edu',
    body: 'The Graduate Academic Committee announces the defense of candidate thesis on Distributed Convex Optimization for Multi-Agent Systems on Monday, October 19, 2026 at 10:00 AM in Gates Hall 400. All faculty and students are invited.',
    expected: 'university / normal',
  },
  {
    name: 'AWS Cloud Invoice',
    subject: 'AWS Invoice Available: $3,420.50 USD for GPU Cluster Usage',
    sender: 'no-reply-aws@amazon.com',
    body: 'Your AWS billing statement for the previous billing cycle is ready. Amount due: $3,420.50. Automatic payment via corporate Visa card is scheduled for October 05, 2026.',
    expected: 'bills / high',
  },
  {
    name: 'Black Friday SaaS Sale',
    subject: 'Limited 50% Lifetime Discount on All GPU Compute Instances',
    sender: 'marketing@cloudgpu-deals.io',
    body: 'Get 50% off compute nodes for the next 48 hours only! Use coupon code CYBERLLM at checkout. Don’t miss this limited opportunity to expand your inference clusters at wholesale rates.',
    expected: 'promotions / low',
  },
  {
    name: 'Phishing Wire Transfer',
    subject: 'URGENT: Confidential Wire Transfer Authorization Required Immediately',
    sender: 'ceo-office-secure@external-domain-suspicious.com',
    body: 'Please initiate an immediate wire transfer of $85,000 to the overseas account provided in this email to complete our international acquisition. Do not call, I am boarding a flight.',
    expected: 'spam / high',
  },
];

export const InferenceStudio: React.FC = () => {
  const [subject, setSubject] = useState(PRESETS[0].subject);
  const [sender, setSender] = useState(PRESETS[0].sender);
  const [body, setBody] = useState(PRESETS[0].body);
  const [categoryThreshold, setCategoryThreshold] = useState(0.70);
  const [priorityThreshold, setPriorityThreshold] = useState(0.70);

  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);

  const handleRunInference = async () => {
    if (!subject.trim() && !body.trim()) return;
    setIsRunning(true);
    setErrorNotice(null);
    try {
      const res = await api.predict({
        subject,
        sender,
        body,
        category_threshold: categoryThreshold,
        priority_threshold: priorityThreshold,
      });
      setResult(res);
    } catch (err: any) {
      console.error('Inference probe failed', err);
      setErrorNotice(err.message || 'Inference probe failed');
    } finally {
      setIsRunning(false);
    }
  };

  const handleLoadPreset = (preset: typeof PRESETS[0]) => {
    setSubject(preset.subject);
    setSender(preset.sender);
    setBody(preset.body);
  };

  const handleDownloadIcs = () => {
    if (!result?.extracted_entities) return;
    const dateEntity = result.extracted_entities.find((e) => e.type === 'date');
    if (!dateEntity) return;

    const icsContent = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//InboxLearn//Triage Calendar Event//EN',
      'BEGIN:VEVENT',
      `SUMMARY:${subject}`,
      `DESCRIPTION:${body.slice(0, 100)}...`,
      `DTSTART;VALUE=DATE:${dateEntity.value.replace(/-/g, '')}`,
      'END:VEVENT',
      'END:VCALENDAR',
    ].join('\r\n');

    const blob = new Blob([icsContent], { type: 'text/calendar;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'inboxlearn_event.ics';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-4 border-b border-paper-border">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-[10px] tracking-wider uppercase text-rust font-semibold">
              03 INFERENCE PROBE BENCH
            </span>
            <span className="text-paper-border">·</span>
            <span className="font-mono text-[10px] text-ink-muted">
              4,096-DIM STATELESS FEATURE PROJECTION
            </span>
          </div>
          <h2 className="font-serif text-2xl sm:text-3xl font-bold text-ink">
            Interactive Model Inference Probe
          </h2>
          <p className="text-xs text-ink-muted mt-1 max-w-2xl leading-relaxed">
            Test the active classifier bundle on arbitrary email text. Inspect uncalibrated log-loss probability distributions, stateless hashing projection, and regex entity extraction.
          </p>
        </div>

        <div className="font-mono text-xs text-ink-muted bg-paper-sheet border border-paper-border px-3 py-2 shadow-paper-sm">
          <span>Vector: HashingVectorizer(n=4096, 1-2 ngrams)</span>
        </div>
      </div>

      {/* Preset Buttons Strip */}
      <div className="space-y-1.5">
        <span className="text-[10px] font-mono uppercase text-ink-faint block">
          Curated Scenario Presets:
        </span>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button
              key={p.name}
              onClick={() => handleLoadPreset(p)}
              className="px-2.5 py-1.5 bg-paper-sheet hover:bg-paper-subtle border border-paper-border text-xs text-ink transition-colors cursor-pointer shadow-paper-sm text-left"
            >
              <strong className="block text-ink">{p.name}</strong>
              <span className="text-[10px] font-mono text-ink-muted">{p.expected}</span>
            </button>
          ))}
        </div>
      </div>

      {errorNotice && (
        <div className="p-3 bg-rose-50 border border-rose-300 text-xs text-rose-900">
          {errorNotice}
        </div>
      )}

      {/* Main Two-Column Probe Console */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* Left Column: Input Form (6 Cols) */}
        <div className="lg:col-span-6 bg-paper-sheet border border-paper-border shadow-paper p-5 space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-paper-border">
            <span className="font-serif text-sm font-bold text-ink">
              Input Message Payload
            </span>
            <button
              onClick={() => {
                setSubject('');
                setSender('');
                setBody('');
              }}
              className="text-[11px] font-mono text-ink-muted hover:text-ink cursor-pointer"
            >
              Clear Form
            </button>
          </div>

          {/* Subject Field */}
          <div className="space-y-1">
            <label htmlFor="probe-subject" className="text-[10px] font-mono uppercase text-ink-muted block font-semibold">
              Subject Line:
            </label>
            <input
              id="probe-subject"
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. AWS Invoice or Fellowship Announcement"
              className="w-full bg-paper-canvas border border-paper-border px-3 py-2 text-xs text-ink focus:outline-none focus:border-rust"
            />
          </div>

          {/* Sender Field */}
          <div className="space-y-1">
            <label htmlFor="probe-sender" className="text-[10px] font-mono uppercase text-ink-muted block font-semibold">
              Sender Address / Header:
            </label>
            <input
              id="probe-sender"
              type="text"
              value={sender}
              onChange={(e) => setSender(e.target.value)}
              placeholder="e.g. billing@amazon.com"
              className="w-full bg-paper-canvas border border-paper-border px-3 py-2 text-xs text-ink focus:outline-none focus:border-rust"
            />
          </div>

          {/* Body Field */}
          <div className="space-y-1">
            <label htmlFor="probe-body" className="text-[10px] font-mono uppercase text-ink-muted block font-semibold">
              Email Body Text:
            </label>
            <textarea
              id="probe-body"
              rows={6}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Paste or type email body here..."
              className="w-full bg-paper-canvas border border-paper-border p-3 text-xs text-ink focus:outline-none focus:border-rust font-sans leading-relaxed"
            />
          </div>

          {/* Threshold Sliders */}
          <div className="pt-2 border-t border-paper-border grid grid-cols-2 gap-4 text-xs font-mono">
            <div>
              <div className="flex justify-between text-[11px]">
                <span className="text-ink-muted">Category Threshold:</span>
                <span className="text-ink font-bold">{(categoryThreshold * 100).toFixed(0)}%</span>
              </div>
              <input
                aria-label="Category confidence review threshold"
                type="range"
                min="0.30"
                max="0.95"
                step="0.05"
                value={categoryThreshold}
                onChange={(e) => setCategoryThreshold(parseFloat(e.target.value))}
                className="w-full accent-rust cursor-pointer mt-1"
              />
            </div>

            <div>
              <div className="flex justify-between text-[11px]">
                <span className="text-ink-muted">Priority Threshold:</span>
                <span className="text-ink font-bold">{(priorityThreshold * 100).toFixed(0)}%</span>
              </div>
              <input
                aria-label="Priority confidence review threshold"
                type="range"
                min="0.30"
                max="0.95"
                step="0.05"
                value={priorityThreshold}
                onChange={(e) => setPriorityThreshold(parseFloat(e.target.value))}
                className="w-full accent-rust cursor-pointer mt-1"
              />
            </div>
          </div>

          {/* Run Inference Action Button */}
          <button
            onClick={handleRunInference}
            disabled={isRunning || (!subject && !body)}
            className="w-full py-2.5 px-4 bg-rust hover:bg-rust-hover text-white text-xs font-sans font-semibold transition-colors flex items-center justify-center gap-2 cursor-pointer shadow-paper-sm disabled:opacity-50"
          >
            <Play className={`w-3.5 h-3.5 fill-current ${isRunning ? 'animate-spin' : ''}`} />
            <span>{isRunning ? 'Calculating Projections...' : 'Run Real-Time Inference Probe'}</span>
          </button>
        </div>

        {/* Right Column: Inference Output Sheet (6 Cols) */}
        <div className="lg:col-span-6 space-y-4">
          {result ? (
            <div className="bg-paper-sheet border border-paper-border shadow-paper p-5 space-y-5">
              
              {/* Output Header */}
              <div className="flex items-center justify-between pb-3 border-b border-paper-border">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-ink">
                    MODEL {result.model_label.toUpperCase()} OUTPUT
                  </span>
                  <span className="text-paper-border">·</span>
                  <span className="font-mono text-[10px] text-ink-muted">
                    {result.latency_ms.toFixed(1)} ms
                  </span>
                </div>

                {result.needs_review ? (
                  <span className="px-2 py-0.5 bg-amber-100 text-amber-900 border border-amber-300 font-mono text-[10px] font-bold uppercase">
                    Needs Review
                  </span>
                ) : (
                  <span className="px-2 py-0.5 bg-emerald-100 text-emerald-900 border border-emerald-300 font-mono text-[10px] font-bold uppercase">
                    Classified
                  </span>
                )}
              </div>

              {/* Classification Cards */}
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 bg-paper-canvas border border-paper-border">
                  <span className="text-[10px] font-mono uppercase text-ink-faint block">Predicted Category</span>
                  <strong className="font-serif text-lg text-ink font-bold block mt-0.5">
                    {result.category}
                  </strong>
                  <span className={`font-mono text-xs font-semibold ${result.category_confidence < categoryThreshold ? 'text-amber-800' : 'text-emerald-800'}`}>
                    {(result.category_confidence * 100).toFixed(1)}% confidence
                  </span>
                </div>

                <div className="p-3 bg-paper-canvas border border-paper-border">
                  <span className="text-[10px] font-mono uppercase text-ink-faint block">Predicted Priority</span>
                  <strong className="font-serif text-lg text-ink font-bold block mt-0.5">
                    {result.priority}
                  </strong>
                  <span className={`font-mono text-xs font-semibold ${result.priority_confidence < priorityThreshold ? 'text-amber-800' : 'text-emerald-800'}`}>
                    {(result.priority_confidence * 100).toFixed(1)}% confidence
                  </span>
                </div>
              </div>

              {/* Routing & Action Suggestion */}
              <div className="p-3 bg-paper-subtle border border-paper-border text-xs space-y-1">
                <div>
                  <span className="font-semibold text-ink">Suggested Action:</span>{' '}
                  <span className="text-ink-light">{result.suggested_action}</span>
                </div>
                <div>
                  <span className="font-semibold text-ink">Routing Reason:</span>{' '}
                  <span className="text-ink-muted italic">{result.routing_reason}</span>
                </div>
              </div>

              {/* Category Probability Distributions (Horizontal Bars) */}
              <div className="space-y-2">
                <span className="text-[10px] font-mono uppercase text-ink-faint block font-semibold">
                  Category Uncalibrated Log-Loss Probabilities
                </span>
                <div className="space-y-1.5 text-xs font-mono">
                  {Object.entries(result.all_category_scores)
                    .sort(([, a], [, b]) => b - a)
                    .map(([cat, score]) => (
                      <div key={cat} className="space-y-0.5">
                        <div className="flex justify-between text-[11px]">
                          <span className={cat === result.category ? 'font-bold text-ink' : 'text-ink-muted'}>
                            {cat}
                          </span>
                          <span className="font-bold text-ink">{(score * 100).toFixed(1)}%</span>
                        </div>
                        <div className="w-full h-1.5 bg-paper-border overflow-hidden">
                          <div
                            className={`h-full ${cat === result.category ? 'bg-rust' : 'bg-ink-muted'}`}
                            style={{ width: `${Math.max(2, score * 100)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                </div>
              </div>

              {/* Priority Probability Distributions */}
              <div className="space-y-2 pt-2 border-t border-paper-border">
                <span className="text-[10px] font-mono uppercase text-ink-faint block font-semibold">
                  Priority Probabilities
                </span>
                <div className="space-y-1.5 text-xs font-mono">
                  {Object.entries(result.all_priority_scores)
                    .sort(([, a], [, b]) => b - a)
                    .map(([pri, score]) => (
                      <div key={pri} className="space-y-0.5">
                        <div className="flex justify-between text-[11px]">
                          <span className={pri === result.priority ? 'font-bold text-ink' : 'text-ink-muted'}>
                            {pri}
                          </span>
                          <span className="font-bold text-ink">{(score * 100).toFixed(1)}%</span>
                        </div>
                        <div className="w-full h-1.5 bg-paper-border overflow-hidden">
                          <div
                            className={`h-full ${pri === result.priority ? 'bg-rust' : 'bg-ink-muted'}`}
                            style={{ width: `${Math.max(2, score * 100)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                </div>
              </div>

              {/* Extracted Entities */}
              {result.extracted_entities && result.extracted_entities.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-paper-border">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono uppercase text-ink-faint block font-semibold">
                      Extracted Entities
                    </span>
                    {result.has_calendar_event && (
                      <button
                        onClick={handleDownloadIcs}
                        className="inline-flex items-center gap-1 text-[11px] font-mono text-rust hover:underline cursor-pointer"
                      >
                        <Download className="w-3 h-3" />
                        <span>Download Event .ics</span>
                      </button>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {result.extracted_entities.map((ent, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-0.5 bg-paper-canvas border border-paper-border font-mono text-[11px] text-ink"
                      >
                        <strong className="text-rust">{ent.type}:</strong> {ent.value}
                      </span>
                    ))}
                  </div>
                </div>
              )}

            </div>
          ) : (
            <div className="p-8 bg-paper-sheet border border-paper-border text-center space-y-2 text-ink-muted shadow-paper-sm">
              <Layers className="w-8 h-8 text-ink-faint mx-auto" />
              <p className="font-serif text-base font-semibold text-ink">Inference probe ready</p>
              <p className="text-xs">Select a preset or enter message text on the left and click "Run Real-Time Inference Probe".</p>
            </div>
          )}
        </div>

      </div>

    </div>
  );
};
