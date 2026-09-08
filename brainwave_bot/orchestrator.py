from __future__ import annotations
import os
import re
from pathlib import Path
from .context import BusinessContextResolver, MARKET_ALIASES
from .models import AskResponse, Metric, Route
from .rag import KnowledgeRetriever
from .sql_agent import ParameterizedSQLBuilder, SQLPlanner
from .sql_tool import SQLiteTool

class MarketAuthorizationError(PermissionError):
    pass

class BrainwaveOrchestrator:
    """Routes RAG/SQL/hybrid questions through one auditable pipeline."""
    def __init__(self, database: Path, knowledge_dir: Path, mode: str = "deterministic"):
        self.resolver = BusinessContextResolver()
        self.retriever = KnowledgeRetriever(knowledge_dir)
        self.planner = SQLPlanner(mode=mode)
        self.builder = ParameterizedSQLBuilder()
        self.sql_tool = SQLiteTool(database)

    def ask(self, question: str, allowed_markets: list[str] | None = None) -> AskResponse:
        allowed_markets = allowed_markets or ["EMEA", "APAC", "AMER", "LATAM"]
        canonical = {MARKET_ALIASES.get(x.upper(), (x.upper(), x.upper()))[0] for x in allowed_markets}
        database_allowed = [stored for _, (name, stored) in MARKET_ALIASES.items() if name in canonical]
        database_allowed = list(dict.fromkeys(database_allowed))
        resolved = self.resolver.resolve(question)
        if resolved.market and resolved.market not in canonical:
            raise MarketAuthorizationError(f"Not authorized for market {resolved.market}")

        market_related = resolved.market is not None or bool(re.search(r"\bmarkets?\b", question, re.I))
        needs_context = resolved.route in (Route.RAG, Route.HYBRID) or market_related
        documents = self.retriever.search(
            resolved.normalized,
            preferred_source="market_definitions.md" if market_related else None,
        ) if needs_context else []
        context = [f"[{doc.metadata['source']}] {doc.page_content}" for doc in documents]
        statement = None
        rows: list[dict] = []
        metric = None
        if resolved.route in (Route.SQL, Route.HYBRID):
            plan = self.planner.plan(resolved)
            plan.authorized_database_markets = database_allowed
            metric = plan.metric
            statement = self.builder.build(plan)
            rows = self.sql_tool.execute(statement)
        answer = self._answer(resolved, metric, rows, context)
        return AskResponse(answer=answer, route=resolved.route, resolved=resolved,
            sql=statement.sql if statement else None,
            parameters=statement.parameters if statement else None, rows=rows, context=context)

    @staticmethod
    def _answer(resolved, metric, rows, context) -> str:
        parts = []
        scope = f" for {resolved.market}" if resolved.market else ""
        period = f" in {resolved.fiscal_label} ({resolved.start_date} through {resolved.end_date})"
        if metric == Metric.REVENUE:
            value = rows[0]["total_revenue"] if rows else 0
            parts.append(f"Total submitted-story revenue{scope}{period} is {value:,.2f}.")
        elif metric == Metric.SUBMISSION_COUNT:
            value = rows[0]["submission_count"] if rows else 0
            parts.append(f"There are {value} submitted stories{scope}{period}.")
        elif metric == Metric.SUBMISSIONS_BY_MARKET:
            values = ", ".join(f"{row['market']}: {row['submission_count']}" for row in rows) or "no submissions"
            parts.append(f"Submitted stories by market{period}: {values}.")
        if context:
            excerpt = context[0].split("] ", 1)[-1].replace("\n", " ")
            parts.append(f"Business context: {excerpt}")
        return " ".join(parts) or "No relevant business context was found."

def default_orchestrator() -> BrainwaveOrchestrator:
    root = Path(__file__).resolve().parents[1]
    database = Path(os.getenv("BRAINWAVE_DB_PATH", root / "data" / "brainwave.db"))
    knowledge = Path(os.getenv("BRAINWAVE_KNOWLEDGE_DIR", root / "knowledge"))
    return BrainwaveOrchestrator(database, knowledge, os.getenv("BRAINWAVE_MODE", "deterministic"))
