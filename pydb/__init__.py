"""
PyDB — a relational database engine written from scratch in Python.

Public API:
    from pydb import connect
    db = connect("./mydb")
    result = db.execute("SELECT * FROM users")
    print(result.to_table())
"""

from .database import Database
from .errors import (
    DBError,
    ParseError,
    ExecutionError,
    ConstraintError,
    SchemaError,
)
from .datatypes import DataType
from .result import Result

__version__ = "0.1.0"

__all__ = [
    "Database",
    "connect",
    "DBError",
    "ParseError",
    "ExecutionError",
    "ConstraintError",
    "SchemaError",
    "DataType",
    "Result",
]


def connect(path: str = "mydb") -> Database:
    """Open (or create) a database at `path`."""
    return Database(path)