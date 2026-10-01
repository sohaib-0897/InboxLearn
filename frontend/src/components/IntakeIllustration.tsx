import { useState } from 'react';
import { animated, useSpring } from '@react-spring/web';
import { useMotionPreference } from '../useMotionPreference';

/** A local routing explanation. Spring owns only the envelope position. */
export function IntakeIllustration() {
  const [uncertain, setUncertain] = useState(true);
  const reduced = useMotionPreference();
  const spring = useSpring({ x: uncertain ? 296 : 60, rotate: uncertain ? 7 : -7,
    immediate: !!reduced, config: { tension: 170, friction: 24 } });
  return (
    <figure className="intake-illustration">
      <div className="illustration-caption"><span>One message. Two possible paths.</span><span>01 → 02</span></div>
      <svg viewBox="0 0 480 310" aria-hidden="true" focusable="false">
        <path d="M240 30V100Q240 124 210 124H134Q114 124 114 145M240 100Q240 124 270 124H346Q366 124 366 145" fill="none" stroke="#a8997b" strokeWidth="1.5" strokeDasharray="4 5" />
        <text x="240" y="28" textAnchor="middle" className="diagram-label">CATEGORY + PRIORITY</text>
        <path d="M44 240H184L169 281H59Z" fill="#dce3ca" stroke="#748264" />
        <path d="M276 240H416L401 281H291Z" fill="#edb79b" stroke="#ab5336" />
        <animated.g transform={spring.x.to(x => `translate(${x} 0)`)}>
          <animated.g transform={spring.rotate.to(r => `translate(0 145) rotate(${r} 50 35)`)}>
            <rect width="108" height="76" fill="#fffaf0" stroke="#522d23" strokeWidth="1.5" />
            <path d="M0 0L54 43L108 0M0 76L39 32M108 76L69 32" fill="none" stroke="#522d23" strokeWidth="1.5" />
            <circle cx="88" cy="16" r="8" fill="#ad482f" />
          </animated.g>
        </animated.g>
        <text x="114" y="307" textAnchor="middle" className="diagram-label">CLASSIFIED</text>
        <text x="346" y="307" textAnchor="middle" className="diagram-label">NEEDS YOUR REVIEW</text>
      </svg>
      <div className="routing-choices" role="group" aria-label="Illustrate confidence routing">
        <button type="button" aria-pressed={!uncertain} onClick={() => setUncertain(false)}>Above both thresholds</button>
        <button type="button" aria-pressed={uncertain} onClick={() => setUncertain(true)}>A little uncertain</button>
      </div>
      <figcaption aria-live="polite">{uncertain ? 'When either confidence is below its threshold, you make the call.' : 'Above both thresholds, the message is classified. You can still review it.'} <span>Illustration only.</span></figcaption>
    </figure>
  );
}
