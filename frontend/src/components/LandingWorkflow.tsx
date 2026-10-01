import { useEffect, useRef } from 'react';
import anime from 'animejs';

/** Anime owns only this explanatory SVG path's dash offset. HTML is always visible. */
export function LandingWorkflow() {
  const figureRef = useRef<HTMLElement>(null);
  const pathRef = useRef<SVGPathElement>(null);
  useEffect(() => {
    const figure = figureRef.current;
    const path = pathRef.current;
    if (!figure || !path) return;
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    let animation: ReturnType<typeof anime> | undefined;
    let inView = false;
    let finished = false;
    let remainingDuration = 1800;
    const pause = () => {
      if (!animation) return;
      remainingDuration = Math.max(0, remainingDuration - animation.currentTime);
      animation.pause();
      // Anime v3 removes paused instances on its next RAF. Destroy this instance's
      // targets before resuming, including when the hidden-document RAF is suspended.
      anime.remove(path);
      animation = undefined;
    };
    const showStatic = () => {
      pause();
      path.style.strokeDashoffset = '0';
      path.style.strokeDasharray = 'none';
      finished = true;
    };
    const synchronize = () => {
      if (preference.matches) { showStatic(); return; }
      if (document.hidden || !inView) { pause(); return; }
      if (finished) return;
      try {
        if (!animation) {
          const length = path.getTotalLength();
          const offset = path.style.strokeDashoffset ? parseFloat(path.style.strokeDashoffset) : length;
          path.style.strokeDasharray = `${length}`;
          animation = anime({ targets: path, strokeDashoffset: [offset, 0], duration: remainingDuration,
            easing: 'easeInOutSine', autoplay: false, complete: () => { finished = true; } });
        }
        animation.play();
      } catch { showStatic(); }
    };
    const observer = 'IntersectionObserver' in window ? new IntersectionObserver(([entry]) => {
      inView = entry.isIntersecting; synchronize();
    }, { threshold: .15 }) : undefined;
    observer?.observe(figure);
    if (!observer) showStatic();
    synchronize();
    preference.addEventListener('change', synchronize);
    document.addEventListener('visibilitychange', synchronize);
    return () => {
      observer?.disconnect(); animation?.pause(); anime.remove(path);
      path.style.removeProperty('stroke-dashoffset'); path.style.removeProperty('stroke-dasharray');
      preference.removeEventListener('change', synchronize);
      document.removeEventListener('visibilitychange', synchronize);
    };
  }, []);

  return (
    <figure className="candidate-workflow" ref={figureRef}>
      <svg viewBox="0 0 640 110" fill="none" aria-hidden="true" focusable="false">
        <path d="M40 55H600" stroke="#d8c8b4" strokeWidth="2" />
        <path ref={pathRef} d="M40 55H600" stroke="#9c3b1b" strokeWidth="2" />
        {[40, 226, 413, 600].map((x, index) => <g key={x}><circle cx={x} cy="55" r="24" fill="#f7f5f0" stroke="#9c3b1b" /><text x={x} y="60" textAnchor="middle" fill="#78351e" fontSize="14">0{index + 1}</text></g>)}
      </svg>
      <ol>
        <li><strong>Saved corrections</strong><span>Human-confirmed labels</span></li>
        <li><strong>Prepare candidate</strong><span>Train from feedback</span></li>
        <li><strong>Compare predictions</strong><span>Inspect what changes</span></li>
        <li><strong>Evaluate separately</strong><span>Held-out examples first</span></li>
      </ol>
      <figcaption>A candidate is a proposal. The active model stays in place until activation is authorized.</figcaption>
    </figure>
  );
}
