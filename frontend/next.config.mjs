/** @type {import('next').NextConfig} */
const backend = process.env.API_SERVER_URL || "http://127.0.0.1:8000";
if (process.env.VERCEL && (!process.env.API_SERVER_URL || !backend.startsWith("https://"))) {
  throw new Error("Set API_SERVER_URL to your reachable HTTPS backend before deploying to Vercel.");
}
const nextConfig = {
  async headers() { return [{ source: "/api/:path*", headers: [{key:"Cache-Control",value:"private, no-store"}] }]; },
  distDir: process.env.NEXT_BUILD_DIR || ".next",
  async rewrites() { return [{ source: "/api/:path*", destination: `${backend.replace(/\/$/, "")}/:path*` }]; },
  experimental: { proxyTimeout: 120000 },
  reactStrictMode: true,
  poweredByHeader: false
};
export default nextConfig;
