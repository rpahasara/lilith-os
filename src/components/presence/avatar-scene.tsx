"use client";

import { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import {
  IDLE_SIGNAL,
  type Activity,
  type Importance,
  type PresenceSignal,
} from "@/lib/presence";

/**
 * PLACEHOLDER avatar. A feminine bust roughed out from Three.js primitives —
 * head, neck, tapered upper torso, two glowing eyes for face direction. It is
 * deliberately NOT the final LILITH; it exists to validate the renderer seam
 * and state-driven procedural motion. When the real VRM lands, this whole file
 * is replaced by the VRM renderer with zero changes to the engine.
 *
 * No blendshapes, no VRM, no asset loading, no lip-sync, no cursor gaze — that
 * is all later phases. Motion here is pure procedural transforms driven by the
 * normalized {@link PresenceSignal}.
 */

/* ------------------------------------------------------- signal → motion map */
// Renderer-local mapping (mirrors the orb's profiles). Personality lives in
// data, not in the animation loop.
interface AvatarParams {
  lean: number; // forward torso lean (rad)
  headTilt: number; // head roll (rad)
  gazeAmp: number; // head-yaw drift amplitude (rad)
  gazeSpeed: number;
  breatheAmp: number;
  breatheSpeed: number;
  bobAmp: number; // head pitch bob (speaking rhythm)
  bobSpeed: number;
  swayAmp: number; // whole-body roll
  swaySpeed: number;
  eyeGlow: number; // emissive intensity multiplier
  riseY: number; // subtle vertical offset
}

const BY_ACTIVITY: Record<Activity, AvatarParams> = {
  idle: {
    lean: 0, headTilt: 0, gazeAmp: 0.05, gazeSpeed: 0.5,
    breatheAmp: 0.035, breatheSpeed: 0.8, bobAmp: 0, bobSpeed: 2,
    swayAmp: 0.025, swaySpeed: 0.5, eyeGlow: 1.0, riseY: 0,
  },
  listening: {
    lean: 0.14, headTilt: 0, gazeAmp: 0.025, gazeSpeed: 0.8,
    breatheAmp: 0.045, breatheSpeed: 1.2, bobAmp: 0, bobSpeed: 2,
    swayAmp: 0.015, swaySpeed: 0.6, eyeGlow: 1.7, riseY: 0.04,
  },
  thinking: {
    lean: -0.05, headTilt: 0.2, gazeAmp: 0.14, gazeSpeed: 0.45,
    breatheAmp: 0.03, breatheSpeed: 0.7, bobAmp: 0, bobSpeed: 2,
    swayAmp: 0.035, swaySpeed: 0.35, eyeGlow: 1.2, riseY: 0,
  },
  speaking: {
    lean: 0.05, headTilt: 0.02, gazeAmp: 0.04, gazeSpeed: 0.9,
    breatheAmp: 0.05, breatheSpeed: 1.4, bobAmp: 0.06, bobSpeed: 3.2,
    swayAmp: 0.02, swaySpeed: 0.6, eyeGlow: 1.5, riseY: 0.02,
  },
  working: {
    lean: 0.08, headTilt: 0.08, gazeAmp: 0.06, gazeSpeed: 0.7,
    breatheAmp: 0.04, breatheSpeed: 1.1, bobAmp: 0.02, bobSpeed: 2.4,
    swayAmp: 0.025, swaySpeed: 0.5, eyeGlow: 1.3, riseY: 0.01,
  },
  waiting: {
    lean: 0, headTilt: 0.04, gazeAmp: 0.05, gazeSpeed: 0.45,
    breatheAmp: 0.03, breatheSpeed: 0.7, bobAmp: 0, bobSpeed: 2,
    swayAmp: 0.03, swaySpeed: 0.4, eyeGlow: 1.15, riseY: 0,
  },
};

const EYE_GAIN: Record<Importance, number> = {
  passive: 1.0, normal: 1.0, notable: 1.12, urgent: 1.28,
};

function avatarParamsFromSignal(signal: PresenceSignal): AvatarParams {
  const base = BY_ACTIVITY[signal.activity] ?? BY_ACTIVITY.idle;
  return { ...base, eyeGlow: base.eyeGlow * (EYE_GAIN[signal.importance] ?? 1) };
}

/* ------------------------------------------------------------------- the rig */
function Rig({ signal }: { signal: PresenceSignal }) {
  const group = useRef<THREE.Group>(null);
  const torso = useRef<THREE.Mesh>(null);
  const head = useRef<THREE.Group>(null);

  const time = useRef(0);
  const cur = useRef<AvatarParams>({ ...avatarParamsFromSignal(IDLE_SIGNAL) });

  const bodyMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: new THREE.Color("#141a2e"),
        metalness: 0.35,
        roughness: 0.4,
        emissive: new THREE.Color("#3b2a6b"),
        emissiveIntensity: 0.28,
      }),
    [],
  );

  // One shared eye material so a single glow value drives both eyes.
  const eyeMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: new THREE.Color("#04121a"),
        emissive: new THREE.Color("#67e8f9"),
        emissiveIntensity: 2.2,
        toneMapped: false,
      }),
    [],
  );

  useFrame((_, delta) => {
    const d = Math.min(delta, 0.05); // clamp after tab-throttle spikes
    const p = avatarParamsFromSignal(signal);
    const c = cur.current;
    const k = 3;
    // smooth every param toward its target
    c.lean = THREE.MathUtils.damp(c.lean, p.lean, k, d);
    c.headTilt = THREE.MathUtils.damp(c.headTilt, p.headTilt, k, d);
    c.gazeAmp = THREE.MathUtils.damp(c.gazeAmp, p.gazeAmp, k, d);
    c.gazeSpeed = THREE.MathUtils.damp(c.gazeSpeed, p.gazeSpeed, k, d);
    c.breatheAmp = THREE.MathUtils.damp(c.breatheAmp, p.breatheAmp, k, d);
    c.breatheSpeed = THREE.MathUtils.damp(c.breatheSpeed, p.breatheSpeed, k, d);
    c.bobAmp = THREE.MathUtils.damp(c.bobAmp, p.bobAmp, k, d);
    c.bobSpeed = THREE.MathUtils.damp(c.bobSpeed, p.bobSpeed, k, d);
    c.swayAmp = THREE.MathUtils.damp(c.swayAmp, p.swayAmp, k, d);
    c.swaySpeed = THREE.MathUtils.damp(c.swaySpeed, p.swaySpeed, k, d);
    c.eyeGlow = THREE.MathUtils.damp(c.eyeGlow, p.eyeGlow, k, d);
    c.riseY = THREE.MathUtils.damp(c.riseY, p.riseY, k, d);

    time.current += d;
    const t = time.current;

    if (group.current) {
      group.current.rotation.x = c.lean;
      group.current.rotation.z = Math.sin(t * c.swaySpeed) * c.swayAmp;
      group.current.position.y =
        0.1 + c.riseY + Math.sin(t * c.breatheSpeed) * c.breatheAmp * 0.4;
    }
    if (torso.current) {
      const b = Math.sin(t * c.breatheSpeed) * c.breatheAmp;
      torso.current.scale.set(1 + b * 0.25, 1 + b, 1 + b * 0.25);
    }
    if (head.current) {
      head.current.rotation.z = c.headTilt;
      head.current.rotation.y = Math.sin(t * c.gazeSpeed) * c.gazeAmp;
      head.current.rotation.x = Math.sin(t * c.bobSpeed) * c.bobAmp;
    }
    eyeMat.emissiveIntensity = c.eyeGlow * 2.2;
  });

  return (
    <group ref={group}>
      {/* upper torso / shoulders — tapered cylinder */}
      <mesh ref={torso} position={[0, -0.75, 0]} material={bodyMat}>
        <cylinderGeometry args={[0.78, 0.55, 1.3, 32]} />
      </mesh>
      {/* neck */}
      <mesh position={[0, 0.08, 0]} material={bodyMat}>
        <cylinderGeometry args={[0.17, 0.2, 0.34, 24]} />
      </mesh>
      {/* head + eyes (rotate together — gaze) */}
      <group ref={head} position={[0, 0.62, 0]}>
        <mesh material={bodyMat}>
          <sphereGeometry args={[0.5, 48, 48]} />
        </mesh>
        <mesh position={[-0.18, 0.04, 0.44]} material={eyeMat}>
          <sphereGeometry args={[0.07, 20, 20]} />
        </mesh>
        <mesh position={[0.18, 0.04, 0.44]} material={eyeMat}>
          <sphereGeometry args={[0.07, 20, 20]} />
        </mesh>
      </group>
    </group>
  );
}

/* --------------------------------------------------------------------- scene */
export function AvatarScene({
  signal,
  paused = false,
}: {
  signal: PresenceSignal;
  paused?: boolean;
}) {
  // Same first-paint re-measure nudge the orb uses (R3F can miss late layout).
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
      camera={{ position: [0, 0, 4.5], fov: 40 }}
      dpr={[1, 2]}
      frameloop={paused ? "never" : "always"}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      style={{ background: "transparent" }}
    >
      <ambientLight intensity={0.35} />
      <directionalLight position={[-3, 4, 3]} intensity={1.4} color="#a78bfa" />
      <pointLight position={[3, 1, 2]} intensity={18} color="#22d3ee" />
      <pointLight position={[0, 1, -4]} intensity={22} color="#8b5cf6" />
      <Rig signal={signal} />
    </Canvas>
  );
}
