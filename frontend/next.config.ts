import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A stray package-lock.json in the home directory makes Next infer the
  // wrong workspace root; pin it explicitly.
  outputFileTracingRoot: __dirname,
};

export default nextConfig;
