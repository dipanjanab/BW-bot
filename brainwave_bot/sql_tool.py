from __future__ import annotations
import sqlite3
import re
from pathlib import Path
from typing import Any
import sqlglot
from sqlglot import exp
from .models import SQLStatement

class SQLValidationError(ValueError):
    pass

class SQLValidator:
    def __init__(self, allowed_tables: set[str] | None = None):
        self.allowed_tables = allowed_tables or {"stories"}
    def validate(self, statement: SQLStatement) -> None:
        try:
            expressions = sqlglot.parse(statement.sql, read="sqlite")
        except sqlglot.errors.ParseError as exc:
            raise SQLValidationError(f"Invalid SQL: {exc}") from exc
        if len(expressions) != 1 or not isinstance(expressions[0], exp.Select):
            raise SQLValidationError("Only one SELECT statement is permitted")
        tree = expressions[0]
        if any(tree.find(kind) for kind in (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter)):
            raise SQLValidationError("Mutating SQL is not permitted")
        tables = {table.name.lower() for table in tree.find_all(exp.Table)}
        allowlist = {name.lower() for name in self.allowed_tables}
        if not tables or not tables <= allowlist:
            raise SQLValidationError(f"Query references non-allowlisted tables: {sorted(tables)}")
        expected = set(re.findall(r":([A-Za-z_][A-Za-z0-9_]*)", statement.sql))
        if expected != set(statement.parameters):
            raise SQLValidationError("SQL placeholders and parameters do not match")

class SQLiteTool:
    """Read-only, validated SQLite execution boundary."""
    def __init__(self, database: Path, validator: SQLValidator | None = None):
        self.database = database
        self.validator = validator or SQLValidator()
    def execute(self, statement: SQLStatement) -> list[dict[str, Any]]:
        self.validator.validate(statement)
        uri = f"file:{self.database.resolve().as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(statement.sql, statement.parameters).fetchall()]
