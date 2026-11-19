"""SQL data types and Python <-> SQL value coercion."""

from enum import Enum

from .errors import ExecutionError


class DataType(Enum):
    INTEGER = "INTEGER"
    REAL = "REAL"
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"

    @classmethod
    def from_name(cls, name: str) -> "DataType":
        n = name.upper()
        if n in ("INT", "INTEGER", "BIGINT", "SMALLINT"):
            return cls.INTEGER
        if n in ("REAL", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL"):
            return cls.REAL
        if n in ("TEXT", "STRING", "VARCHAR", "CHAR"):
            return cls.TEXT
        if n in ("BOOL", "BOOLEAN"):
            return cls.BOOLEAN
        raise ExecutionError(f"unknown data type: {name}")


def coerce(value, dtype: DataType):
    """Convert a Python value into the canonical representation for `dtype`."""
    if value is None:
        return None

    if dtype is DataType.INTEGER:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if value != int(value):
                raise ExecutionError(f"cannot store {value!r} in an INTEGER column")
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                raise ExecutionError(f"cannot convert {value!r} to INTEGER")
        raise ExecutionError(f"cannot convert {type(value).__name__} to INTEGER")

    if dtype is DataType.REAL:
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                raise ExecutionError(f"cannot convert {value!r} to REAL")
        raise ExecutionError(f"cannot convert {type(value).__name__} to REAL")

    if dtype is DataType.TEXT:
        if isinstance(value, str):
            return value
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    if dtype is DataType.BOOLEAN:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            s = value.strip().lower()
            if s in ("true", "t", "yes", "y", "1"):
                return True
            if s in ("false", "f", "no", "n", "0"):
                return False
        raise ExecutionError(f"cannot convert {value!r} to BOOLEAN")

    raise ExecutionError(f"unsupported data type: {dtype}")