from __future__ import annotations
import re
from datetime import date
from .models import ResolvedQuestion, Route

MARKET_ALIASES = {
    "EMIA": ("EMEA", "EMIA"), "EMEA": ("EMEA", "EMIA"),
    "APAC": ("APAC", "APAC"), "AMER": ("AMER", "AMER"), "LATAM": ("LATAM", "LATAM"),
}

def fiscal_year_bounds(fy_end_year: int) -> tuple[str, str]:
    return f"{fy_end_year - 1:04d}-04-01", f"{fy_end_year:04d}-03-31"

def current_fiscal_year(today: date) -> int:
    return today.year + 1 if today.month >= 4 else today.year

class BusinessContextResolver:
    """Normalize company vocabulary and April-March fiscal periods."""
    def resolve(self, question: str, today: date | None = None) -> ResolvedQuestion:
        today = today or date.today()
        substitutions: dict[str, str] = {}
        normalized = re.sub(r"\bstories\b", "submissions", question, flags=re.I)
        if normalized != question:
            substitutions["stories"] = "submissions"
        market = database_market = None
        for alias, (canonical, stored) in MARKET_ALIASES.items():
            if re.search(rf"\b{alias}\b", question, re.I):
                market, database_market = canonical, stored
                if alias != canonical:
                    substitutions[alias] = canonical
                break
        match = re.search(r"\bFY\s*([0-9]{2}|[0-9]{4})\b", question, re.I)
        if match:
            raw = int(match.group(1)); fy = raw if raw >= 2000 else 2000 + raw
            fiscal_label = f"FY{str(fy)[-2:]}"
        elif re.search(r"\b(this|current)\s+(fiscal\s+)?year\b", question, re.I):
            fy = current_fiscal_year(today); fiscal_label = f"FY{str(fy)[-2:]}"
            substitutions["current year"] = fiscal_label
        else:
            fy = current_fiscal_year(today); fiscal_label = f"FY{str(fy)[-2:]} (default)"
        start_date, end_date = fiscal_year_bounds(fy)
        sql_signal = bool(re.search(r"\b(how many|count|total|revenue|submissions?|submitted|show|list|average|sum)\b", normalized, re.I))
        rag_signal = bool(re.search(r"\b(define|definition|mean|means|why|policy|guide|explain|calendar)\b", normalized, re.I))
        route = Route.HYBRID if sql_signal and rag_signal else Route.SQL if sql_signal else Route.RAG
        return ResolvedQuestion(original=question, normalized=normalized, route=route, market=market,
            database_market=database_market, start_date=start_date, end_date=end_date,
            fiscal_label=fiscal_label, substitutions=substitutions)
