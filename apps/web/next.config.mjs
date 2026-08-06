/** @type {import('next').NextConfig} */
const originOf = (value) => {
  try {
    return value ? new URL(value).origin : null;
  } catch {
    return null;
  }
};

const supabaseOrigin = originOf(process.env.NEXT_PUBLIC_SUPABASE_URL);
const apiOrigin = originOf(process.env.NEXT_PUBLIC_API_URL);
const connectSources = ["'self'", supabaseOrigin, apiOrigin]
  .filter(Boolean)
  .join(" ");
const scriptSources = process.env.NODE_ENV === "production"
  ? "'self' 'unsafe-inline'"
  : "'self' 'unsafe-inline' 'unsafe-eval'";

const nextConfig = {
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: [
            "default-src 'self'",
            `script-src ${scriptSources}`,
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: blob: https:",
            "font-src 'self' data:",
            `connect-src ${connectSources} wss:`,
            "media-src 'self' blob: https:",
            "worker-src 'self' blob:",
            "manifest-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "object-src 'none'",
          ].join('; ') },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
