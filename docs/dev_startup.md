# Scientra Copilot — Development Startup Guide

## Recommended Startup

```bash
python Scripts/dev_restart.py
```

This single command handles:
- API port detection & conflict resolution
- Old API server detection
- Frontend `.env.local` synchronization
- Next.js cache cleanup
- API schema validation
- Prints access URLs

## Command Options

| Flag | Description |
|------|-------------|
| `--api-port <N>` | Force specific API port (default: auto-detect 8710→8711→8712→8713→8720) |
| `--web-port <N>` | Force specific Web port (default: auto-detect 3000→3001→3002) |
| `--kill-old` | Attempt to kill old API processes on occupied ports |
| `--no-web` | Only start API, skip web frontend |
| `--no-cache-clean` | Skip `.next` cache cleanup |
| `--open` | Auto-open browser to Research Map |
| `--strict` | Exit with error if schema validation fails |

## Common Issues & Solutions

### "Port 8710 occupied by old API"

**Symptom:** The API server on port 8710 is running outdated code with old schema `{topics:[], papers:[]}`.

**Solution 1 (recommended):**
```bash
python Scripts/dev_restart.py
```
The script will auto-detect the old API and switch to port 8711.

**Solution 2 (force kill):**
```bash
python Scripts/dev_restart.py --kill-old
```
If you get "Access denied", you need administrator privileges:
```powershell
# Run PowerShell as Administrator
taskkill /PID <pid> /F
python Scripts/dev_restart.py
```

### "Web connected to old API" / ".env.local points to wrong API"

**Symptom:** Frontend loads but Research Map shows no data or wrong data.

**Solution:**
```bash
python Scripts/dev_restart.py
```
The script automatically writes `web/.env.local` with the correct API URL.

**Manual fix:**
Edit `web/.env.local`:
```
NEXT_PUBLIC_SCIENTRA_API_URL=http://127.0.0.1:8711
NEXT_PUBLIC_SCIENTRA_API_PORT=8711
```

### "Research Map schema mismatch"

**Symptom:** Console shows `[Scientra Schema] Research Map API returned an outdated or empty schema.`

**Cause:**
- The frontend is connected to an old API server (port mismatch)
- The API server is running outdated code

**Solution:**
```bash
python Scripts/dev_restart.py
```

### "Next.js cache stale"

**Symptom:** Code changes not reflected in browser.

**Solution:**
`dev_restart.py` automatically cleans `web/.next` on each run. To do it manually:
```bash
rm -rf web/.next
```

### "Connection refused" (localhost)

**Symptom:** Browser shows "localhost refused to connect."

**Causes & Solutions:**

1. **API server not running:**
   ```bash
   curl http://127.0.0.1:8710/health
   # If fails: python Scripts/dev_restart.py
   ```

2. **Web frontend not running:**
   ```bash
   curl http://localhost:3000
   # If fails: python Scripts/dev_restart.py
   ```

3. **Wrong port in .env.local:**
   Check `web/.env.local` — should match the running API port.

## Manual Server Control

### API Server Only
```bash
python Scripts/run_api_server.py --port 8710
```

### Web Frontend Only
```bash
cd web
npm run dev
```

### Production Launcher (includes GROBID)
```bash
python Scripts/start_all.py
```

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│  Browser    │────▶│  Next.js Web │────▶│  Scientra API │
│  :3000      │     │  :3000       │     │  :8710/:8711  │
└─────────────┘     └──────────────┘     └───────────────┘
                           │                      │
                    reads .env.local      serves /health
                    NEXT_PUBLIC_*          /research-map
                                          /version (v2 schema)
```

### Schema Versions

| Version | Keys in /research-map | Status |
|---------|----------------------|--------|
| v2 (current) | `clusters`, `mature_topics`, `growing_topics`, `gap_topics`, `topic_relationships` | ✅ Active |
| v1 (old) | `topics`, `papers` (empty) | ⚠️ Deprecated |

The `/version` endpoint returns:
```json
{
  "app": "Scientra Copilot",
  "api_version": "dev",
  "research_map_schema": "v2",
  "evidence_engine": "v2.2"
}
```
