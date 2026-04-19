import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

// Dev-only proxy for the agent API. In production CloudFront fronts both
// the static dashboard and the agent Lambda under the same origin, so a
// browser request to `/api/agent/*` is same-origin. Locally we forward to
// the dev CloudFront so the same path works without CORS preflight.
//
// Set VITE_AGENT_PROXY_TARGET in `.env.development.local` (gitignored).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const agentTarget = env.VITE_AGENT_PROXY_TARGET;

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: agentTarget
      ? {
          proxy: {
            "/api/agent": {
              target: agentTarget,
              changeOrigin: true,
              secure: true,
            },
          },
        }
      : undefined,
  };
});
