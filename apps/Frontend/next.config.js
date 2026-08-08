const path = require("path");

const repoRoot = path.resolve(__dirname, "../..");

/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingRoot: repoRoot,
  turbopack: {
    root: repoRoot,
  },
};

module.exports = nextConfig;
