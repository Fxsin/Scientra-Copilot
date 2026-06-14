/**
 * Scientra Copilot — Unified Dev Launcher (v2)
 *
 * Auto-starts API (Python, port 8710) + Web (Next.js, port 3000).
 * Kills stale processes on startup so you never get "port in use" or
 * "old code" problems. One Ctrl+C stops both.
 *
 * Usage:
 *   npm run dev                          # start both (auto-clean)
 *   node scripts/dev-launcher.js         # same
 *   node scripts/dev-launcher.js --web-only
 *   node scripts/dev-launcher.js --api-only
 *   node scripts/dev-launcher.js --force # kill existing & restart
 */

const { spawn, execSync } = require("child_process");
const http = require("http");
const path = require("path");
const net = require("net");

const PROJECT_ROOT = path.resolve(__dirname, "..", "..");
const API_PORT = process.env.SCIENTRA_API_PORT || "8710";
const WEB_PORT = process.env.SCIENTRA_WEB_PORT || "3000";
const API_URL = `http://127.0.0.1:${API_PORT}`;
const WEB_URL = `http://localhost:${WEB_PORT}`;

const args = process.argv.slice(2);
const webOnly = args.includes("--web-only");
const apiOnly = args.includes("--api-only");
const force = args.includes("--force");

let apiProcess = null;
let webProcess = null;

function log(label, msg) {
  const ts = new Date().toLocaleTimeString("en-US", { hour12: false });
  console.log(`\x1b[90m${ts}\x1b[0m \x1b[36m[${label}]\x1b[0m ${msg}`);
}

function warn(msg) {
  console.log(`\x1b[33m  ⚠ ${msg}\x1b[0m`);
}

/* ── Port utilities ── */

function isPortInUse(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(true));
    server.once("listening", () => { server.close(); resolve(false); });
    server.listen(port, "127.0.0.1");
  });
}

function findPidOnPort(port) {
  try {
    const out = execSync(`netstat -ano | findstr ":${port}" | findstr "LISTENING"`, {
      encoding: "utf8", timeout: 5000, windowsHide: true,
    });
    const match = out.trim().split(/\s+/);
    const pid = match[match.length - 1];
    return pid ? parseInt(pid) : null;
  } catch {
    return null;
  }
}

function killProcess(pid) {
  try {
    if (process.platform === "win32") {
      execSync(`taskkill /PID ${pid} /F`, { timeout: 5000, windowsHide: true });
    } else {
      process.kill(pid, "SIGTERM");
    }
    return true;
  } catch {
    return false;
  }
}

/* ── HTTP health checks ── */

function httpGet(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      let body = "";
      res.on("data", (d) => (body += d));
      res.on("end", () => {
        try { resolve({ ok: res.statusCode < 400, body: JSON.parse(body) }); }
        catch { resolve({ ok: res.statusCode < 400 }); }
      });
    });
    req.on("error", () => resolve({ ok: false }));
    req.setTimeout(3000, () => { req.destroy(); resolve({ ok: false }); });
  });
}

async function checkApiHealth() {
  const r = await httpGet(`${API_URL}/health`);
  return r.ok && r.body?.api_status === "ok";
}

async function cleanup() {
  log("launcher", "Shutting down...");
  if (webProcess) { webProcess.kill("SIGTERM"); webProcess = null; }
  if (apiProcess) { apiProcess.kill("SIGTERM"); apiProcess = null; }
  process.exit(0);
}

process.on("SIGINT", cleanup);
process.on("SIGTERM", cleanup);

/* ── Auto-clean stale processes ── */

async function ensurePortFree(port, label, healthCheck) {
  const inUse = await isPortInUse(port);
  if (!inUse) {
    log(label, `Port ${port} is free`);
    return true;
  }

  // Port is in use — check if it's a valid Scientra service
  if (healthCheck) {
    const healthy = await healthCheck();
    if (healthy && !force) {
      log(label, `Already running and healthy on port ${port} — reusing`);
      return "reuse";
    }
  }

  // Stale or non-Scientra process — kill it
  const pid = findPidOnPort(port);
  if (pid) {
    log(label, `Killing stale process PID ${pid} on port ${port}...`);
    const killed = killProcess(pid);
    if (!killed) {
      warn(`Could not kill PID ${pid}. Close it manually and re-run.`);
      return false;
    }
    // Wait for port to free up
    await new Promise((r) => setTimeout(r, 1500));
    const stillInUse = await isPortInUse(port);
    if (stillInUse) {
      warn(`Port ${port} still occupied. Close the program manually.`);
      return false;
    }
    log(label, `Port ${port} freed`);
    return true;
  }

  warn(`Port ${port} is in use but cannot find the process.`);
  return false;
}

/* ── Main ── */

async function main() {
  console.log("");
  console.log("  \x1b[1;36mScientra Copilot — Dev Launcher\x1b[0m");
  console.log("  \x1b[90m──────────────────────────────\x1b[0m");
  console.log("");

  let apiReady = false;

  // ── API Server ──
  if (!webOnly) {
    const apiPortStatus = await ensurePortFree(API_PORT, "api", checkApiHealth);
    if (apiPortStatus === "reuse") {
      apiReady = true;
    } else if (apiPortStatus === true) {
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

      apiProcess.stderr.on("data", (d) => {
        const text = d.toString().trim();
        if (text && !text.includes("Warning")) {
          log("api", text.slice(0, 200));
        }
      });

      apiProcess.on("error", (err) => {
        log("api", `Startup error: ${err.message}`);
      });

      // Wait for health
      log("api", `Waiting for /health on port ${API_PORT}...`);
      const start = Date.now();
      while (Date.now() - start < 30000) {
        if (await checkApiHealth()) {
          apiReady = true;
          break;
        }
        await new Promise((r) => setTimeout(r, 1500));
      }

      if (apiReady) {
        log("api", `Ready — ${API_URL}/health ✅`);
      } else {
        warn(`API did not respond within 30s. Check for errors.`);
      }
    } else {
      warn("API port could not be freed. Skipping API startup.");
    }
  }

  // ── Web Frontend ──
  if (!apiOnly) {
    await new Promise((r) => setTimeout(r, 500));

    const webPortStatus = await ensurePortFree(WEB_PORT, "web", async () => {
      const r = await httpGet(WEB_URL);
      return r.ok;
    });

    if (webPortStatus === "reuse") {
      log("web", `Already running at ${WEB_URL} — reusing`);
      log("launcher", `Open ${WEB_URL}/import in your browser`);
    } else if (webPortStatus === true) {
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
        log("web", `Startup error: ${err.message}`);
      });

      webProcess.on("exit", (code) => {
        if (code !== null && code !== 0) {
          log("web", `Process exited (code ${code})`);
        }
        cleanup();
      });

      // Wait for web to be ready
      log("web", "Waiting for Next.js to compile...");
      const start = Date.now();
      let webReady = false;
      while (Date.now() - start < 120000) {
        const r = await httpGet(WEB_URL);
        if (r.ok) { webReady = true; break; }
        await new Promise((res) => setTimeout(res, 2000));
      }
      if (webReady) {
        log("web", `Ready — ${WEB_URL} ✅`);
        log("launcher", `API: ${API_URL}/health  |  Web: ${WEB_URL}/import`);
      } else {
        warn("Web did not respond within 120s. It may still be compiling.");
      }
    } else {
      warn("Web port could not be freed. Skipping web startup.");
    }
  }

  if (!webProcess && !apiProcess) {
    log("launcher", "Nothing to run. Services may already be running.");
    log("launcher", `API:  ${API_URL}/health`);
    log("launcher", `Web:  ${WEB_URL}/import`);
  }
}

main().catch((err) => {
  console.error("Launcher error:", err);
  process.exit(1);
});
