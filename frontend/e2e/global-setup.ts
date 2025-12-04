import { execSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DEFAULT_BACKEND_DIR = path.resolve(__dirname, "..", "..", "backend");
const DEFAULT_MANAGE = path.join(DEFAULT_BACKEND_DIR, "manage.py");

function shouldSkipReset(): boolean {
  return ["1", "true", "TRUE"].includes(
    process.env.PLAYWRIGHT_SKIP_RESET ?? ""
  );
}

export default async function globalSetup(): Promise<void> {
  if (shouldSkipReset()) {
    console.info(
      "[playwright] Skipping reset_e2e_data (PLAYWRIGHT_SKIP_RESET set)"
    );
    return;
  }

  const managePy = process.env.PLAYWRIGHT_MANAGE_PATH ?? DEFAULT_MANAGE;
  const backendDir = path.dirname(managePy);
  const pythonBin = process.env.PLAYWRIGHT_PYTHON_BIN ?? "python";

  console.info("[playwright] Running reset_e2e_data before tests…");
  try {
    execSync(`${pythonBin} ${path.basename(managePy)} reset_e2e_data --force`, {
      cwd: backendDir,
      stdio: "inherit",
    });
  } catch (error) {
    console.error("[playwright] reset_e2e_data failed");
    throw error;
  }
}
