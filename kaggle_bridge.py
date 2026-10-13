#!/usr/bin/env python3
"""Ultimate AI - notebook bridge (Kaggle T4 x2, Jupyter, Colab, any Python REPL).

This is the IMPORT surface for notebooks. The harness itself is an interactive
REPL; notebooks have no stdin, so this wraps the exact same agent loop behind a
tiny class:

    from kaggle_bridge import UltimateAI
    ai = UltimateAI()                 # verifies daemon, warms the model
    ai.run("Scan online for at least 3 minutes: ...")   # live progress + result

All harness guarantees apply unchanged: TIME CONTRACTS (stated durations are
enforced), 65536 proven context window (auto-degrades if VRAM won't hold it),
overflow-proof compaction, keep-warm (never starts a turn on a cold model),
27 tools (run_bash/run_cmd/run_python work on Linux).
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_HARNESS_DIR = _ROOT / "harness"
if str(_HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(_HARNESS_DIR))

import harness as H  # noqa: E402  (needs the sys.path line above)

try:
    from rich.console import Console
except Exception as exc:  # pragma: no cover - clear failure beats a trace
    raise SystemExit(
        "Ultimate AI needs the 'rich' package:  pip install -r requirements.txt"
    ) from exc


class UltimateAI:
    def __init__(
        self,
        model: str = "gpt-oss:20b",
        host: str = "http://127.0.0.1:11434",
        num_ctx: int | None = None,
        max_iters: int = 600,
        warm: bool = True,
    ):
        self.model = model
        self.host = host.rstrip("/")
        self.max_iters = max_iters
        self.console = Console()

        self._require_daemon()

        H.STATE["console"] = self.console
        H.STATE.update(model=model, host=self.host, num_ctx=num_ctx, done=False)
        # Adopt the REAL-prompt-proven window (written by tools/ctx_proof.py) so
        # the notebook gets the maximum context the GPUs can hold.
        proof = H._ctx_proof_num_ctx(model)
        if proof and int(H.STATE.get("num_ctx") or 0) < proof:
            H.STATE["num_ctx"] = proof
        H.STATE["messages"] = [{"role": "system", "content": H.build_system_prompt()}]
        try:
            H.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
            H.STATE["session_file"] = H.SESSIONS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}.json"
        except Exception:
            H.STATE["session_file"] = None
        H.STATE["t_start_wall"] = datetime.now()
        H.STATE["t_start_mono"] = time.monotonic()
        H.STATE["turn_active"] = False

        self._keep_warm = H.KeepWarm()
        self._keep_warm.start()

        if warm:
            self.warm()

    # -- infrastructure -------------------------------------------------------

    def _require_daemon(self) -> None:
        try:
            r = H._httpx().get(self.host + "/api/ps", timeout=5.0)
            r.raise_for_status()
        except Exception as exc:
            raise RuntimeError(
                f"Ollama is not reachable at {self.host} ({exc}). Run the setup first:\n"
                f"    !bash kaggle_setup.sh      (installs Ollama, pulls {self.model}, starts the daemon)"
            ) from exc

    def warm(self, timeout_s: float = 600.0) -> None:
        """Load the model now (blocking, with progress) so the first goal is hot."""
        import httpx

        print(f"[UltimateAI] warming {self.model} (weights load once, then stay resident 24h)...")
        t0 = time.time()
        try:
            with httpx.Client(timeout=httpx.Timeout(timeout_s, connect=10.0)) as client:
                r = client.post(
                    self.host + "/api/generate",
                    json={"model": self.model, "prompt": "", "keep_alive": "24h"},
                )
                r.raise_for_status()
        except Exception as exc:
            print(f"[UltimateAI] WARNING: warm failed ({exc}) - the first goal may wait for a cold load.")
            return
        try:
            ps = H._httpx().get(self.host + "/api/ps", timeout=5.0).json()
            ctx = next((m.get("context_length") for m in ps.get("models", []) if str(m.get("name", "")).startswith(self.model.split(":")[0])), None)
        except Exception:
            ctx = None
        print(f"[UltimateAI] ready in {time.time() - t0:.0f}s - model {self.model}, context {ctx or H.STATE.get('num_ctx') or 'default'}")

    def status(self) -> dict:
        try:
            ps = H._httpx().get(self.host + "/api/ps", timeout=5.0).json().get("models", [])
            resident = [
                {"name": m.get("name"), "context_length": m.get("context_length"), "vram_gb": round(m.get("size_vram", 0) / 1e9, 1)}
                for m in ps
            ]
        except Exception:
            resident = []
        return {
            "model": H.STATE.get("model"),
            "context_window": H.STATE.get("num_ctx") or "default",
            "resident": resident,
            "tool_count": len(H.TOOLS),
        }

    # -- the agent ------------------------------------------------------------

    def run(self, goal: str) -> dict:
        """Run one full autonomous goal. Live progress prints into the cell;
        returns {'outcome', 'summary', 'tool_calls', 'elapsed_s'}."""
        if not str(goal or "").strip():
            return {"outcome": "empty_goal", "summary": "", "tool_calls": 0, "elapsed_s": 0.0}
        args = argparse.Namespace(
            model=self.model,
            host=self.host,
            num_ctx=H.STATE.get("num_ctx"),
            max_iters=self.max_iters,
            mission=None,
            system=None,
            self_test=False,
            yes=True,
        )
        t0 = time.monotonic()
        H.STATE["last_outcome"] = None
        H.STATE["mission_mode"] = False
        H.STATE["done"] = False
        H.run_agent_turn(str(goal), args)
        outcome = H.STATE.get("last_outcome")
        summary = ""
        for m in reversed(H.STATE.get("messages", [])):
            if m.get("role") == "tool" and m.get("name") == "task_done":
                summary = str(m.get("content", ""))
                break
        return {
            "outcome": outcome,
            "summary": summary,
            "tool_calls": len(H.STATE.get("tool_log", [])),
            "elapsed_s": round(time.monotonic() - t0, 1),
        }

    # Convenience alias.
    ask = run

    def close(self) -> None:
        kw = getattr(self, "_keep_warm", None)
        if kw is not None:
            kw.stop()


def main() -> int:  # pragma: no cover - smoke when run as a script
    ai = UltimateAI()
    print(ai.status())
    return 0


if __name__ == "__main__":
    sys.exit(main())
