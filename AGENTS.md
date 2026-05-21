# AGENTS.md — LabQA 实验室智能问答系统

## Architecture

This project has **two parallel execution surfaces** that share the same codebase:

1. **Python runtime** (`labqa/` package, `main.py`) — standalone CLI / Feishu WebSocket / one-shot Q&A
2. **OpenCode agent definitions** (`.opencode/agent/`) — slash commands (`/查设备`, `/查项目`, `/查文档`) inside OpenCode sessions

They use the same knowledge base (`.opencode/context/`) but route through different code paths. The OpenCode agent definitions reference the context files directly; the Python side loads them via `labqa/context_store.py`.

## Commands

```bash
# CLI interactive mode (recommended for dev)
python3 main.py cli

# One-shot query
python3 main.py ask "GPU服务器在哪"

# Feishu WebSocket long connection (recommended for production — no public IP needed)
python3 main.py feishu

# Convert raw-docs/ → .opencode/context/ (requires python-docx, python-pptx, openpyxl)
bash scripts/convert.sh

# Install Python deps
pip install httpx lark-oapi          # runtime
pip install python-docx python-pptx openpyxl  # doc conversion (optional)
```

## Environment / Config

Copy `.env.example` → `.env` and fill in real values. **The `.env` loader in `main.py` is hand-rolled** (not python-dotenv). Shell env vars always win over `.env` values.

Required: `LABQA_LLM_API_KEY` (or `DEEPSEEK_API_KEY`). Default LLM: DeepSeek `deepseek-chat`.

For Feishu: `FEISHU_APP_ID` + `FEISHU_APP_SECRET`. Use WebSocket long connection mode (`main.py feishu`) — it avoids needing a public IP.

## Two Feishu Implementations — Use the Right One

| File | What it is | Use |
|------|-----------|-----|
| `labqa/feishu_ws.py` | WebSocket long connection via lark-oapi SDK | **Use this** (`main.py feishu`) |
| `labqa/webhook.py` | Flask HTTP webhook | `main.py webhook` (needs public IP) |
| `scripts/feishu-webhook.py` | **Legacy standalone** — has its own keyword-matching, bypasses `labqa/` | Do NOT use for new work |

Only `labqa/feishu_ws.py` and `labqa/webhook.py` go through the real orchestrator.

## Package Structure

```
labqa/
  orchestrator.py   # Main dispatcher: intent → agent → LLM → response
  router.py         # Keyword-based intent recognition (DEVICE/PROJECT/KNOWLEDGE)
  agents/           # Three agents (Device/Project/Knowledge), all extend BaseAgent
  context_store.py  # Loads .opencode/context/*.md, keyword search + scoring
  llm.py            # OpenAI-compatible chat client (httpx, timeout 60s)
  feishu_ws.py      # Feishu WebSocket client (lark-oapi)
  webhook.py        # Feishu HTTP webhook (Flask)
  cli.py            # Terminal interactive UI (supports offline mode)
  config.py          # All config from env vars, validates at startup
```

## Key Gotchas

- **KnowledgeAgent searches TWO directories**: `category = None` means it queries both `context/knowledge/` and `context/guides/` in two separate `get_context_text()` calls. Other agents search exactly one directory.
- **LLM URL construction**: If `LABQA_LLM_API_BASE` already contains `/v1`, the client appends `/chat/completions` directly to avoid doubling (`/v1/v1`).
- **No test framework**: There is no `pytest`, no test directory. The only "tests" are the manual checklist in `docs/TESTING.md`.
- **Frontmatter is hand-parsed**: `context_store.py` splits on `---` and parses `key: value` lines manually. Not a full YAML parser.
- **CLI offline mode**: When no API key is set, the CLI offers an offline mode that does keyword search only (no LLM calls). This uses `os.environ["LABQA_LLM_API_KEY"] = "offline-mode"` as a sentinel.
- **Message dedup in feishu_ws.py**: Two-layer dedup — by `message_id` (set-based) and by content hash within 30s window (chat-scoped). This compensates for Feishu's retry behavior.
- **Agent matching is pure keyword scoring**, not LLM-based. Keywords are hardcoded in `router.py` and each agent's `extract_search_keywords()`.

## Knowledge Base

All knowledge lives in `.opencode/context/` as Markdown files with YAML frontmatter:

```yaml
---
type: device | project | knowledge | guide
tags: []
updated: 2026-05-07
---
```

`context/navigation.md` is the master index — it's **excluded from search results** by the context store. Admin workflow: drop files in `raw-docs/` → run `scripts/convert.sh` → verify output in `context/`.

## References

- Architecture: `docs/ARCHITECTURE.md`
- Quick start: `QUICK-START.md`
- Test checklist: `docs/TESTING.md`
- Agent definitions: `.opencode/agent/lab-orchestrator.md` (+ subagents/)
