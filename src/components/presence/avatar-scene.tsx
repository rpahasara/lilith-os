"use client";

import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useLoader } from "@react-three/fiber";
import { VRMLoaderPlugin, type VRM } from "@pixiv/three-vrm";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { PresenceSignal } from "@/lib/presence";

const AVATAR_URL = "/assets/avatars/Hsin_FINAL_EXPORT_WORKING_FIXED.vrm";

type MaterialAssignment = {
  mesh: THREE.Mesh;
  material: THREE.Material | THREE.Material[];
};

function createBasicMaterialFallback(source: THREE.Material) {
  const mtoon = source as THREE.Material & {
    isMToonMaterial?: boolean;
    color?: THREE.Color;
    map?: THREE.Texture | null;
    alphaMap?: THREE.Texture | null;
    ignoreVertexColor?: boolean;
  };
  const fallback = new THREE.MeshBasicMaterial({
    color: mtoon.color?.clone() ?? new THREE.Color(0xffffff),
    map: mtoon.map ?? null,
    alphaMap: mtoon.alphaMap ?? null,
  });

  // Copy render-state values explicitly. The texture objects are intentionally
  // shared and never mutated, so their loader-assigned color spaces stay intact.
  fallback.name = `${source.name || "MToon"} [MeshBasic fallback]`;
  fallback.opacity = source.opacity;
  fallback.transparent = source.transparent;
  fallback.alphaTest = source.alphaTest;
  fallback.alphaHash = source.alphaHash;
  fallback.alphaToCoverage = source.alphaToCoverage;
  fallback.side = source.side;
  fallback.shadowSide = source.shadowSide;
  fallback.depthTest = source.depthTest;
  fallback.depthWrite = source.depthWrite;
  fallback.depthFunc = source.depthFunc;
  fallback.colorWrite = source.colorWrite;
  fallback.blending = source.blending;
  fallback.blendSrc = source.blendSrc;
  fallback.blendDst = source.blendDst;
  fallback.blendEquation = source.blendEquation;
  fallback.blendSrcAlpha = source.blendSrcAlpha;
  fallback.blendDstAlpha = source.blendDstAlpha;
  fallback.blendEquationAlpha = source.blendEquationAlpha;
  fallback.premultipliedAlpha = source.premultipliedAlpha;
  fallback.dithering = source.dithering;
  fallback.polygonOffset = source.polygonOffset;
  fallback.polygonOffsetFactor = source.polygonOffsetFactor;
  fallback.polygonOffsetUnits = source.polygonOffsetUnits;
  fallback.clippingPlanes = source.clippingPlanes;
  fallback.clipIntersection = source.clipIntersection;
  fallback.clipShadows = source.clipShadows;
  fallback.stencilWrite = source.stencilWrite;
  fallback.stencilWriteMask = source.stencilWriteMask;
  fallback.stencilFunc = source.stencilFunc;
  fallback.stencilRef = source.stencilRef;
  fallback.stencilFuncMask = source.stencilFuncMask;
  fallback.stencilFail = source.stencilFail;
  fallback.stencilZFail = source.stencilZFail;
  fallback.stencilZPass = source.stencilZPass;
  fallback.toneMapped = source.toneMapped;
  fallback.visible = source.visible;
  fallback.vertexColors = mtoon.ignoreVertexColor !== true;
  fallback.userData = { ...source.userData, mtoonFallbackSource: source.name };

  return fallback;
}

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

  useLayoutEffect(() => {
    const fallbacks = new Map<THREE.Material, THREE.MeshBasicMaterial>();
    const assignments: MaterialAssignment[] = [];

    vrm.scene.traverse((object) => {
      if (!(object instanceof THREE.Mesh)) return;

      const original = object.material;
      const materials = Array.isArray(original) ? original : [original];
      if (
        !materials.some(
          (material) =>
            (material as THREE.Material & { isMToonMaterial?: boolean })
              .isMToonMaterial === true,
        )
      ) {
        return;
      }

      assignments.push({ mesh: object, material: original });
      object.material = materials.map((material) => {
        if (
          (material as THREE.Material & { isMToonMaterial?: boolean })
            .isMToonMaterial !== true
        ) {
          return material;
        }
        let fallback = fallbacks.get(material);
        if (!fallback) {
          fallback = createBasicMaterialFallback(material);
          fallbacks.set(material, fallback);
        }
        return fallback;
      });
      if (!Array.isArray(original)) object.material = object.material[0];
    });

    const diagnostics = [...fallbacks].map(([source, fallback]) => ({
      material: source.name,
      sourceType: "MToonMaterial",
      fallbackType: fallback.type,
      hasBaseColorMap: Boolean(fallback.map),
      textureColorSpace: fallback.map?.colorSpace ?? "none",
      alphaTest: fallback.alphaTest,
      transparent: fallback.transparent,
      side: fallback.side === THREE.DoubleSide ? "DoubleSide" : fallback.side,
    }));
    console.table(diagnostics);
    console.info(
      `[Hsin material fallback] ${JSON.stringify(diagnostics)}`,
    );

    return () => {
      assignments.forEach(({ mesh, material }) => {
        mesh.material = material;
      });
      fallbacks.forEach((material) => material.dispose());
    };
  }, [vrm]);

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
