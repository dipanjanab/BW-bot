# Brainwave Bot prototype

A complete, local-first reference implementation for asking natural-language questions about Brainwave business data. It resolves company terminology and fiscal dates, routes SQL/RAG/hybrid requests, creates a typed SQL plan, generates bound SQL, validates its AST with SQLGlot, enforces market authorization, executes SQLite read-only, and turns actual rows into an answer.

Queries that name a market or request a market breakdown explicitly retrieve their terminology and descriptive context from `knowledge/market_definitions.md`; numerical counts and revenue still come exclusively from SQLite.

The included database and Markdown knowledge files are demonstration inputs supplied with the project. Knowledge text is indexed as content only; it is never executed as instructions.

## Flow

```text
question
  -> BusinessContextResolver (EMIA -> EMEA; stories -> submissions; FY26 -> date range)
  -> Orchestrator route (SQL | RAG | hybrid)
       -> LangChain InMemoryVectorStore RAG
       -> SQLPlanner (deterministic or LangChain/OpenRouter structured output)
          -> ParameterizedSQLBuilder
          -> market authorization predicate
          -> SQLGlot SELECT/table/placeholder validation
          -> read-only SQLite tool
  -> natural-language answer + inspectable trace
```

## Quick start (no API key)

Requires Python 3.11+.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
brainwave "How many EMIA stories were submitted in FY26?" --json
pytest
uvicorn brainwave_bot.api:app --reload
```

Example result: `There are 3 submitted stories for EMEA in FY26 (2025-04-01 through 2026-03-31).`

The API exposes `GET /health` and `POST /ask`:

```powershell
curl.exe -X POST http://127.0.0.1:8000/ask `
  -H "Content-Type: application/json" `
  -d '{"question":"Show submissions by market in FY26","allowed_markets":["APAC"]}'
```

`allowed_markets` is a caller authorization scope, not merely a UI filter. A named unauthorized market returns HTTP 403; an unscoped/grouped question receives a SQL `IN (...)` predicate containing only authorized database markets.

## OpenRouter structured planning

Deterministic mode is the default and covers the supported demo metrics without network access. To use a LangChain `ChatOpenAI` client pointed at OpenRouter with Pydantic structured output:

```powershell
$env:OPENROUTER_API_KEY = "..."
$env:OPENROUTER_MODEL = "openai/gpt-4o-mini"
$env:BRAINWAVE_MODE = "openrouter"
brainwave "What is EMIA revenue in FY26?"
```

The model emits only a typed `SQLPlan`; it never executes free-form SQL. Both modes pass through the same template builder, authorization constraints, SQLGlot validator, allowlist, and read-only connection.

## Layout

- `brainwave_bot/context.py` — terminology, fiscal dates, deterministic routing signals
- `brainwave_bot/rag.py` — LangChain in-memory vector search with local deterministic embeddings
- `brainwave_bot/sql_agent.py` — deterministic/OpenRouter structured planner and SQL templates
- `brainwave_bot/sql_tool.py` — SQLGlot validation and read-only SQLite execution
- `brainwave_bot/orchestrator.py` — authorization, routing, result composition
- `brainwave_bot/api.py`, `cli.py` — FastAPI and CLI entry points
- `tests/test_brainwave.py` — seven automated tests

## Supported demonstration questions

- `How many EMIA stories were submitted in FY26?`
- `What is EMIA revenue in FY26?`
- `Show submissions by market this year`
- `What does EMIA mean?`
- `How many EMIA submissions in FY26 and explain the submitted-story definition?`

This is a prototype: production use should derive market permissions from authenticated identity, add telemetry and result-size limits, use managed secrets, and replace local hashing embeddings with an approved embedding service.
