import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';

const VERTEX_SHADER = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = vec4(position, 1.0);
  }
`;

// Luminous continuous probability & latent manifold shader (basement + shadergradient inspiration)
const FRAGMENT_SHADER = `
  uniform float u_time;
  uniform vec2 u_resolution;
  uniform vec2 u_mouse;
  varying vec2 vUv;

  // Simplex-inspired pseudo-noise
  vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec3 permute(vec3 x) { return mod289(((x*34.0)+1.0)*x); }

  float snoise(vec2 v) {
    const vec4 C = vec4(0.211324865405187,  // (3.0-sqrt(3.0))/6.0
                        0.366025403784439,  // 0.5*(sqrt(3.0)-1.0)
                       -0.577350269189626,  // -1.0 + 2.0 * C.x
                        0.024390243902439); // 1.0 / 41.0
    vec2 i  = floor(v + dot(v, C.yy));
    vec2 x0 = v -   i + dot(i, C.xx);
    vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec4 x12 = x0.xyxy + C.xxzz;
    x12.xy -= i1;
    i = mod289(i);
    vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0)) + i.x + vec3(0.0, i1.x, 1.0));
    vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
    m = m*m;
    m = m*m;
    vec3 x = 2.0 * fract(p * C.www) - 1.0;
    vec3 h = abs(x) - 0.5;
    vec3 ox = floor(x + 0.5);
    vec3 a0 = x - ox;
    m *= 1.79284291400159 - 0.85373472095314 * (a0*a0 + h*h);
    vec3 g;
    g.x  = a0.x  * x0.x  + h.x  * x0.y;
    g.yz = a0.yz * x12.xz + h.yz * x12.yw;
    return 130.0 * dot(m, g);
  }

  void main() {
    vec2 st = gl_FragCoord.xy / u_resolution.xy;
    st.x *= u_resolution.x / u_resolution.y;

    float t = u_time * 0.18;
    vec2 mouse = u_mouse * 0.5;

    // Multi-octave continuous manifold turbulence
    float n1 = snoise(st * 1.4 + vec2(t * 0.4, t * 0.3) + mouse);
    float n2 = snoise(st * 2.2 - vec2(t * 0.2, -t * 0.5) + vec2(n1 * 0.4));
    float n3 = snoise(st * 0.8 + vec2(n2 * 0.5, t * 0.1));

    // Luxury palette: deep obsidian (#050508), electric indigo (#6366f1), violet (#8b5cf6), cyan (#06b6d4)
    vec3 colorBase = vec3(0.02, 0.02, 0.04);
    vec3 colorIndigo = vec3(0.24, 0.25, 0.85);
    vec3 colorViolet = vec3(0.48, 0.22, 0.88);
    vec3 colorCyan = vec3(0.02, 0.65, 0.78);
    vec3 colorAmber = vec3(0.85, 0.45, 0.10);

    float blend1 = smoothstep(-0.6, 0.7, n1);
    float blend2 = smoothstep(-0.4, 0.8, n2);
    float blend3 = smoothstep(-0.2, 0.9, n3);

    vec3 finalColor = mix(colorBase, colorIndigo, blend1 * 0.75);
    finalColor = mix(finalColor, colorViolet, blend2 * 0.6);
    finalColor = mix(finalColor, colorCyan, blend3 * 0.35);

    // Subtle edge amber highlight representing decision boundaries
    float boundary = smoothstep(0.48, 0.52, abs(n2));
    finalColor += colorAmber * (1.0 - boundary) * 0.12;

    // Vignette falloff to deep obsidian at borders
    vec2 uvNorm = vUv * (1.0 - vUv);
    float vignette = clamp(uvNorm.x * uvNorm.y * 15.0, 0.0, 1.0);
    finalColor *= vignette;

    gl_FragColor = vec4(finalColor, 0.85);
  }
`;

export const HeroShader: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hasWebGL, setHasWebGL] = useState<boolean>(true);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState<boolean>(false);

  useEffect(() => {
    // Check reduced motion preference
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReducedMotion(mq.matches);
    const handleMotionChange = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
    mq.addEventListener('change', handleMotionChange);

    // Check WebGL availability
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (!gl) {
      setHasWebGL(false);
      return;
    }

    if (mq.matches) {
      return;
    }

    const container = containerRef.current;
    if (!container) return;

    // Three.js Scene Setup
    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      powerPreference: 'high-performance',
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    const uniforms = {
      u_time: { value: 0 },
      u_resolution: { value: new THREE.Vector2(container.clientWidth, container.clientHeight) },
      u_mouse: { value: new THREE.Vector2(0, 0) },
    };

    const geometry = new THREE.PlaneGeometry(2, 2);
    const material = new THREE.ShaderMaterial({
      vertexShader: VERTEX_SHADER,
      fragmentShader: FRAGMENT_SHADER,
      uniforms,
      transparent: true,
    });

    const mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);

    let animationId: number;
    let isVisible = true;

    // Intersection Observer to pause render loop when off-screen
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        isVisible = entry.isIntersecting;
      });
    }, { threshold: 0.1 });
    observer.observe(container);

    const onPointerMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
      uniforms.u_mouse.value.set(x * 0.5, y * 0.5);
    };
    window.addEventListener('pointermove', onPointerMove, { passive: true });

    const onResize = () => {
      if (!container) return;
      const width = container.clientWidth;
      const height = container.clientHeight;
      renderer.setSize(width, height);
      uniforms.u_resolution.value.set(width, height);
    };
    window.addEventListener('resize', onResize, { passive: true });

    const clock = new THREE.Clock();
    const animate = () => {
      animationId = requestAnimationFrame(animate);
      if (isVisible) {
        uniforms.u_time.value = clock.getElapsedTime();
        renderer.render(scene, camera);
      }
    };
    animate();

    return () => {
      cancelAnimationFrame(animationId);
      observer.disconnect();
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('resize', onResize);
      mq.removeEventListener('change', handleMotionChange);
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      geometry.dispose();
      material.dispose();
      renderer.dispose();
    };
  }, []);

  if (!hasWebGL || prefersReducedMotion) {
    return (
      <div 
        aria-hidden="true" 
        className="absolute inset-0 pointer-events-none opacity-80"
        style={{
          background: 'radial-gradient(ellipse 80% 60% at 50% 20%, rgba(99, 102, 241, 0.25), rgba(139, 92, 246, 0.12) 40%, rgba(5, 5, 8, 0.95) 85%)'
        }}
      />
    );
  }

  return (
    <div 
      ref={containerRef} 
      aria-hidden="true"
      className="absolute inset-0 pointer-events-none overflow-hidden" 
    />
  );
};
