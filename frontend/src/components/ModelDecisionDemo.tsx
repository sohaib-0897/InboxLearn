import { useState } from 'react';
import { motion } from 'motion/react';
import { useMotionPreference } from '../useMotionPreference';
import { ArrowRight, Check, RotateCcw } from 'lucide-react';

/** Explicitly local teaching state; never calls training or model APIs. */
export function ModelDecisionDemo() {
  const [stage, setStage] = useState<'prepared' | 'evaluated' | 'active' | 'restored'>('prepared');
  const reduced = useMotionPreference();
  const evaluated = stage !== 'prepared';
  return (
    <div className="decision-demo">
      <div className="decision-demo-heading"><span>THE ACTIVATION CHECKPOINT</span><button onClick={() => setStage('prepared')} type="button">Reset</button></div>
      <p className="demo-disclosure">Interactive illustration · no model is trained or changed.</p>
      <div className="model-pair">
        <div className={stage === 'active' ? '' : 'is-live'}><span>Original model</span><strong>A</strong><small>{stage === 'active' ? 'Kept in history' : 'Active'}</small></div>
        <ArrowRight size={24} aria-hidden="true" />
        <div className={stage === 'active' ? 'is-live' : ''}><span>Candidate</span><strong>B</strong><small>{stage === 'active' ? 'Active' : evaluated ? 'Evaluation recorded' : 'Awaiting evaluation'}</small></div>
      </div>
      <div className="decision-check"><Check size={17} aria-hidden="true" /><span>Preparing a candidate keeps the original model active.</span></div>
      <div className={`decision-check ${evaluated ? 'is-complete' : ''}`}><span className="decision-check-mark" aria-hidden="true">{evaluated ? '✓' : '○'}</span><span>Evaluation comes before the activation decision.</span></div>
      <div className="decision-actions">
        <button type="button" disabled={stage !== 'prepared'} onClick={() => setStage('evaluated')}>1. Simulate evaluation</button>
        <button type="button" disabled={stage !== 'evaluated'} onClick={() => setStage('active')}>2. Simulate activation</button>
        {stage === 'active' && <button type="button" onClick={() => setStage('restored')}><RotateCcw size={15} aria-hidden="true" /> Roll back illustration</button>}
      </div>
      <div className="decision-notice" role="status"><motion.p key={stage} initial={{ opacity: reduced ? 1 : .4 }} animate={{ opacity: 1 }} transition={{ duration: reduced ? 0 : .2 }}>
        {stage === 'prepared' ? 'Activation is locked. In the workspace, run the required held-out evaluation first.' : stage === 'evaluated' ? 'Illustrative evaluation recorded. Real results need your judgment; evaluation does not guarantee improvement.' : stage === 'active' ? 'B is active in this illustration. A is still available if you need to go back.' : 'Back to A. In the workspace, rollback restores a saved version and keeps your feedback.'}
      </motion.p></div>
    </div>
  );
}
