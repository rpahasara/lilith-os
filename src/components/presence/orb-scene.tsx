"use client";

import { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import {
  IDLE_SIGNAL,
  orbParamsFromSignal,
  type PresenceSignal,
} from "@/lib/presence";

/* ---------------------------------------------------------------- shaders */
// Ashima 3D simplex noise — public domain.
const NOISE = /* glsl */ `
vec4 permute(vec4 x){return mod(((x*34.0)+1.0)*x, 289.0);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159 - 0.85373472095314 * r;}
float snoise(vec3 v){
  const vec2 C = vec2(1.0/6.0, 1.0/3.0);
  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
  vec3 i  = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + 1.0 * C.xxx;
  vec3 x2 = x0 - i2 + 2.0 * C.xxx;
  vec3 x3 = x0 - 1.0 + 3.0 * C.xxx;
  i = mod(i, 289.0);
  vec4 p = permute(permute(permute(
             i.z + vec4(0.0, i1.z, i2.z, 1.0))
           + i.y + vec4(0.0, i1.y, i2.y, 1.0))
           + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  float n_ = 1.0/7.0;
  vec3 ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z *ns.z);
  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);
  vec4 x = x_ *ns.x + ns.yyyy;
  vec4 y = y_ *ns.x + ns.yyyy;
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
`;

const VERT = /* glsl */ `
uniform float uTime;
uniform float uAmp;
uniform float uSpeed;
varying float vNoise;
varying vec3 vNormal;
varying vec3 vView;
${NOISE}
void main(){
  vNormal = normalize(normalMatrix * normal);
  float t = uTime * uSpeed;
  float n = snoise(normal * 1.6 + vec3(t * 0.35));
  float n2 = snoise(normal * 3.2 - vec3(t * 0.22));
  float d = (n * 0.7 + n2 * 0.3);
  vNoise = d;
  vec3 pos = position + normal * d * uAmp;
  vec4 mv = modelViewMatrix * vec4(pos, 1.0);
  vView = normalize(-mv.xyz);
  gl_Position = projectionMatrix * mv;
}
`;

const FRAG = /* glsl */ `
uniform vec3 uColorA;
uniform vec3 uColorB;
uniform float uColorMix;
uniform float uIntensity;
varying float vNoise;
varying vec3 vNormal;
varying vec3 vView;
void main(){
  float fres = pow(1.0 - max(dot(vNormal, vView), 0.0), 2.4);
  float mixv = clamp(uColorMix + vNoise * 0.35, 0.0, 1.0);
  vec3 base = mix(uColorA, uColorB, mixv);
  vec3 col = base * (0.35 + vNoise * 0.4);
  col += base * fres * 2.2 * uIntensity;      // rim glow
  col += vec3(1.0) * pow(fres, 5.0) * 0.6;     // hot edge
  float alpha = clamp(0.55 + fres * 0.7, 0.0, 1.0);
  gl_FragColor = vec4(col, alpha);
}
`;

/* ---------------------------------------------------------------- core orb */
function Core({ signal }: { signal: PresenceSignal }) {
  const mat = useRef<THREE.ShaderMaterial>(null);
  const mesh = useRef<THREE.Mesh>(null);

  const idle = orbParamsFromSignal(IDLE_SIGNAL);
  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uAmp: { value: idle.amplitude },
      uSpeed: { value: idle.speed },
      uColorMix: { value: idle.colorMix },
      uIntensity: { value: idle.intensity },
      uColorA: { value: new THREE.Color("#8b5cf6") },
      uColorB: { value: new THREE.Color("#22d3ee") },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  useFrame((_, delta) => {
    const p = orbParamsFromSignal(signal);
    const u = uniforms;
    u.uTime.value += delta;
    // smooth state transitions
    u.uAmp.value = THREE.MathUtils.damp(u.uAmp.value, p.amplitude, 3, delta);
    u.uSpeed.value = THREE.MathUtils.damp(u.uSpeed.value, p.speed, 3, delta);
    u.uColorMix.value = THREE.MathUtils.damp(u.uColorMix.value, p.colorMix, 3, delta);
    u.uIntensity.value = THREE.MathUtils.damp(u.uIntensity.value, p.intensity, 3, delta);
    if (mesh.current) {
      mesh.current.rotation.y += delta * 0.12;
      mesh.current.rotation.x += delta * 0.04;
    }
  });

  return (
    <mesh ref={mesh}>
      <icosahedronGeometry args={[1.15, 64]} />
      <shaderMaterial
        ref={mat}
        uniforms={uniforms}
        vertexShader={VERT}
        fragmentShader={FRAG}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </mesh>
  );
}

/* ---------------------------------------------------------------- particles */
function Halo({ signal }: { signal: PresenceSignal }) {
  const points = useRef<THREE.Points>(null);
  const COUNT = 900;

  const geom = useMemo(() => {
    const positions = new Float32Array(COUNT * 3);
    for (let i = 0; i < COUNT; i++) {
      // distribute on a shell, biased outward
      const r = 1.7 + Math.random() * 1.4;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    return g;
  }, []);

  useFrame((_, delta) => {
    if (!points.current) return;
    const speed = orbParamsFromSignal(signal).speed;
    points.current.rotation.y -= delta * 0.05 * (0.6 + speed);
    points.current.rotation.z += delta * 0.02;
  });

  return (
    <points ref={points} geometry={geom}>
      <pointsMaterial
        size={0.02}
        color="#a9b4ff"
        transparent
        opacity={0.7}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

/* ---------------------------------------------------------------- scene */
export function OrbScene({
  signal,
  paused = false,
}: {
  signal: PresenceSignal;
  paused?: boolean;
}) {
  // This component mounts together with the <canvas> (it arrives via a dynamic
  // import), so nudging a re-measure here — after the canvas exists — reliably
  // sizes the drawing buffer to the container on first paint.
  useEffect(() => {
    const fire = () => window.dispatchEvent(new Event("resize"));
    const raf = requestAnimationFrame(fire);
    const timers = [setTimeout(fire, 150), setTimeout(fire, 400)];
    return () => {
      cancelAnimationFrame(raf);
      timers.forEach(clearTimeout);
    };
  }, []);

  return (
    <Canvas
      camera={{ position: [0, 0, 4.2], fov: 45 }}
      dpr={[1, 2]}
      frameloop={paused ? "never" : "always"}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      style={{ background: "transparent" }}
    >
      <Core signal={signal} />
      <Halo signal={signal} />
    </Canvas>
  );
}
