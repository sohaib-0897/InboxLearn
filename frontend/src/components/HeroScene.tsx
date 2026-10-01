import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';

// A clip-space quad fills the viewport: no camera angle, silhouette or terrain.
const vertexShader = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = vec4(position.xy, 0.0, 1.0);
  }
`;
const fragmentShader = `
  uniform float uTime;
  varying vec2 vUv;
  void main() {
    float t = uTime * 0.16;
    vec2 p = vUv;
    p += 0.055 * vec2(sin(p.y * 6.0 + t), cos(p.x * 5.0 - t));
    vec2 ochreCenter = vec2(0.08 + 0.12 * sin(t), 0.2 + 0.12 * cos(t * 0.8));
    vec2 clayCenter = vec2(0.94 + 0.1 * cos(t * 0.7), 0.72 + 0.18 * sin(t));
    float ochre = exp(-3.8 * dot(p - ochreCenter, p - ochreCenter));
    float clay = exp(-4.6 * dot(p - clayCenter, p - clayCenter));
    vec3 cream = vec3(0.988, 0.949, 0.82);
    vec3 color = mix(cream, vec3(0.91, 0.58, 0.19), ochre * 0.93);
    color = mix(color, vec3(0.78, 0.28, 0.16), clay * 0.91);
    // Keep the reading area light throughout the animation, including mobile.
    float readingArea = 1.0 - smoothstep(0.12, 0.65, abs(p.x - 0.5));
    color = mix(color, cream, readingArea * 0.52);
    gl_FragColor = vec4(color, 1.0);
  }
`;

function GradientField() {
  const uniforms = useMemo(() => ({ uTime: { value: 0 } }), []);
  useFrame((_, delta) => {
    // Accumulate active time only; avoid a jump after a hidden tab resumes.
    uniforms.uTime.value += Math.min(delta, 0.05);
  });
  return (
    <mesh frustumCulled={false}>
      <planeGeometry args={[2, 2]} />
      <shaderMaterial vertexShader={vertexShader} fragmentShader={fragmentShader} uniforms={uniforms} depthTest={false} depthWrite={false} />
    </mesh>
  );
}

// Renderer construction and in-canvas errors must never remove the HTML hero.
class SceneBoundary extends React.Component<React.PropsWithChildren, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? null : this.props.children; }
}

export function HeroScene({ className = '' }: { className?: string }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [supported, setSupported] = useState(false);
  const [failed, setFailed] = useState(false);
  const [visible, setVisible] = useState(true);
  const [documentVisible, setDocumentVisible] = useState(() => !document.hidden);

  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const onPreference = () => setReducedMotion(preference.matches);
    preference.addEventListener('change', onPreference);
    onPreference();
    const onVisibility = () => setDocumentVisible(!document.hidden);
    document.addEventListener('visibilitychange', onVisibility);
    onVisibility();
    // The host stays mounted across all fallback/canvas transitions.
    const observer = 'IntersectionObserver' in window
      ? new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting))
      : undefined;
    if (hostRef.current) observer?.observe(hostRef.current);
    try {
      const probe = document.createElement('canvas');
      const context = probe.getContext('webgl2');
      setSupported(!!context);
      context?.getExtension('WEBGL_lose_context')?.loseContext();
    } catch { setSupported(false); }
    return () => {
      preference.removeEventListener('change', onPreference);
      document.removeEventListener('visibilitychange', onVisibility);
      observer?.disconnect();
    };
  }, []);

  return (
    <div ref={hostRef} className={`${className} hero-gradient-fallback`} aria-hidden="true">
      {supported && !reducedMotion && !failed && (
        <SceneBoundary>
          <Canvas
            dpr={1}
            gl={{ antialias: false, alpha: false, powerPreference: 'low-power' }}
            frameloop={visible && documentVisible ? 'always' : 'never'}
            fallback={null}
          >
            <ContextLoss onLost={() => setFailed(true)} />
            <GradientField />
          </Canvas>
        </SceneBoundary>
      )}
    </div>
  );
}

// Own the listener in an effect so StrictMode and route exit remove it.
function ContextLoss({ onLost }: { onLost: () => void }) {
  const canvas = useThree((state) => state.gl.domElement);
  useEffect(() => {
    const lost = (event: Event) => { event.preventDefault(); onLost(); };
    canvas.addEventListener('webglcontextlost', lost);
    return () => canvas.removeEventListener('webglcontextlost', lost);
  }, [canvas, onLost]);
  return null;
}

export default HeroScene;
