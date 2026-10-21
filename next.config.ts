import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // the pg driver and Prisma's generated client run on the server only
  serverExternalPackages: ["pg", "@prisma/adapter-pg"],
  // On Vercel, /api/py is the Python function in api/py.py. Locally, `npm run dev:py` serves it on port 8001.
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    return [{ source: "/api/py", destination: "http://127.0.0.1:8001/api/py" }];
  },
};

export default nextConfig;
