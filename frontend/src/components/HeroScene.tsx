import React, { useRef, useMemo, useEffect, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

/**
 * Vertex and fragment shaders for a warm, organic mesh-gradient effect.
 * Creates an evolving topographic surface that reacts to time —
 * warm terracotta, amber, and cream tones that feel alive without being flashy.
 */
const vertexShader = `
  uniform float uTime;
  varying vec2 vUv;
  varying float vElevation;
  
  // Simplex-inspired noise
  vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 permute(vec4 x) { return mod289(((x*34.0)+10.0)*x); }
  vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
  
  float snoise(vec3 v) {
    const vec2 C = vec2(1.0/6.0, 1.0/3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    vec3 i = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + C.yyy;
    vec3 x3 = x0 - D.yyy;
    i = mod289(i);
    vec4 p = permute(permute(permute(
      i.z + vec4(0.0, i1.z, i2.z, 1.0))
      + i.y + vec4(0.0, i1.y, i2.y, 1.0))
      + i.x + vec4(0.0, i1.x, i2.x, 1.0));
    float n_ = 0.142857142857;
    vec3 ns = n_ * D.wyz - D.xzx;
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    vec4 x = x_ * ns.x + ns.yyyy;
    vec4 y = y_ * ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    vec4 b0 = vec4(x.xy, y.xy);
    vec4 b1 = vec4(x.zw, y.zw);
    vec4 s0 = floor(b0)*2.0 + 1.0;
    vec4 s1 = floor(b1)*2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
    vec3 p0 = vec3(a0.xy, h.x);
    vec3 p1 = vec3(a0.zw, h.y);
    vec3 p2 = vec3(a1.xy, h.z);
    vec3 p3 = vec3(a1.zw, h.w);
    vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
    p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
    vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
    m = m * m;
    return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
  }

  void main() {
    vUv = uv;
    
    float slowTime = uTime * 0.15;
    
    // Layered noise for organic terrain
    float noise1 = snoise(vec3(position.x * 0.8, position.y * 0.8, slowTime));
    float noise2 = snoise(vec3(position.x * 1.6, position.y * 1.6, slowTime * 1.3)) * 0.5;
    float noise3 = snoise(vec3(position.x * 3.2, position.y * 3.2, slowTime * 0.7)) * 0.25;
    
    float elevation = (noise1 + noise2 + noise3) * 0.35;
    vElevation = elevation;
    
    vec3 newPosition = position;
    newPosition.z += elevation;
    
    gl_Position = projectionMatrix * modelViewMatrix * vec4(newPosition, 1.0);
  }
`;

const fragmentShader = `
  uniform float uTime;
  varying vec2 vUv;
  varying float vElevation;

  void main() {
    float slowTime = uTime * 0.1;
    
    // Warm palette: cream → terracotta → deep sienna
    vec3 colorDeep   = vec3(0.42, 0.16, 0.08);   // #6B2914 deep sienna
    vec3 colorMid    = vec3(0.61, 0.23, 0.11);   // #9C3B1B terracotta (rust accent)
    vec3 colorWarm   = vec3(0.82, 0.58, 0.38);   // #D19461 warm amber
    vec3 colorLight  = vec3(0.96, 0.93, 0.88);   // #F5EDE0 warm cream
    
    // Map elevation to color with smooth transitions
    float t = smoothstep(-0.35, 0.35, vElevation);
    
    vec3 color;
    if (t < 0.3) {
      color = mix(colorDeep, colorMid, t / 0.3);
    } else if (t < 0.6) {
      color = mix(colorMid, colorWarm, (t - 0.3) / 0.3);
    } else {
      color = mix(colorWarm, colorLight, (t - 0.6) / 0.4);
    }
    
    // Subtle shimmer along ridges
    float ridge = abs(vElevation) * 2.0;
    color += vec3(0.04, 0.03, 0.02) * ridge;
    
    // Soft vignette toward edges
    float vignette = 1.0 - smoothstep(0.3, 0.85, length(vUv - 0.5));
    color = mix(colorLight * 0.95, color, vignette * 0.8 + 0.2);
    
    gl_FragColor = vec4(color, 1.0);
  }
`;

/** The animated 3D terrain mesh */
function TerrainMesh() {
  const meshRef = useRef<THREE.Mesh>(null);
  const { size } = useThree();
  
  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
  }), []);

  useFrame((state) => {
    uniforms.uTime.value = state.clock.elapsedTime;
  });

  return (
    <mesh ref={meshRef} rotation={[-Math.PI / 2.8, 0, Math.PI / 8]} position={[0, -0.3, 0]}>
      <planeGeometry args={[6, 6, size.width < 640 ? 40 : 80, size.width < 640 ? 40 : 80]} />
      <shaderMaterial
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

interface HeroSceneProps {
  className?: string;
}

/**
 * HeroScene — Renders a warm, organic 3D terrain using custom shaders.
 * Falls back to a static CSS gradient for devices that can't render WebGL.
 * Respects prefers-reduced-motion by pausing animation.
 */
export const HeroScene: React.FC<HeroSceneProps> = ({ className = '' }) => {
  const sceneRef = useRef<HTMLDivElement>(null);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(() =>
    typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches === true,
  );
  const [supportsWebGL, setSupportsWebGL] = useState(false);
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const onPreferenceChange = (event: MediaQueryListEvent) => setPrefersReducedMotion(event.matches);
    if (preference.addEventListener) preference.addEventListener('change', onPreferenceChange);
    else preference.addListener(onPreferenceChange);

    // Canvas can fail before its in-tree fallback is mounted on browsers with
    // WebGL disabled. Probe first so those browsers render the CSS fallback.
    let webglAvailable = false;
    try {
      const probe = document.createElement('canvas');
      const context = probe.getContext('webgl2') || probe.getContext('webgl');
      webglAvailable = context !== null;
      context?.getExtension('WEBGL_lose_context')?.loseContext();
    } catch {
      webglAvailable = false;
    }
    setSupportsWebGL(webglAvailable);

    const scene = sceneRef.current;
    const observer = scene && 'IntersectionObserver' in window
      ? new IntersectionObserver(([entry]) => setIsVisible(entry.isIntersecting), { rootMargin: '80px' })
      : undefined;
    if (scene && observer) observer.observe(scene);

    return () => {
      if (preference.removeEventListener) preference.removeEventListener('change', onPreferenceChange);
      else preference.removeListener(onPreferenceChange);
      observer?.disconnect();
    };
  }, []);

  if (prefersReducedMotion || !supportsWebGL) {
    return <div ref={sceneRef} className={`relative ${className} hero-gradient-fallback`} aria-hidden="true" />;
  }

  return (
    <div ref={sceneRef} className={`relative ${className}`}>
      {/* CSS remains visible if WebGL cannot create a context. */}
      <div 
        className="absolute inset-0 hero-gradient-fallback"
        aria-hidden="true"
      />
      
      {/* 3D Canvas overlay */}
      <div className="absolute inset-0">
        <Canvas
          camera={{ position: [0, 2.5, 3.5], fov: 45 }}
          dpr={[1, 1]}
          gl={{ 
            antialias: false,
            alpha: true,
            powerPreference: 'low-power',
          }}
          frameloop={isVisible ? 'always' : 'demand'}
          fallback={<div className="absolute inset-0 hero-gradient-fallback" aria-hidden="true" />}
          style={{ background: 'transparent' }}
          onCreated={({ gl }) => {
            gl.setClearColor(0x000000, 0);
            gl.domElement.addEventListener('webglcontextlost', () => setSupportsWebGL(false), { once: true });
          }}
        >
          <TerrainMesh />
        </Canvas>
      </div>
    </div>
  );
};

export default HeroScene;
