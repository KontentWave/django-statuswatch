import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";
import { fileURLToPath, URL } from "node:url";
import fs from "fs";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxyTarget =
    env.VITE_API_BASE ??
    env.VITE_BACKEND_ORIGIN ??
    env.VITE_BACKEND_PROXY ??
    "http://127.0.0.1:8001"; // Default to Django on 8001

  // SSL certificate paths (update these to your actual paths)
  const certPath = env.VITE_SSL_CERT || "/path/to/your/cert.pem";
  const keyPath = env.VITE_SSL_KEY || "/path/to/your/key.pem";

  // Check if SSL files exist
  const useHttps = fs.existsSync(certPath) && fs.existsSync(keyPath);

  console.log("🔧 Vite Config:", {
    proxyTarget,
    useHttps,
    certPath: useHttps ? certPath : "not using HTTPS",
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
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
        },
      },
    },
  };
});
