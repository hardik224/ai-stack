import type { NextConfig } from 'next';

const apiProxyTarget = process.env.API_PROXY_TARGET || 'http://127.0.0.1:2000';

const nextConfig: NextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/proxy/:path*',
        destination: `${apiProxyTarget}/:path*`,
      },
    ];
  },
};

export default nextConfig;
