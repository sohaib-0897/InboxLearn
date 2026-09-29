import React, { useRef, useMemo, useState, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useSpring, animated } from '@react-spring/web';
import { ShieldCheck, Cpu, ArrowUpRight } from 'lucide-react';

/**
 * Custom GLSL Shaders for the 4,096-Dimensional Classification Manifold
 * Creates a topographical probability surface in warm terracotta, cream, and ink.
 */
const manifoldVertexShader = `
  uniform float uTime;
  uniform vec2 uPointer;
  varying vec2 vUv;
  varying float vElevation;

  void main() {
    vUv = uv;
    
    // Wave formula representing probability decision boundary surface
    float freq = 2.4;
    float wave1 = sin(position.x * freq + uTime * 0.8) * cos(position.y * freq + uTime * 0.6);
    float wave2 = sin(position.x * freq * 1.8 - uTime * 0.4) * sin(position.y * freq * 1.8 + uTime * 0.5) * 0.4;
    
    // Pointer influence
    float distToPointer = length(uv - (uPointer * 0.5 + 0.5));
    float pointerWave = exp(-distToPointer * 4.0) * sin(distToPointer * 10.0 - uTime * 2.0) * 0.2;
    
    float elevation = (wave1 + wave2 + pointerWave) * 0.38;
    vElevation = elevation;

    vec3 pos = position;
    pos.z += elevation;

    gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
  }
`;

const manifoldFragmentShader = `
  uniform float uTime;
  varying vec2 vUv;
  varying float vElevation;

  void main() {
    // Warm terracotta to carbon ink palette
    vec3 colorTerracotta = vec3(0.612, 0.231, 0.106); // #9c3b1b
    vec3 colorAmber      = vec3(0.784, 0.490, 0.271); // #c87d45
    vec3 colorPaper      = vec3(0.969, 0.961, 0.941); // #f7f5f0
    vec3 colorInk        = vec3(0.098, 0.090, 0.082); // #191715

    float t = smoothstep(-0.35, 0.35, vElevation);
    
    vec3 baseColor;
    if (t < 0.45) {
      baseColor = mix(colorTerracotta, colorAmber, t / 0.45);
    } else {
      baseColor = mix(colorAmber, colorPaper, (t - 0.45) / 0.55);
    }

    // Topographic contour lines
    float contour = fract(vElevation * 8.0);
    float line = smoothstep(0.0, 0.08, contour) - smoothstep(0.08, 0.16, contour);
    baseColor = mix(baseColor, colorInk, line * 0.6);

    // Subtle edge vignette
    float edge = 1.0 - smoothstep(0.35, 0.5, length(vUv - 0.5));
    
    gl_FragColor = vec4(baseColor, edge * 0.95);
  }
`;

function ManifoldMesh({ pointer }: { pointer: { x: number; y: number } }) {
  const meshRef = useRef<THREE.Mesh>(null);
  
  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uPointer: { value: new THREE.Vector2(0, 0) },
  }), []);

  useFrame((state) => {
    uniforms.uTime.value = state.clock.elapsedTime;
    uniforms.uPointer.value.lerp(new THREE.Vector2(pointer.x, pointer.y), 0.05);

    if (meshRef.current) {
      meshRef.current.rotation.z = state.clock.elapsedTime * 0.04;
    }
  });

  return (
    <mesh ref={meshRef} rotation={[-Math.PI / 3, 0, Math.PI / 6]} position={[0, -0.1, 0]}>
      <planeGeometry args={[4.2, 4.2, 80, 80]} />
      <shaderMaterial
        vertexShader={manifoldVertexShader}
        fragmentShader={manifoldFragmentShader}
        uniforms={uniforms}
        wireframe={false}
        transparent={true}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

export function HeroManifold3D() {
  const [pointer, setPointer] = useState({ x: 0, y: 0 });
  const [hasWebGL, setHasWebGL] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  // Spring physics for card hover tilt
  const [cardSpring, cardApi] = useSpring(() => ({
    rotateX: 0,
    rotateY: 0,
    scale: 1,
    config: { mass: 1.2, tension: 240, friction: 26 },
  }));

  const prefersReducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;

  useEffect(() => {
    try {
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
      if (!gl) setHasWebGL(false);
    } catch {
      setHasWebGL(false);
    }
  }, []);

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!containerRef.current || prefersReducedMotion) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
    setPointer({ x, y });

    // Subtle 3D card tilt
    cardApi.start({
      rotateX: y * 4,
      rotateY: x * 6,
      scale: 1.01,
    });
  };

  const handlePointerLeave = () => {
    setPointer({ x: 0, y: 0 });
    cardApi.start({
      rotateX: 0,
      rotateY: 0,
      scale: 1,
    });
  };

  return (
    <animated.div
      ref={containerRef}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
      style={{
        transform: prefersReducedMotion
          ? undefined
          : cardSpring.scale.to(
              (s) =>
                `perspective(1000px) rotateX(${cardSpring.rotateX.get()}deg) rotateY(${cardSpring.rotateY.get()}deg) scale(${s})`
            ),
      }}
      className="w-full max-w-lg mx-auto bg-paper-sheet border-2 border-ink shadow-paper-raised relative select-none"
    >
      {/* Editorial Card Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-ink bg-paper-subtle text-xs font-mono">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-rust inline-block" />
          <span className="font-bold text-ink uppercase tracking-wider text-[11px]">
            Feature Manifold
          </span>
        </div>
        <span className="text-[10px] text-ink-muted">
          4,096 DIMS · L2 NORMALIZED
        </span>
      </div>

      {/* 3D Canvas / Topographic Stage */}
      <div className="relative h-64 sm:h-72 w-full bg-[#fdfbf7] overflow-hidden flex items-center justify-center">
        {hasWebGL && !prefersReducedMotion ? (
          <Canvas
            camera={{ position: [0, 2.6, 2.8], fov: 48 }}
            dpr={[1, 1.5]}
            gl={{ antialias: true, alpha: true }}
            style={{ width: '100%', height: '100%' }}
          >
            <ManifoldMesh pointer={pointer} />
          </Canvas>
        ) : (
          /* Graceful Topographical Fallback */
          <div className="w-full h-full p-6 flex flex-col justify-between hero-gradient-fallback relative">
            <svg
              className="absolute inset-0 w-full h-full opacity-40"
              viewBox="0 0 400 300"
              fill="none"
              stroke="#9c3b1b"
              strokeWidth="1"
            >
              <path d="M 20,150 Q 100,60 200,150 T 380,150" strokeDasharray="3 3" />
              <path d="M 20,170 Q 120,90 220,160 T 380,170" />
              <path d="M 20,190 Q 140,120 240,170 T 380,190" strokeWidth="1.5" />
              <path d="M 20,210 Q 160,150 260,190 T 380,210" />
              <circle cx="200" cy="150" r="4" fill="#9c3b1b" />
              <circle cx="240" cy="170" r="3" fill="#191715" />
            </svg>
            <div className="relative z-10 font-mono text-[11px] text-ink-muted">
              <span className="block font-bold text-ink">TOPOGRAPHICAL CONTOUR</span>
              <span>Stateless SGD Decision Plane</span>
            </div>
            <div className="relative z-10 flex items-center justify-between text-[10px] font-mono text-ink-muted">
              <span>Class Boundary [bills / spam]</span>
              <span>Threshold: 0.70</span>
            </div>
          </div>
        )}

        {/* Floating Telemetry Stamp */}
        <div className="absolute bottom-2.5 right-2.5 bg-paper-sheet/95 border border-paper-border px-2.5 py-1 text-[10px] font-mono text-ink shadow-sm pointer-events-none">
          <span className="text-rust font-semibold">Dual SGD</span> · log-loss
        </div>
      </div>

      {/* Real Model Probe Telemetry Footprint */}
      <div className="p-4 border-t border-ink bg-paper divide-y divide-paper-border text-xs font-mono">
        <div className="pb-2.5 flex items-start justify-between gap-2">
          <div>
            <span className="text-[10px] text-ink-faint block uppercase">PROBE INPUT</span>
            <span className="font-sans font-semibold text-ink text-xs line-clamp-1">
              "AWS Invoice Available: $3,420.50 for GPU Usage"
            </span>
          </div>
          <span className="px-1.5 py-0.5 bg-amber-100 border border-amber-300 text-amber-900 text-[10px] font-semibold flex-shrink-0">
            NEEDS REVIEW
          </span>
        </div>

        <div className="pt-2.5 grid grid-cols-2 gap-3 text-[11px]">
          <div>
            <span className="text-ink-faint block text-[10px]">CATEGORY CONFIDENCE</span>
            <div className="flex items-center gap-1.5 mt-0.5">
              <div className="flex-1 bg-paper-border h-1.5 overflow-hidden">
                <div className="bg-rust h-full" style={{ width: '57.7%' }} />
              </div>
              <span className="font-bold text-ink">57.7%</span>
            </div>
            <span className="text-[10px] text-ink-muted">Threshold: 70%</span>
          </div>

          <div>
            <span className="text-ink-faint block text-[10px]">SYSTEM ACTION</span>
            <span className="font-bold text-ink block mt-0.5">Diverted to Desk</span>
            <span className="text-[10px] text-ink-muted">Awaiting confirmation</span>
          </div>
        </div>
      </div>
    </animated.div>
  );
}

export default HeroManifold3D;
