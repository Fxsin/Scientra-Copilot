# LLM API Setup for Scientra Literature Agent

## Why LLM?

The `/chat` page and PaperAskCard default to `use_llm=true`. When an LLM API key is configured, the agent:

1. Retrieves relevant evidence from LanceDB (pdf_asset_chunks + evidence_chunks)
2. Sends context + question to Claude
3. Returns a synthesized answer with [Ref:N] citations

Without an API key, the agent automatically falls back to evidence-only mode — showing structured context chunks without AI synthesis.

## Security

**API keys MUST be set on the backend only.** Never expose them to the frontend.

- ❌ Do NOT use `NEXT_PUBLIC_*` environment variables
- ❌ Do NOT hardcode keys in source files
- ❌ Do NOT commit keys to git
- ✅ Set keys via environment variables on the backend server

## Setup

### Windows (PowerShell)

```powershell
# Temporary (current session)
$env:ANTHROPIC_API_KEY = "sk-ant-api03-your-key-here"

# Permanent (survives restarts)
setx ANTHROPIC_API_KEY "sk-ant-api03-your-key-here"
```

### Windows (Command Prompt)

```cmd
set ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
setx ANTHROPIC_API_KEY "sk-ant-api03-your-key-here"
```

### Linux / macOS

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-your-key-here"

# Add to ~/.bashrc or ~/.zshrc for persistence
echo 'export ANTHROPIC_API_KEY="sk-ant-api03-your-key-here"' >> ~/.bashrc
```

### Optional: Custom Model

```bash
# Default is claude-sonnet-4-6
export ANTHROPIC_MODEL="claude-sonnet-4-6"
```

## Restart the Backend

After setting the key, restart the Scientra API server:

```powershell
# Kill existing server
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# Restart
cd "g:\AI_agent\Scientra Copilot"
python -m scientra.server
```

## Test

```bash
# Test LLM mode
python -c "from scientra.agent import LiteratureAgent; r=LiteratureAgent().ask('What methods are commonly used in this literature library?', use_llm=True); print(r.answer[:500])"

# Test fallback (unset key first)
python -c "from scientra.agent import LiteratureAgent; r=LiteratureAgent().ask('What methods are used?', use_llm=True); print('Model:', r.model)"
# → Model: evidence-only-fallback
```

## Verify in Chat

1. Open `http://127.0.0.1:3000/chat`
2. "Use LLM" should be checked by default
3. If key is set: answer shows "LLM synthesis" badge
4. If key is missing: answer shows "LLM unavailable — evidence retrieved" badge with yellow warning

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "LLM is not configured" warning | `ANTHROPIC_API_KEY` not set | Set key and restart backend |
| HTTP 401 error | Invalid API key | Check key format (`sk-ant-api03-...`) |
| "evidence-only-fallback" model | Key set but API call failed | Check network, key validity |
| No answer at all | Backend not running | `python -m scientra.server` |
