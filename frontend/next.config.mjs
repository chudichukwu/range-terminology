/** @type {import('next').NextConfig} */
const nextConfig = {
  distDir: process.env.NEXT_BUILD_DIR || ".next",
  async rewrites() { return [{ source: "/api/:path*", destination: `${process.env.API_SERVER_URL || "http://127.0.0.1:8000"}/:path*` }]; },
  experimental: { proxyTimeout: 120000 },
  reactStrictMode: true,
  poweredByHeader: false
};
export default nextConfig;
