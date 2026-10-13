#!/usr/bin/env bash
# Ultimate AI - interactive REPL on Linux/Kaggle (use a terminal or run inside
# tmux/screen; notebooks should use kaggle_bridge.py instead - no stdin there).
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE=q8_0
exec python "$ROOT/harness/harness.py" --model gpt-oss:20b --num-ctx 65536 --yes
