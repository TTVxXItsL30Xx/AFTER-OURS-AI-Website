import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  experimental: process.env.NEXT_FORCE_WASM === "1" ? { useWasmBinary: true } : {},
};

export default nextConfig;
