#!/usr/bin/env python
"""One-click LLM Setup Wizard for Scientra Copilot.

Three ways to configure:

  1. Interactive:   python Scripts/setup_llm.py
  2. From env var:   DEEPSEEK_API_KEY="sk-..." python Scripts/setup_llm.py --quick
  3. Via Web UI:     Settings > AI Provider (after starting the server)

Your API key is stored in Config/llm_config.yaml (gitignored — never committed).
"""

from __future__ import annotations

import argparse, os, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = PROJECT_ROOT / "Config" / "llm_config.template.yaml"
CONFIG_PATH = PROJECT_ROOT / "Config" / "llm_config.yaml"

PROVIDERS: dict[str, dict] = {
    "1": {"name": "DeepSeek", "id": "deepseek", "model": "deepseek-chat",
          "url": "https://api.deepseek.com", "env": "DEEPSEEK_API_KEY"},
    "2": {"name": "OpenAI", "id": "openai", "model": "gpt-4o-mini",
          "url": "https://api.openai.com", "env": "OPENAI_API_KEY"},
    "3": {"name": "Anthropic", "id": "anthropic", "model": "claude-sonnet-4-6",
          "url": "https://api.anthropic.com", "env": "ANTHROPIC_API_KEY"},
    "4": {"name": "Local (no API key needed)", "id": "local", "model": "local",
          "url": "", "env": ""},
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Scientra LLM Setup Wizard")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    if not TEMPLATE_PATH.exists():
        print("Error: Template not found at", TEMPLATE_PATH)
        return 1

    print("\n" + "=" * 55)
    print("  Scientra LLM Setup Wizard")
    print("=" * 55)

    if CONFIG_PATH.exists():
        print("\n  Config already exists at:", CONFIG_PATH)
        choice = input("  Overwrite? [y/N]: ").strip().lower()
        if choice != "y":
            print("  Keeping existing config.")
            if args.test:
                return _test_connection()
            return 0

    if not args.quick:
        print("\n  Select AI Provider:")
        for key, p in PROVIDERS.items():
            print(f"    [{key}] {p['name']}")
        choice = input(f"\n  Provider [1-4, default=1]: ").strip() or "1"
        provider = PROVIDERS.get(choice, PROVIDERS["1"])

        if provider["id"] == "local":
            api_key, model, base_url = "", "local", ""
        else:
            print(f"\n  {provider['name']} API Key")
            print(f"  (Get one at: {provider['url']})")
            env_val = os.environ.get(provider["env"], "")
            if env_val:
                print(f"  Found in ${provider['env']} env var")
                api_key = env_val
            else:
                api_key = input("  Enter API key: ").strip()
            model = input(f"  Model [{provider['model']}]: ").strip() or provider["model"]
            base_url = input(f"  Base URL [{provider['url']}]: ").strip() or provider["url"]
    else:
        provider = PROVIDERS["1"]
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        model, base_url = "deepseek-chat", "https://api.deepseek.com"
        if not api_key:
            print("\n  Quick mode needs DEEPSEEK_API_KEY env var. Example:")
            print("    export DEEPSEEK_API_KEY='sk-...'")
            print("    python Scripts/setup_llm.py --quick")
            return 1
        print(f"\n  Provider: {provider['name']}")
        print(f"  Model: {model}")
        print(f"  Using DEEPSEEK_API_KEY from environment")

    config_yaml = f"""# Scientra LLM Configuration
enabled: true
provider: {provider['id']}
model: {model}
api_key: {api_key}
base_url: {base_url}
temperature: 0.2
max_tokens: 4096

enabled_tasks:
  summary: true
  evidence_enrichment: false
  figure_interpretation: false
  table_interpretation: false
  supplementary_interpretation: false
  gap_extraction: false
  hypothesis_generation: false
  agent_chat: true
"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(config_yaml, encoding="utf-8")
    print(f"\n  Saved to: {CONFIG_PATH}")

    masked = api_key[:6] + "***" + api_key[-4:] if len(api_key) > 10 else "***"
    print(f"  API key: {masked}")

    if args.test or (not args.quick and input("\n  Test connection? [y/N]: ").strip().lower() == "y"):
        return _test_connection()

    print("\n  Setup complete. Verify later with: python Scripts/setup_llm.py --test")
    return 0


def _test_connection() -> int:
    print("\n  Testing connection...")
    sys.path.insert(0, str(PROJECT_ROOT))
    from scientra.ai.llm_gateway import reload_config, test_connection
    reload_config()
    result = test_connection()
    if result.success:
        print(f"  Connected! Provider: {result.provider}, Model: {result.model}")
        return 0
    else:
        print(f"  Failed: {result.error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
