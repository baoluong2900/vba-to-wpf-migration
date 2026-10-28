/** @type {import('next').NextConfig} */
const nextConfig = {
  turbopack: {},
  onDemandEntries: {
    maxInactiveAge: 15 * 1000,
    pagesBufferLength: 2,
  },
  // Prevent stale pages after a redeploy: HTML and API responses are never cached.
  // /_next/* is excluded on purpose — Next.js already serves hashed static assets
  // as immutable, and overriding Cache-Control there breaks dev mode (and would
  // otherwise force no-store onto every JS/CSS chunk).
  async headers() {
    return [
      {
        source: '/((?!_next/).*)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'no-cache, no-store, must-revalidate',
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
