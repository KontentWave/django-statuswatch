import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";
import { fileURLToPath, URL } from "node:url";
import fs from "fs";
import type { IncomingMessage } from "node:http";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  // SSL certificate paths (update these to your actual paths)
  const certPath = env.VITE_SSL_CERT || "/path/to/your/cert.pem";
  const keyPath = env.VITE_SSL_KEY || "/path/to/your/key.pem";

  // Check if SSL files exist
  const useHttps = fs.existsSync(certPath) && fs.existsSync(keyPath);

  console.log("🔧 Vite Config:", {
    mode,
    useHttps,
    certPath: useHttps ? certPath : "not using HTTPS",
    note: "Dynamic proxy - extracts tenant from request Host header",
  });

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    server: {
      https: useHttps
        ? {
            cert: fs.readFileSync(certPath),
            key: fs.readFileSync(keyPath),
          }
        : undefined,
      // Dynamic proxy based on incoming request Host header
      // Examples:
      //   localhost:5173/api → localhost:8001/api
      //   acme.localhost:5173/api → acme.localhost:8001/api
      //   marcepokus.localhost:5173/api → marcepokus.localhost:8001/api
      proxy: {
        "/api": {
          target: "http://localhost:8000", // Default fallback
          changeOrigin: false, // CRITICAL: Preserve Host header with tenant subdomain
          secure: false,
          // Dynamic router: extract tenant from Host header and route to correct backend
          router: (req: IncomingMessage) => {
            const host = req.headers.host || "localhost:5173";
            const hostname = host.split(":")[0]; // Remove port

            // Extract tenant subdomain
            const parts = hostname.split(".");

            // If no subdomain (just "localhost"), route to localhost:8001
            if (hostname === "localhost") {
              return "http://localhost:8000";
            }

            // If subdomain exists (e.g., "acme.localhost"), route to tenant backend
            if (parts.length >= 2 && parts[parts.length - 1] === "localhost") {
              const tenant = parts[0];
              return `http://${tenant}.localhost:8000`;
            }

            // Fallback for any other domain
            return "http://localhost:8000";
          },
        },
      },
    },
  };
});
