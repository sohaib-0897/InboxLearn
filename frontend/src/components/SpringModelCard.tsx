import React, { useRef, useState } from 'react';
import { useSpring, animated } from '@react-spring/web';
import { ShieldCheck, Cpu, Database, Activity, RefreshCw } from 'lucide-react';

interface SpringModelCardProps {
  versionLabel?: string;
  kind?: string;
  seedCount?: number;
  feedbackCount?: number;
  categoryAccuracy?: number;
  priorityAccuracy?: number;
}

const calc = (x: number, y: number, rect: DOMRect) => [
  -(y - rect.top - rect.height / 2) / 18,
  (x - rect.left - rect.width / 2) / 18,
  1.02,
];

const trans = (x: number, y: number, s: number) =>
  `perspective(800px) rotateX(${x}deg) rotateY(${y}deg) scale(${s})`;

export const SpringModelCard: React.FC<SpringModelCardProps> = ({
  versionLabel = 'v1',
  kind = 'baseline',
  seedCount = 15,
  feedbackCount = 0,
  categoryAccuracy = 0.90,
  priorityAccuracy = 0.80,
}) => {
  const cardRef = useRef<HTMLDivElement>(null);
  const [isFlipped, setIsFlipped] = useState(false);

  // React Spring physics animation
  const [{ xys, specular }, api] = useSpring(() => ({
    xys: [0, 0, 1],
    specular: [50, 50],
    config: { mass: 1.2, tension: 260, friction: 22 },
  }));

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const x = e.clientX;
    const y = e.clientY;
    api.start({
      xys: calc(x, y, rect),
      specular: [
        ((x - rect.left) / rect.width) * 100,
        ((y - rect.top) / rect.height) * 100,
      ],
    });
  };

  const handlePointerLeave = () => {
    api.start({
      xys: [0, 0, 1],
      specular: [50, 50],
    });
  };

  return (
    <div className="relative select-none py-4">
      <animated.div
        ref={cardRef}
        onPointerMove={handlePointerMove}
        onPointerLeave={handlePointerLeave}
        style={{
          transform: xys.to(trans),
        }}
        className="w-full max-w-md mx-auto rounded-2xl p-[1px] bg-gradient-to-b from-brand-indigo/40 via-white/10 to-brand-cyan/20 shadow-tactile transition-shadow hover:shadow-tactile-hover cursor-pointer"
        onClick={() => setIsFlipped(!isFlipped)}
      >
        <div className="relative rounded-2xl bg-surface-elevated/95 backdrop-blur-xl p-6 overflow-hidden border border-white/10">
          {/* Specular highlight translation across spring motion */}
          <animated.div
            className="absolute inset-0 pointer-events-none opacity-20"
            style={{
              background: specular.to(
                (sx, sy) =>
                  `radial-gradient(circle 240px at ${sx}% ${sy}%, rgba(255,255,255,0.4), transparent 70%)`
              ),
            }}
          />

          {/* Header */}
          <div className="flex items-center justify-between border-b border-white/5 pb-4 mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-brand-indigo/15 border border-brand-indigo/30 flex items-center justify-center text-brand-indigo shadow-glow-indigo">
                <Cpu className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-semibold tracking-wider text-white">
                    MODEL BUNDLE
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-brand-indigo/20 text-brand-indigo border border-brand-indigo/30">
                    {versionLabel.toUpperCase()}
                  </span>
                </div>
                <p className="text-xs text-zinc-400 capitalize">{kind} snapshot</p>
              </div>
            </div>

            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-brand-emerald/10 border border-brand-emerald/30 text-brand-emerald text-xs font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-emerald animate-pulse" />
              ACTIVE
            </div>
          </div>

          {!isFlipped ? (
            /* Front Face: Architecture Metrics & Memory State */
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-xl bg-surface/70 border border-white/5">
                  <div className="text-[11px] text-zinc-400 flex items-center gap-1 mb-1">
                    <Database className="w-3.5 h-3.5 text-brand-cyan" />
                    Feature Space
                  </div>
                  <div className="text-lg font-mono font-semibold text-white">
                    4,096 <span className="text-xs text-zinc-500 font-normal">dims</span>
                  </div>
                  <div className="text-[10px] text-zinc-500 font-mono mt-0.5">
                    HashingVectorizer (1-2)
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-surface/70 border border-white/5">
                  <div className="text-[11px] text-zinc-400 flex items-center gap-1 mb-1">
                    <Activity className="w-3.5 h-3.5 text-brand-emerald" />
                    Linear Solvers
                  </div>
                  <div className="text-lg font-mono font-semibold text-white">
                    2x <span className="text-xs text-zinc-500 font-normal">SGD</span>
                  </div>
                  <div className="text-[10px] text-zinc-500 font-mono mt-0.5">
                    Loss: log_loss (optimal)
                  </div>
                </div>
              </div>

              {/* Data partition gauges */}
              <div className="space-y-2 p-3 rounded-xl bg-surface/40 border border-white/5">
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-400">Training Composition</span>
                  <span className="font-mono text-zinc-300">
                    {seedCount} seed · {feedbackCount} feedback
                  </span>
                </div>
                <div className="h-1.5 w-full bg-zinc-800 rounded-full overflow-hidden flex">
                  <div
                    className="bg-brand-indigo h-full"
                    style={{
                      width: `${(seedCount / (seedCount + feedbackCount || 1)) * 100}%`,
                    }}
                    title="Seed Examples"
                  />
                  <div
                    className="bg-brand-cyan h-full"
                    style={{
                      width: `${(feedbackCount / (seedCount + feedbackCount || 1)) * 100}%`,
                    }}
                    title="Human Feedback Corrections"
                  />
                </div>
                <div className="flex justify-between text-[10px] font-mono text-zinc-500">
                  <span>Synthetic Seed Split</span>
                  <span>Incremental Feedback</span>
                </div>
              </div>

              {/* Verification & Serialization Guarantee */}
              <div className="flex items-center justify-between text-xs pt-1 px-1">
                <div className="flex items-center gap-1.5 text-zinc-400">
                  <ShieldCheck className="w-4 h-4 text-brand-emerald" />
                  <span>IBL1 Array Binary (No Pickle)</span>
                </div>
                <span className="text-zinc-500 font-mono text-[11px] flex items-center gap-1 hover:text-white transition-colors">
                  <RefreshCw className="w-3 h-3" /> Flip details
                </span>
              </div>
            </div>
          ) : (
            /* Back Face: Serialization & Mathematical Invariants */
            <div className="space-y-3 font-mono text-xs">
              <div className="text-zinc-300 font-semibold mb-2 flex items-center justify-between">
                <span>IBL1 DESERIALIZATION SCHEMA</span>
                <span className="text-[10px] text-brand-indigo">REVERSIBLE</span>
              </div>

              <div className="p-2.5 rounded-lg bg-void/80 border border-white/10 text-[11px] space-y-1.5 text-zinc-400">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Magic Header:</span>
                  <span className="text-emerald-400">b"IBL1\x00"</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Coefficients:</span>
                  <span className="text-zinc-200">Float64 Contiguous</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Category Accuracy:</span>
                  <span className="text-cyan-400">{(categoryAccuracy * 100).toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Priority Accuracy:</span>
                  <span className="text-cyan-400">{(priorityAccuracy * 100).toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Rollback Precision:</span>
                  <span className="text-brand-emerald">Bit-Exact (15/15 Probes)</span>
                </div>
              </div>

              <p className="text-[10px] text-zinc-400 leading-relaxed">
                Snapshot stored with exact revision foreign keys in SQLite. Direct activation bypass is prevented by evaluation hash validation.
              </p>
              
              <div className="text-center pt-1">
                <span className="text-zinc-500 text-[11px] hover:text-white transition-colors">
                  Click to return
                </span>
              </div>
            </div>
          )}
        </div>
      </animated.div>
    </div>
  );
};
