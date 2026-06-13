/**
 * Scientra Copilot — Unified Dev Launcher
 *
 * Starts the Python API server (port 8710) first, waits for it to be healthy,
 * then launches Next.js dev server. One Ctrl+C stops both.
 *
 * Usage:
 *   node scripts/dev-launcher.js              # start both
 *   node scripts/dev-launcher.js --web-only   # only Next.js
 *   node scripts/dev-launcher.js --api-only   # only API server
 */

const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const PROJECT_ROOT = path.resolve(__dirname, "..", "..");
const API_PORT = process.env.SCIENTRA_API_PORT || "8710";
const WEB_PORT = process.env.SCIENTRA_WEB_PORT || "3000";
const API_URL = `http://127.0.0.1:${API_PORT}`;

const args = process.argv.slice(2);
const webOnly = args.includes("--web-only");
const apiOnly = args.includes("--api-only");

let apiProcess = null;
let webProcess = null;

function log(label, msg) {
  const ts = new Date().toLocaleTimeString("en-US", { hour12: false });
  console.log(`\x1b[90m${ts}\x1b[0m \x1b[36m[${label}]\x1b[0m ${msg}`);
}

function checkApiHealth() {
  return new Promise((resolve) => {
    const req = http.get(`${API_URL}/health`, (res) => {
      let body = "";
      res.on("data", (d) => (body += d));
      res.on("end", () => {
        try {
          const data = JSON.parse(body);
          resolve(data.api_status === "ok");
        } catch {
          resolve(false);
        }
      });
    });
    req.on("error", () => resolve(false));
    req.setTimeout(3000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForApi(maxWait = 30) {
  const start = Date.now();
  while (Date.now() - start < maxWait * 1000) {
    if (await checkApiHealth()) return true;
    await new Promise((r) => setTimeout(r, 1500));
  }
  return false;
}

function cleanup() {
  log("launcher", "Shutting down...");
  if (webProcess) {
    webProcess.kill("SIGTERM");
    webProcess = null;
  }
  if (apiProcess) {
    apiProcess.kill("SIGTERM");
    apiProcess = null;
  }
  process.exit(0);
}

process.on("SIGINT", cleanup);
process.on("SIGTERM", cleanup);
process.on("exit", cleanup);

async function main() {
  console.log("");
  console.log("  \x1b[1;36mScientra Copilot — Dev Launcher\x1b[0m");
  console.log("  \x1b[90m──────────────────────────────\x1b[0m");
  console.log("");

  // ── Start API server ──
  if (!webOnly) {
    // Check if already running
    const alreadyHealthy = await checkApiHealth();
    if (alreadyHealthy) {
      log("api", `Already running on port ${API_PORT}`);
    } else {
      log("api", "Starting API server...");

      const pythonCmd = process.platform === "win32" ? "python" : "python3";
      apiProcess = spawn(pythonCmd, [
        path.join(PROJECT_ROOT, "Scripts", "run_api_server.py"),
        "--port", API_PORT,
        "--host", "127.0.0.1",
        "--reload",
      ], {
        cwd: PROJECT_ROOT,
        stdio: "pipe",
        env: { ...process.env, SCIENTRA_ROOT: PROJECT_ROOT },
      });

      apiProcess.stdout.on("data", (d) => {
        const lines = d.toString().trim().split("\n");
        for (const line of lines) {
          if (line.includes("Uvicorn running") || line.includes("Application startup")) {
            log("api", "Server starting...");
          }
        }
      });

      apiProcess.stderr.on("data", (d) => {
        const text = d.toString().trim();
        if (text && !text.includes("Warning")) {
          log("api", text.slice(0, 200));
        }
      });

      apiProcess.on("error", (err) => {
        log("api", `Failed to start: ${err.message}`);
        log("api", "Make sure Python 3.11+ and dependencies are installed:");
        log("api", "  pip install fastapi uvicorn pyyaml");
      });

      apiProcess.on("exit", (code) => {
        if (code !== null && code !== 0 && !webProcess) {
          log("api", `Process exited (code ${code})`);
        }
      });

      // Wait for health
      log("api", `Waiting for /health on port ${API_PORT}...`);
      const ready = await waitForApi(30);
      if (ready) {
        log("api", `Ready — ${API_URL}/health`);
      } else {
        log("api", "WARNING: API did not respond within 30s. Check for errors above.");
        log("api", "Web frontend will start anyway — some features will be unavailable.");
      }
    }
  }

  // ── Start Web frontend ──
  if (!apiOnly) {
    // Small delay to let API settle
    await new Promise((r) => setTimeout(r, 1000));

    const npmCmd = process.platform === "win32" ? "npm.cmd" : "npm";
    log("web", "Starting Next.js dev server...");

    webProcess = spawn(npmCmd, ["run", "next:dev"], {
      cwd: path.join(PROJECT_ROOT, "web"),
      stdio: "inherit",
      env: {
        ...process.env,
        NEXT_PUBLIC_SCIENTRA_API_URL: API_URL,
        NEXT_PUBLIC_SCIENTRA_API_PORT: API_PORT,
      },
    });

    webProcess.on("error", (err) => {
      log("web", `Failed to start: ${err.message}`);
      log("web", "Make sure Node.js is installed. Try: npm run dev");
    });

    webProcess.on("exit", (code) => {
      if (code !== null && code !== 0) {
        log("web", `Process exited (code ${code})`);
      }
      // If web exits, clean up everything
      cleanup();
    });
  }

  // Keep process alive
  if (apiOnly && apiProcess) {
    process.stdin.resume();
  } else if (!webProcess) {
    log("launcher", "Nothing to run. Use --web-only or --api-only.");
    process.exit(0);
  }
}

main().catch((err) => {
  console.error("Launcher error:", err);
  process.exit(1);
});
