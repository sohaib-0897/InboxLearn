import React, { useEffect, useRef } from 'react';
import anime from 'animejs';

interface MetricCounterProps {
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
  className?: string;
}

export const MetricCounter: React.FC<MetricCounterProps> = ({
  value,
  decimals = 0,
  prefix = '',
  suffix = '',
  duration = 900,
  className = '',
}) => {
  const nodeRef = useRef<HTMLSpanElement>(null);
  const currentValRef = useRef({ val: 0 });

  useEffect(() => {
    const isReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (isReduced) {
      if (nodeRef.current) {
        nodeRef.current.textContent = `${prefix}${value.toFixed(decimals)}${suffix}`;
      }
      return;
    }

    const anim = anime({
      targets: currentValRef.current,
      val: value,
      duration,
      easing: 'easeOutExpo',
      update: () => {
        if (nodeRef.current) {
          nodeRef.current.textContent = `${prefix}${currentValRef.current.val.toFixed(decimals)}${suffix}`;
        }
      },
    });

    return () => {
      anim.pause();
    };
  }, [value, decimals, prefix, suffix, duration]);

  return (
    <span ref={nodeRef} className={`tabular-nums font-mono ${className}`}>
      {prefix}{value.toFixed(decimals)}{suffix}
    </span>
  );
};
