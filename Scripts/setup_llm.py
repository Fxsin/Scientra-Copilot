"""
Scientra Copilot — LLM API Setup (First-Time User)

Usage:
    python Scripts/setup_llm.py

This will guide you through setting up an LLM API key for the Chat feature.
The key is stored in Config/llm_config.yaml (gitignored, never committed).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "Config" / "llm_config.yaml"

print("=" * 60)
print("  Scientra Copilot — LLM API Setup")
print("=" * 60)
print()
print("The Chat feature can use an LLM to synthesize research answers.")
print("Choose your provider:")
print()
print("  1. DeepSeek  (https://platform.deepseek.com)")
print("  2. Anthropic (https://console.anthropic.com)")
print()

choice = input("Select provider [1/2]: ").strip()

if choice == "1":
    provider = "deepseek"
    model = "deepseek-chat"
    base_url = "https://api.deepseek.com"
    print()
    print("Get your API key at: https://platform.deepseek.com/api_keys")
elif choice == "2":
    provider = "anthropic"
    model = "claude-sonnet-4-6"
    base_url = "https://api.anthropic.com"
    print()
    print("Get your API key at: https://console.anthropic.com/settings/keys")
else:
    print("Invalid choice. Exiting.")
    sys.exit(1)

api_key = input("Paste your API key: ").strip()

if not api_key or len(api_key) < 10:
    print("Invalid API key. Exiting.")
    sys.exit(1)

# Save to config file
import yaml
config = {
    "provider": provider,
    "api_key": api_key,
    "model": model,
    "base_url": base_url,
}
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
CONFIG_PATH.write_text(yaml.dump(config, default_flow_style=False), encoding="utf-8")

# Add to .gitignore
gitignore = ROOT / ".gitignore"
if gitignore.exists():
    content = gitignore.read_text(encoding="utf-8")
    if "Config/llm_config.yaml" not in content:
        content += "\n# LLM config (contains API key)\nConfig/llm_config.yaml\n"
        gitignore.write_text(content, encoding="utf-8")

print()
print("=" * 60)
print("  Setup complete!")
print("=" * 60)
print()
print(f"  Provider: {provider}")
print(f"  Model:    {model}")
print(f"  Config:   {CONFIG_PATH}")
print()
print("Next steps:")
print("  1. Restart the backend server")
print("  2. Open http://127.0.0.1:3000/chat")
print("  3. Select Answer Mode: Auto or LLM synthesis")
print()
print("To test:")
print('  python -c "from scientra.agent import LiteratureAgent;')
print("    r=LiteratureAgent().ask('test', use_llm=True);")
print('    print(r.model)"')
