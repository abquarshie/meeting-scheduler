import type { NextConfig } from "next";

// Sent with every page: no framing by other sites, no guessing file types, and no camera, microphone or location.
const SECURITY_HEADERS = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
  // the pg driver and Prisma's generated client run on the server only
  serverExternalPackages: ["pg", "@prisma/adapter-pg"],
  // On Vercel, /api/py is the Python function in api/py.py. Locally, `npm run dev:py` serves it on port 8001.
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    return [{ source: "/api/py", destination: "http://127.0.0.1:8001/api/py" }];
  },
};

export default nextConfig;
