from __future__ import annotations
import os
from .models import Metric, ResolvedQuestion, SQLPlan, SQLStatement

class SQLPlanner:
    """Structured business planner; deterministic or OpenRouter-backed."""
    def __init__(self, mode: str = "deterministic", model: str | None = None):
        self.mode = mode
        self.model = model or os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    def plan(self, resolved: ResolvedQuestion) -> SQLPlan:
        if self.mode == "openrouter":
            return self._openrouter_plan(resolved)
        text = resolved.normalized.lower()
        metric = (Metric.REVENUE if "revenue" in text else
                  Metric.SUBMISSIONS_BY_MARKET if "by market" in text or "group" in text else
                  Metric.SUBMISSION_COUNT)
        return SQLPlan(metric=metric, market=resolved.database_market,
            start_date=resolved.start_date or "1900-01-01", end_date=resolved.end_date or "2999-12-31",
            explanation="Deterministic structured plan from resolved terminology and dates.")
    def _openrouter_plan(self, resolved: ResolvedQuestion) -> SQLPlan:
        from langchain_openai import ChatOpenAI
        if not os.getenv("OPENROUTER_API_KEY"):
            raise RuntimeError("OPENROUTER_API_KEY is required when BRAINWAVE_MODE=openrouter")
        llm = ChatOpenAI(model=self.model, api_key=os.environ["OPENROUTER_API_KEY"],
            base_url="https://openrouter.ai/api/v1", temperature=0).with_structured_output(SQLPlan)
        prompt = f"""Create a reporting plan, not SQL. Allowed metrics: submission_count, revenue,
submissions_by_market. Schema: stories(story_id, story_title, market, category, submission_date,
status, submitter, revenue). Submitted metrics always use status Submitted. Resolved input:
{resolved.model_dump_json()}
Return dates and database market exactly as resolved."""
        return llm.invoke(prompt)

class ParameterizedSQLBuilder:
    def build(self, plan: SQLPlan) -> SQLStatement:
        if plan.metric == Metric.REVENUE:
            select, group = "SELECT COALESCE(SUM(revenue), 0) AS total_revenue", ""
        elif plan.metric == Metric.SUBMISSIONS_BY_MARKET:
            select, group = "SELECT market, COUNT(*) AS submission_count", " GROUP BY market ORDER BY market"
        else:
            select, group = "SELECT COUNT(*) AS submission_count", ""
        sql = select + " FROM stories WHERE status = :status AND submission_date BETWEEN :start_date AND :end_date"
        parameters: dict[str, object] = {"status": "Submitted", "start_date": plan.start_date, "end_date": plan.end_date}
        if plan.market:
            sql += " AND market = :market"; parameters["market"] = plan.market
        elif plan.authorized_database_markets:
            names = []
            for index, market in enumerate(plan.authorized_database_markets):
                name = f"auth_market_{index}"
                names.append(f":{name}")
                parameters[name] = market
            sql += f" AND market IN ({', '.join(names)})"
        return SQLStatement(sql=sql + group, parameters=parameters)
