"use client";

import { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useLoader } from "@react-three/fiber";
import { VRMLoaderPlugin, type VRM } from "@pixiv/three-vrm";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { PresenceSignal } from "@/lib/presence";

const AVATAR_URL = "/assets/avatars/Hsin_FINAL_EXPORT_WORKING_FIXED.vrm";

/**
 * First-pass VRM renderer. Presence signals continue to drive subtle whole-body
 * motion, while expressions, gaze, blinking, springs, and optimization remain
 * intentionally disabled for the next integration phases.
 */
function HsinAvatar({ signal }: { signal: PresenceSignal }) {
  const rig = useRef<THREE.Group>(null);
  const time = useRef(0);
  const gltf = useLoader(GLTFLoader, AVATAR_URL, (loader) => {
    loader.register((parser) => new VRMLoaderPlugin(parser));
  });
  const vrm = gltf.userData.vrm as VRM;

  const framing = useMemo(() => {
    const scene = vrm.scene;
    scene.updateMatrixWorld(true);

    // Normalize the imported model to a predictable full-body frame without
    // modifying the source VRM or its skeleton hierarchy.
    const bounds = new THREE.Box3().setFromObject(scene);
    const size = bounds.getSize(new THREE.Vector3());
    const center = bounds.getCenter(new THREE.Vector3());
    const scale = size.y > 0 ? 2.75 / size.y : 1;

    return {
      scale,
      position: new THREE.Vector3(
        -center.x * scale,
        -center.y * scale,
        -center.z * scale,
      ),
    };
  }, [vrm]);

  useFrame((_, delta) => {
    if (!rig.current) return;

    const d = Math.min(delta, 0.05);
    time.current += d;
    const t = time.current;
    vrm.materials?.forEach((material) => {
      const updatable = material as THREE.Material & {
        update?: (frameDelta: number) => void;
      };
      updatable.update?.(d);
    });
    const listening = signal.activity === "listening" ? 1 : 0;
    const thinking = signal.activity === "thinking" ? 1 : 0;
    const speaking = signal.activity === "speaking" ? 1 : 0;

    const targetLean = listening * 0.035 - thinking * 0.018 + speaking * 0.012;
    const targetTilt = thinking * 0.025;
    rig.current.rotation.x = THREE.MathUtils.damp(
      rig.current.rotation.x,
      targetLean,
      3,
      d,
    );
    rig.current.rotation.z = THREE.MathUtils.damp(
      rig.current.rotation.z,
      targetTilt + Math.sin(t * 0.55) * 0.006,
      3,
      d,
    );
    rig.current.position.y = Math.sin(t * (speaking ? 1.25 : 0.8)) * 0.008;
  });

  return (
    <group ref={rig}>
      <group scale={framing.scale} position={framing.position}>
        <primitive object={vrm.scene} />
      </group>
    </group>
  );
}

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
      camera={{ position: [0, 0, 4.25], fov: 36 }}
      dpr={[1, 2]}
      frameloop={paused ? "never" : "always"}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      style={{ background: "transparent" }}
    >
      <ambientLight intensity={1.1} />
      <directionalLight position={[-3, 4, 3]} intensity={2.2} color="#ffffff" />
      <directionalLight position={[3, 1, 2]} intensity={1.2} color="#bdefff" />
      <HsinAvatar signal={signal} />
    </Canvas>
  );
}

useLoader.preload(GLTFLoader, AVATAR_URL, (loader) => {
  loader.register((parser) => new VRMLoaderPlugin(parser));
});
