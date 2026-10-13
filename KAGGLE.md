# Ultimate AI on Kaggle (T4 x2) — exact notebook steps

The folder is fully self-contained: same agent, same guarantees (time contracts,
proven max context, overflow-proof compaction, keep-warm), ported for Linux.

**Kaggle settings first:** Notebook options → *Internet* **ON**, Accelerator
**GPU T4 x2**.

## 1. Get the folder onto the notebook

Either upload `ultimate-llm-portable.zip` (next to this file) as a Kaggle
Dataset and attach it, or upload the zip into `/kaggle/working` and unzip:

```python
!unzip -q /kaggle/working/ultimate-llm-portable.zip -d /kaggle/working/
```

The examples below assume the folder is at `/kaggle/working/ultimate-llm-portable`.

## 2. One-time setup cell (installs Ollama, pulls the model, warms it)

```python
!bash /kaggle/working/ultimate-llm-portable/kaggle_setup.sh
```

Takes ~5-10 min the first time (model download ~13GB). Idempotent — re-run any
time. On a T4 x2 pair the proof normally ADOPTS the 65536 context window; if
it doesn't, the harness keeps the proven-safe floor and **auto-degrades
mid-session if a window ever proves too big** — it can never crash a session.

## 3. Agent cell

```python
import sys
sys.path.insert(0, "/kaggle/working/ultimate-llm-portable")
from kaggle_bridge import UltimateAI

ai = UltimateAI()          # verifies daemon, adopts max context, model is warm
print(ai.status())

result = ai.run("Scan online for at least 3 minutes: what are the latest "
                "OpenWhispr releases and what improved for dictation?")
print(result["outcome"], "-", result["summary"])
```

`ai.run(...)` streams the whole mission live into the cell (tool calls,
results, the answer) and returns a dict:

| key | meaning |
|---|---|
| `outcome` | `done` (verified complete), `answered`, `max_iters`, ... |
| `summary` | the agent's final task_done summary |
| `tool_calls` | how many tool calls the goal took |
| `elapsed_s` | wall time of the goal |

Keep `ai` in a notebook variable — it holds the keep-warm thread so the model
never goes cold between cells. State a duration in the goal ("scan for at
least 5 minutes") and the harness enforces it, exactly like on your PC.

## 4. Local machine (Windows) — same folder

Double-click `Ultimate-AI.cmd` in this folder (or run it from a terminal):
fast launch, interactive REPL, full 26+1 tools. Everything committed in the
main project applies here identically.
