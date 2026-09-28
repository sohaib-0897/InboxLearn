import React, { useState, useEffect, useRef } from 'react';
import Lenis from 'lenis';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Cpu, 
  ShieldCheck, 
  Activity, 
  Terminal, 
  Layers, 
  CheckSquare, 
  GitCompare, 
  History, 
  Lock, 
  Zap, 
  ArrowRight, 
  Sliders 
} from 'lucide-react';

import { api, StatusResponse } from './api/client';
import { HeroShader } from './components/HeroShader';
import { SpringModelCard } from './components/SpringModelCard';
import { PipelineLifecycle } from './components/PipelineLifecycle';
import { InferenceStudio } from './components/InferenceStudio';
import { ReviewDesk } from './components/ReviewDesk';
import { CandidateDiffGate } from './components/CandidateDiffGate';
import { VersionLedger } from './components/VersionLedger';
import { Navbar } from './components/Navbar';
import { MetricCounter } from './components/MetricCounter';

gsap.registerPlugin(ScrollTrigger);

export function App() {
  const [activeTab, setActiveTab] = useState<'studio' | 'review' | 'candidate' | 'ledger' | 'pipeline'>('studio');
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);

  const heroRef = useRef<HTMLDivElement>(null);

  const refreshStatus = async () => {
    try {
      const data = await api.getStatus();
      setStatus(data);
    } catch (err) {
      console.warn('API status fetch notice:', err);
    } finally {
      setIsInitializing(false);
    }
  };

  useEffect(() => {
    refreshStatus();
  }, []);

  // Initialize Lenis smooth scroll & integrate with GSAP ScrollTrigger
  useEffect(() => {
    const isReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (isReduced) return;

    const lenis = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      touchMultiplier: 2,
    });

    lenis.on('scroll', ScrollTrigger.update);

    const updateTicker = (time: number) => {
      lenis.raf(time * 1000);
    };

    gsap.ticker.add(updateTicker);
    gsap.ticker.lagSmoothing(0);

    return () => {
      gsap.ticker.remove(updateTicker);
      lenis.destroy();
    };
  }, []);

  // GSAP Hero Entrance Choreography
  useEffect(() => {
    const isReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (isReduced || !heroRef.current) return;

    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });

      tl.from('.hero-kicker', { opacity: 0, y: -20, duration: 0.6 })
        .from('.hero-title', { opacity: 0, y: 30, duration: 0.8 }, '-=0.3')
        .from('.hero-desc', { opacity: 0, y: 20, duration: 0.7 }, '-=0.5')
        .from('.hero-card', { opacity: 0, scale: 0.94, duration: 0.9 }, '-=0.6')
        .from('.hero-telemetry', { opacity: 0, y: 20, stagger: 0.1, duration: 0.6 }, '-=0.5');
    }, heroRef);

    return () => ctx.revert();
  }, []);

  return (
    <div className="min-h-screen bg-void text-zinc-100 flex flex-col font-sans selection:bg-brand-indigo selection:text-white">
      {/* Top Fixed Header */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        status={status}
      />

      <main className="flex-1">
        {/* ========================================================================= */}
        {/* HERO SECTION WITH THREE.JS SHADER & SPRING PHYSICS MODEL CARD             */}
        {/* ========================================================================= */}
        <section 
          ref={heroRef} 
          className="relative pt-12 pb-20 px-4 sm:px-6 lg:px-8 overflow-hidden border-b border-white/5 bg-grid-dots"
        >
          {/* WebGL Fluid Shader Gradient Canvas */}
          <HeroShader />

          {/* Foreground Hero Content */}
          <div className="relative max-w-7xl mx-auto z-10">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
              {/* Left Column: Typography & Agency Precision Copy */}
              <div className="lg:col-span-7 space-y-6">
                <div className="hero-kicker inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-elevated/90 border border-white/10 text-xs font-mono shadow-sm">
                  <span className="w-2 h-2 rounded-full bg-brand-emerald animate-pulse" />
                  <span className="text-zinc-300">LOCAL AI SYSTEMS ARCHITECTURE</span>
                  <span className="text-zinc-600">·</span>
                  <span className="text-brand-indigo font-semibold">IBL1 ARRAYS</span>
                </div>

                <h1 className="hero-title text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-white leading-[1.08]">
                  Precision Inference & Autonomous{' '}
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-indigo via-brand-cyan to-brand-emerald">
                    Learning Lifecycle
                  </span>
                </h1>

                <p className="hero-desc text-base sm:text-lg text-zinc-400 max-w-2xl leading-relaxed">
                  A high-throughput email triage agent operating locally with stateless 4,096-dimensional hashing, confidence routing, pre-activation prediction diffing, and evaluation-gated candidate models.
                </p>

                {/* Hero CTAs */}
                <div className="flex flex-wrap items-center gap-4 pt-2">
                  <button
                    onClick={() => setActiveTab('studio')}
                    className="flex items-center gap-2 px-6 py-3 rounded-xl bg-brand-indigo hover:bg-brand-indigo/90 text-white font-mono text-xs font-semibold shadow-glow-indigo transition-all group cursor-pointer"
                  >
                    <span>Launch Inference Studio</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </button>

                  <button
                    onClick={() => setActiveTab('candidate')}
                    className="flex items-center gap-2 px-5 py-3 rounded-xl bg-surface-elevated hover:bg-surface-highlight border border-white/10 text-zinc-200 font-mono text-xs transition-colors cursor-pointer"
                  >
                    <GitCompare className="w-4 h-4 text-brand-cyan" />
                    <span>Inspect Quality Gates</span>
                  </button>
                </div>

                {/* Hero Verification Metrics */}
                <div className="hero-telemetry pt-6 grid grid-cols-2 sm:grid-cols-4 gap-4 border-t border-white/10 text-xs font-mono">
                  <div>
                    <span className="text-zinc-500 text-[10px] block">CATEGORY F1 DELTA</span>
                    <div className="text-lg font-bold text-brand-emerald mt-0.5">
                      +47.1%
                    </div>
                    <span className="text-zinc-500 text-[10px]">0.422 → 0.893</span>
                  </div>

                  <div>
                    <span className="text-zinc-500 text-[10px] block">PRIORITY ACCURACY</span>
                    <div className="text-lg font-bold text-brand-emerald mt-0.5">
                      +50.0%
                    </div>
                    <span className="text-zinc-500 text-[10px]">30% → 80%</span>
                  </div>

                  <div>
                    <span className="text-zinc-500 text-[10px] block">FEATURE SPACE</span>
                    <div className="text-lg font-bold text-white mt-0.5">
                      4,096
                    </div>
                    <span className="text-zinc-500 text-[10px]">Stateless Hashing</span>
                  </div>

                  <div>
                    <span className="text-zinc-500 text-[10px] block">ROLLBACK RESTORATION</span>
                    <div className="text-lg font-bold text-brand-cyan mt-0.5">
                      Exact
                    </div>
                    <span className="text-zinc-500 text-[10px]">15/15 Probes Verified</span>
                  </div>
                </div>
              </div>

              {/* Right Column: Interactive 3D Spring Model Architecture Card */}
              <div className="hero-card lg:col-span-5 flex justify-center">
                <SpringModelCard
                  versionLabel={status?.active_version.label || 'v1'}
                  kind={status?.active_version.kind || 'baseline'}
                  seedCount={status?.active_version.seed_count || 15}
                  feedbackCount={status?.active_version.feedback_count || 0}
                  categoryAccuracy={0.90}
                  priorityAccuracy={0.80}
                />
              </div>
            </div>
          </div>
        </section>

        {/* ========================================================================= */}
        {/* INTERACTIVE WORKSPACE SECTIONS                                            */}
        {/* ========================================================================= */}
        <div className="relative">
          <AnimatePresence mode="wait">
            {activeTab === 'studio' && (
              <motion.div
                key="studio"
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -15 }}
                transition={{ duration: 0.25 }}
              >
                <InferenceStudio />
              </motion.div>
            )}

            {activeTab === 'review' && (
              <motion.div
                key="review"
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -15 }}
                transition={{ duration: 0.25 }}
              >
                <ReviewDesk onFeedbackSaved={refreshStatus} />
              </motion.div>
            )}

            {activeTab === 'candidate' && (
              <motion.div
                key="candidate"
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -15 }}
                transition={{ duration: 0.25 }}
              >
                <CandidateDiffGate
                  activeVersionId={status?.active_version.id || 1}
                  activeLabel={status?.active_version.label || 'v1'}
                  candidateInfo={status?.candidate || null}
                  onRefresh={refreshStatus}
                />
              </motion.div>
            )}

            {activeTab === 'ledger' && (
              <motion.div
                key="ledger"
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -15 }}
                transition={{ duration: 0.25 }}
              >
                <VersionLedger onRollback={refreshStatus} />
              </motion.div>
            )}

            {activeTab === 'pipeline' && (
              <motion.div
                key="pipeline"
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -15 }}
                transition={{ duration: 0.25 }}
              >
                <PipelineLifecycle />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Global Architecture Strip (Always visible when on Studio, Review, or Ledger) */}
        {activeTab !== 'pipeline' && (
          <div className="border-t border-white/5 py-12 bg-void/50">
            <PipelineLifecycle />
          </div>
        )}
      </main>

      {/* ========================================================================= */}
      {/* FOOTER & SYSTEM TELEMETRY STRIP                                           */}
      {/* ========================================================================= */}
      <footer className="border-t border-white/10 bg-void py-8 px-4 sm:px-6 lg:px-8 text-xs font-mono text-zinc-500">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-brand-indigo" />
            <span className="text-zinc-300 font-semibold">InboxLearn Engine</span>
            <span>· v2.4.0</span>
            <span>· Local Hardware Execution</span>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-[11px]">
            <span>153 Passed Tests</span>
            <span>·</span>
            <span>Zero Remote API Callout</span>
            <span>·</span>
            <span>IBL1 Safe Serialization</span>
            <span>·</span>
            <span>Strict Split Isolation</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
