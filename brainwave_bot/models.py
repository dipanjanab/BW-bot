from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class Route(str, Enum):
    SQL = "sql"
    RAG = "rag"
    HYBRID = "hybrid"

class Metric(str, Enum):
    SUBMISSION_COUNT = "submission_count"
    REVENUE = "revenue"
    SUBMISSIONS_BY_MARKET = "submissions_by_market"

class ResolvedQuestion(BaseModel):
    original: str
    normalized: str
    route: Route
    market: str | None = None
    database_market: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    fiscal_label: str | None = None
    substitutions: dict[str, str] = Field(default_factory=dict)

class SQLPlan(BaseModel):
    metric: Metric
    market: str | None = None
    start_date: str
    end_date: str
    authorized_database_markets: list[str] = Field(default_factory=list)
    explanation: str = ""

class SQLStatement(BaseModel):
    sql: str
    parameters: dict[str, Any]

class AskRequest(BaseModel):
    question: str = Field(min_length=2)
    allowed_markets: list[str] = Field(default_factory=lambda: ["EMEA", "APAC", "AMER", "LATAM"])

class AskResponse(BaseModel):
    answer: str
    route: Route
    resolved: ResolvedQuestion
    sql: str | None = None
    parameters: dict[str, Any] | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    context: list[str] = Field(default_factory=list)
