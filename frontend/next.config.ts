import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  experimental: process.env.NEXT_FORCE_WASM === "1" ? { useWasmBinary: true } : {},
  async rewrites() {
    const backend = process.env.INTERNAL_API_URL || "http://backend:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
