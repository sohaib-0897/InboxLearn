import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Play, 
  RotateCcw, 
  Sliders, 
  Sparkles, 
  AlertCircle, 
  CheckCircle2, 
  Calendar, 
  Tag, 
  Zap, 
  Layers, 
  ExternalLink 
} from 'lucide-react';
import { api, PredictResponse, ExtractedEntity } from '../api/client';
import { MetricCounter } from './MetricCounter';

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

const CATEGORY_COLORS: Record<string, string> = {
  'job opportunities': 'bg-indigo-500',
  'university': 'bg-cyan-500',
  'bills': 'bg-amber-500',
  'promotions': 'bg-pink-500',
  'spam': 'bg-rose-500',
};

const PRIORITY_COLORS: Record<string, string> = {
  'high': 'bg-rose-500',
  'normal': 'bg-amber-500',
  'low': 'bg-emerald-500',
};

export const InferenceStudio: React.FC = () => {
  const [subject, setSubject] = useState(PRESETS[0].subject);
  const [sender, setSender] = useState(PRESETS[0].sender);
  const [body, setBody] = useState(PRESETS[0].body);

  const [categoryThreshold, setCategoryThreshold] = useState(0.65);
  const [priorityThreshold, setPriorityThreshold] = useState(0.60);

  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runInference = async (customSub?: string, customSend?: string, customBody?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await api.predict({
        subject: customSub !== undefined ? customSub : subject,
        sender: customSend !== undefined ? customSend : sender,
        body: customBody !== undefined ? customBody : body,
        category_threshold: categoryThreshold,
        priority_threshold: priorityThreshold,
      });
      setResult(resp);
    } catch (err: any) {
      setError(err.message || 'Inference execution failed');
    } finally {
      setIsLoading(false);
    }
  };

  const applyPreset = (preset: typeof PRESETS[0]) => {
    setSubject(preset.subject);
    setSender(preset.sender);
    setBody(preset.body);
    runInference(preset.subject, preset.sender, preset.body);
  };

  const resetForm = () => {
    setSubject('');
    setSender('');
    setBody('');
    setResult(null);
    setError(null);
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Studio Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="w-2 h-2 rounded-full bg-brand-indigo animate-pulse" />
            <span className="font-mono text-xs text-brand-indigo uppercase tracking-wider">
              REAL-TIME PROBE BENCH
            </span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            Inference & Decision Studio
          </h2>
          <p className="text-sm text-zinc-400 mt-1">
            Probe the active SGDClassifier bundle directly across the 4,096-dim stateless feature space.
          </p>
        </div>

        {/* Presets */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-zinc-500 font-mono mr-1">Presets:</span>
          {PRESETS.map((p) => (
            <button
              key={p.name}
              onClick={() => applyPreset(p)}
              className="text-xs px-3 py-1.5 rounded-lg bg-surface-subtle border border-white/5 text-zinc-300 hover:text-white hover:border-brand-indigo/50 hover:bg-brand-indigo/10 transition-all font-mono"
            >
              {p.name}
            </button>
          ))}
        </div>
      </div>

      {/* Main Grid: Input Column & Live Metrics Output Column */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Email Input & Threshold Controls (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          <div className="rounded-2xl bg-surface/80 border border-white/10 p-6 backdrop-blur-xl shadow-tactile space-y-5">
            <div className="flex items-center justify-between border-b border-white/5 pb-3">
              <span className="font-mono text-xs text-zinc-400 font-semibold tracking-wider flex items-center gap-2">
                <Layers className="w-4 h-4 text-brand-indigo" />
                INPUT MESSAGE PAYLOAD
              </span>
              <button
                onClick={resetForm}
                className="text-xs text-zinc-500 hover:text-zinc-300 flex items-center gap-1 font-mono transition-colors"
                title="Reset input fields"
              >
                <RotateCcw className="w-3.5 h-3.5" /> Clear
              </button>
            </div>

            {/* Subject Input */}
            <div className="space-y-1.5">
              <label className="text-xs font-mono text-zinc-400 flex items-center justify-between">
                <span>SUBJECT</span>
                <span className="text-zinc-600 text-[11px]">{subject.length} chars</span>
              </label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Enter email subject line..."
                className="w-full px-4 py-2.5 rounded-xl bg-surface-elevated border border-white/10 text-white placeholder-zinc-600 text-sm focus:outline-none focus:border-brand-indigo focus:ring-1 focus:ring-brand-indigo transition-all font-sans"
              />
            </div>

            {/* Sender Input */}
            <div className="space-y-1.5">
              <label className="text-xs font-mono text-zinc-400">SENDER / FROM</label>
              <input
                type="text"
                value={sender}
                onChange={(e) => setSender(e.target.value)}
                placeholder="sender@domain.tld or Organization Name"
                className="w-full px-4 py-2.5 rounded-xl bg-surface-elevated border border-white/10 text-white placeholder-zinc-600 text-sm focus:outline-none focus:border-brand-indigo focus:ring-1 focus:ring-brand-indigo transition-all font-sans"
              />
            </div>

            {/* Body Input */}
            <div className="space-y-1.5">
              <label className="text-xs font-mono text-zinc-400 flex items-center justify-between">
                <span>BODY (SANITIZED PLAINTEXT)</span>
                <span className="text-zinc-600 text-[11px]">{body.length} chars</span>
              </label>
              <textarea
                rows={5}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Paste or type email text content here..."
                className="w-full px-4 py-3 rounded-xl bg-surface-elevated border border-white/10 text-white placeholder-zinc-600 text-sm focus:outline-none focus:border-brand-indigo focus:ring-1 focus:ring-brand-indigo transition-all resize-none font-sans leading-relaxed"
              />
            </div>

            {/* Threshold Sliders */}
            <div className="p-4 rounded-xl bg-void/50 border border-white/5 space-y-4">
              <div className="flex items-center gap-2 text-xs font-mono text-zinc-300">
                <Sliders className="w-3.5 h-3.5 text-brand-cyan" />
                <span>CONFIDENCE ROUTING THRESHOLDS</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-zinc-400">Category Cutoff</span>
                    <span className="text-brand-indigo font-bold">{(categoryThreshold * 100).toFixed(0)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0.4"
                    max="0.95"
                    step="0.05"
                    value={categoryThreshold}
                    onChange={(e) => setCategoryThreshold(parseFloat(e.target.value))}
                    className="w-full accent-brand-indigo cursor-pointer h-1.5 bg-zinc-800 rounded-lg appearance-none"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-zinc-400">Priority Cutoff</span>
                    <span className="text-brand-cyan font-bold">{(priorityThreshold * 100).toFixed(0)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0.4"
                    max="0.95"
                    step="0.05"
                    value={priorityThreshold}
                    onChange={(e) => setPriorityThreshold(parseFloat(e.target.value))}
                    className="w-full accent-brand-cyan cursor-pointer h-1.5 bg-zinc-800 rounded-lg appearance-none"
                  />
                </div>
              </div>
            </div>

            {/* Action Bar */}
            <div className="flex items-center justify-between pt-2">
              <button
                onClick={() => runInference()}
                disabled={isLoading || (!subject && !body)}
                className="flex items-center gap-2 px-6 py-3 rounded-xl bg-brand-indigo hover:bg-brand-indigo/90 text-white font-semibold text-sm shadow-glow-indigo transition-all disabled:opacity-50 disabled:cursor-not-allowed group cursor-pointer"
              >
                {isLoading ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Projecting Features...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-current group-hover:scale-110 transition-transform" />
                    <span>Execute Inference Probe</span>
                  </>
                )}
              </button>

              <span className="text-xs font-mono text-zinc-500 hidden sm:inline-block">
                Zero external API dependencies
              </span>
            </div>
          </div>
        </div>

        {/* Right Column: Live Output & Probability Manifold (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          <AnimatePresence mode="wait">
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="p-4 rounded-xl bg-brand-rose/10 border border-brand-rose/30 text-brand-rose flex items-start gap-3"
              >
                <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                <div className="text-xs font-mono">
                  <div className="font-semibold mb-1">Inference Engine Error</div>
                  <div>{error}</div>
                </div>
              </motion.div>
            )}

            {result ? (
              <motion.div
                key="result"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3 }}
                className="rounded-2xl bg-surface-elevated border border-white/10 p-6 backdrop-blur-xl shadow-tactile space-y-6"
              >
                {/* Header: Latency & Model Lineage */}
                <div className="flex items-center justify-between border-b border-white/5 pb-4">
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-brand-amber" />
                    <span className="text-xs font-mono text-zinc-400">LATENCY:</span>
                    <MetricCounter
                      value={result.latency_ms}
                      decimals={2}
                      suffix=" ms"
                      className="text-sm font-bold text-white"
                    />
                  </div>

                  <div className="text-xs font-mono text-zinc-500">
                    MODEL: <span className="text-brand-indigo font-bold">{result.model_label.toUpperCase()}</span>
                  </div>
                </div>

                {/* Primary Decision Banner */}
                <div className="p-4 rounded-xl bg-surface border border-white/5 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-mono text-zinc-500 tracking-wider">PREDICTED DECISION</span>
                    <div
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono ${
                        result.needs_review
                          ? 'bg-brand-amber/15 text-brand-amber border border-brand-amber/30'
                          : 'bg-brand-emerald/15 text-brand-emerald border border-brand-emerald/30'
                      }`}
                    >
                      {result.needs_review ? (
                        <>
                          <AlertCircle className="w-3.5 h-3.5" />
                          <span>NEEDS HUMAN REVIEW</span>
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>AUTO-CLASSIFIED</span>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 pt-1">
                    <div>
                      <div className="text-xs text-zinc-400 font-mono">Category</div>
                      <div className="text-lg font-bold text-white capitalize">
                        {result.category}
                      </div>
                      <div className="text-xs font-mono text-zinc-400 mt-0.5">
                        <MetricCounter value={result.category_confidence * 100} decimals={1} suffix="%" /> conf
                      </div>
                    </div>

                    <div>
                      <div className="text-xs text-zinc-400 font-mono">Priority</div>
                      <div className="text-lg font-bold text-white capitalize">
                        {result.priority}
                      </div>
                      <div className="text-xs font-mono text-zinc-400 mt-0.5">
                        <MetricCounter value={result.priority_confidence * 100} decimals={1} suffix="%" /> conf
                      </div>
                    </div>
                  </div>
                </div>

                {/* All Category Probability Distributions */}
                <div className="space-y-3">
                  <div className="flex justify-between items-center text-xs font-mono text-zinc-400">
                    <span>CATEGORY PROBABILITY PROFILE</span>
                    <span className="text-[10px] text-zinc-600">Uncalibrated Log-Loss</span>
                  </div>

                  <div className="space-y-2">
                    {Object.entries(result.all_category_scores)
                      .sort(([, a], [, b]) => b - a)
                      .map(([cat, score]) => (
                        <div key={cat} className="space-y-1">
                          <div className="flex justify-between text-xs">
                            <span className={`capitalize ${cat === result.category ? 'text-white font-medium' : 'text-zinc-400'}`}>
                              {cat}
                            </span>
                            <span className="font-mono text-zinc-300">
                              {(score * 100).toFixed(1)}%
                            </span>
                          </div>
                          <div className="h-1.5 w-full bg-zinc-800/80 rounded-full overflow-hidden">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${Math.max(score * 100, 2)}%` }}
                              transition={{ duration: 0.5, ease: 'easeOut' }}
                              className={`h-full rounded-full ${
                                cat === result.category ? (CATEGORY_COLORS[cat] || 'bg-brand-indigo') : 'bg-zinc-600'
                              }`}
                            />
                          </div>
                        </div>
                      ))}
                  </div>
                </div>

                {/* Priority Distribution */}
                <div className="space-y-3 pt-2">
                  <div className="flex justify-between items-center text-xs font-mono text-zinc-400">
                    <span>PRIORITY PROBABILITY PROFILE</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    {['high', 'normal', 'low'].map((prio) => {
                      const score = result.all_priority_scores[prio] || 0;
                      const isChosen = prio === result.priority;
                      return (
                        <div
                          key={prio}
                          className={`p-2.5 rounded-xl border text-center font-mono ${
                            isChosen
                              ? 'bg-white/10 border-white/20 text-white'
                              : 'bg-surface/50 border-white/5 text-zinc-400'
                          }`}
                        >
                          <div className="text-[11px] capitalize">{prio}</div>
                          <div className="text-sm font-semibold mt-0.5">
                            {(score * 100).toFixed(1)}%
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Routing Reason Explanation */}
                <div className="p-3.5 rounded-xl bg-void/60 border border-white/5 text-xs text-zinc-300 space-y-1 font-sans">
                  <div className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">
                    EXPLAINABLE ROUTING REASON
                  </div>
                  <p className="leading-relaxed">{result.routing_reason}</p>
                </div>

                {/* Extracted Entities & RFC 5545 */}
                {result.extracted_entities && result.extracted_entities.length > 0 && (
                  <div className="space-y-2 pt-2 border-t border-white/5">
                    <div className="flex items-center gap-1.5 text-xs font-mono text-zinc-400">
                      <Tag className="w-3.5 h-3.5 text-brand-cyan" />
                      <span>EXTRACTED ENTITIES & DEADLINES</span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {result.extracted_entities.map((e, idx) => (
                        <div
                          key={idx}
                          className="px-2.5 py-1 rounded-lg bg-surface border border-white/10 text-xs font-mono flex items-center gap-1.5 text-zinc-200"
                        >
                          <span className="text-[10px] text-brand-cyan uppercase">{e.type}:</span>
                          <span>{e.value}</span>
                          <span className="text-[10px] text-zinc-500 font-sans">({e.raw_phrase})</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            ) : (
              /* Empty state before running inference */
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="rounded-2xl bg-surface/40 border border-dashed border-white/10 p-12 text-center flex flex-col items-center justify-center space-y-4 min-h-[380px]"
              >
                <div className="w-14 h-14 rounded-2xl bg-brand-indigo/10 border border-brand-indigo/20 flex items-center justify-center text-brand-indigo">
                  <Sparkles className="w-7 h-7" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-white">Inference Engine Ready</h3>
                  <p className="text-xs text-zinc-400 mt-1 max-w-xs mx-auto">
                    Type a message or select a preset above, then click <strong>Execute Inference Probe</strong> to evaluate across the feature space.
                  </p>
                </div>
                <div className="text-[11px] font-mono text-zinc-500 pt-2">
                  [BOUNDED HASH: 4096-DIM · SGD LOSS: LOG]
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};
