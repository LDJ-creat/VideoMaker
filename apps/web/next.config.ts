import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@videomaker/contracts"],
};

export default nextConfig;
