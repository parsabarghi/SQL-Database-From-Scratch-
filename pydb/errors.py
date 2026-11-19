class DBError(Exception):
    """Base class for every PyDB error."""


class ParseError(DBError):
    """Raised when SQL text cannot be tokenized/parsed."""


class ExecutionError(DBError):
    """Raised when a parsed statement cannot be executed."""


class SchemaError(DBError):
    """Raised for invalid schema definitions."""


class ConstraintError(DBError):
    """Raised when a NOT NULL / PRIMARY KEY constraint is violated."""