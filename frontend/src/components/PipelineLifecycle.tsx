import React, { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { 
  Inbox, 
  Binary, 
  GitBranch, 
  CheckSquare, 
  Cpu, 
  ShieldCheck, 
  ArrowRight 
} from 'lucide-react';

gsap.registerPlugin(ScrollTrigger);

const PIPELINE_STAGES = [
  {
    step: '01',
    title: 'Intake & Bounded Sanitization',
    desc: 'RFC 822 MIME parsing with strict 5MB bounds, HTML strip to plaintext, and zero network leakage.',
    icon: Inbox,
    color: 'from-blue-500/20 to-indigo-500/20',
    border: 'border-blue-500/30',
    tag: 'READ-ONLY INTAKE',
  },
  {
    step: '02',
    title: 'Stateless 4,096-D Hashing',
    desc: 'HashingVectorizer mapping 1-2 ngrams into 4096 dimensions. No vocabulary drift or dictionary sync overhead.',
    icon: Binary,
    color: 'from-indigo-500/20 to-purple-500/20',
    border: 'border-indigo-500/30',
    tag: 'FEATURE PROJECTION',
  },
  {
    step: '03',
    title: 'Twin SGD Confidence Routing',
    desc: 'Dual log-loss classifiers route predictions below thresholds (65% category, 60% priority) to human triage.',
    icon: GitBranch,
    color: 'from-amber-500/20 to-orange-500/20',
    border: 'border-amber-500/30',
    tag: 'CONFIDENCE GATE',
  },
  {
    step: '04',
    title: 'Operator Review & Correction',
    desc: 'Human corrections are stored with batch checksum tokens preventing stale concurrent overwrites.',
    icon: CheckSquare,
    color: 'from-cyan-500/20 to-teal-500/20',
    border: 'border-cyan-500/30',
    tag: 'HUMAN-IN-THE-LOOP',
  },
  {
    step: '05',
    title: 'Split-Isolated Candidate Training',
    desc: 'assert_split_isolated() guarantees zero normalized overlap before creating safe IBL1 snapshots.',
    icon: Cpu,
    color: 'from-violet-500/20 to-pink-500/20',
    border: 'border-violet-500/30',
    tag: 'SAFE IBL1 SERIALIZATION',
  },
  {
    step: '06',
    title: 'Held-Out Eval Gate & Rollback',
    desc: 'Candidates cannot activate without verified held-out evaluation. One click restores historical weights.',
    icon: ShieldCheck,
    color: 'from-emerald-500/20 to-green-500/20',
    border: 'border-emerald-500/30',
    tag: 'EVALUATION GATING',
  },
];

export const PipelineLifecycle: React.FC = () => {
  const sectionRef = useRef<HTMLDivElement>(null);
  const cardsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const isReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (isReduced) return;

    const ctx = gsap.context(() => {
      const cards = gsap.utils.toArray('.pipeline-card');

      gsap.from(cards, {
        scrollTrigger: {
          trigger: cardsRef.current,
          start: 'top 85%',
          end: 'bottom 40%',
          scrub: 0.8,
        },
        y: 60,
        opacity: 0.15,
        stagger: 0.15,
        ease: 'power2.out',
      });
    }, sectionRef);

    return () => ctx.revert();
  }, []);

  return (
    <section ref={sectionRef} className="py-24 px-4 sm:px-6 lg:px-8 relative overflow-hidden">
      <div className="max-w-7xl mx-auto">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-indigo/10 border border-brand-indigo/20 text-brand-indigo text-xs font-mono mb-4">
            <span>[PIPELINE ARCHITECTURE]</span>
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight text-white mb-4">
            Engineered for Continuous, Safe Learning
          </h2>
          <p className="text-base text-zinc-400">
            Every incoming message traverses strict boundaries: stateless vectorization, confidence-routed human triage, split-isolated candidate training, and evaluation-gated deployment.
          </p>
        </div>

        {/* Scroll-scrubbed Cards Grid */}
        <div 
          ref={cardsRef} 
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 relative"
        >
          {PIPELINE_STAGES.map((stage, idx) => {
            const Icon = stage.icon;
            return (
              <div
                key={stage.step}
                className={`pipeline-card relative rounded-2xl bg-surface/80 border ${stage.border} p-6 backdrop-blur-md flex flex-col justify-between hover:bg-surface-elevated transition-colors group`}
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <span className="font-mono text-xs px-2.5 py-1 rounded bg-white/5 text-zinc-400 border border-white/5">
                      STAGE {stage.step}
                    </span>
                    <span className="font-mono text-[10px] tracking-wider text-zinc-500">
                      {stage.tag}
                    </span>
                  </div>

                  <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${stage.color} flex items-center justify-center mb-4 text-white border border-white/10 group-hover:scale-105 transition-transform`}>
                    <Icon className="w-6 h-6" />
                  </div>

                  <h3 className="text-lg font-semibold text-white mb-2 group-hover:text-brand-indigo transition-colors">
                    {stage.title}
                  </h3>

                  <p className="text-sm text-zinc-400 leading-relaxed">
                    {stage.desc}
                  </p>
                </div>

                <div className="pt-6 mt-4 border-t border-white/5 flex items-center justify-between text-xs text-zinc-500 font-mono">
                  <span>Isolated Boundary</span>
                  <ArrowRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all text-brand-indigo" />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
