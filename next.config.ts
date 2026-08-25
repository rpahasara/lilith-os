import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // React Compiler is disabled: react-three-fiber relies heavily on mutable
  // refs inside useFrame, and we want fully predictable render behaviour for
  // the 3D presence scene. Re-enable later once the scene is stable.
  reactCompiler: false,
  transpilePackages: ["three"],
};

export default nextConfig;
