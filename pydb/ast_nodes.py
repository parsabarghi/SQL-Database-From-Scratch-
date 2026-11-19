"""Abstract syntax tree node definitions."""

from dataclasses import dataclass, field
from typing import Any, List, Optional


# --------------------------------------------------------------------------- #
# Expressions
# --------------------------------------------------------------------------- #
@dataclass
class Literal:
    value: Any

    def __str__(self):
        if self.value is None:
            return "NULL"
        if isinstance(self.value, str):
            return f"'{self.value}'"
        if isinstance(self.value, bool):
            return "TRUE" if self.value else "FALSE"
        return str(self.value)


@dataclass
class ColumnRef:
    name: str

    def __str__(self):
        return self.name


@dataclass
class UnaryOp:
    op: str
    operand: Any

    def __str__(self):
        return f"({self.op} {self.operand})"


@dataclass
class BinaryOp:
    op: str
    left: Any
    right: Any

    def __str__(self):
        return f"({self.left} {self.op} {self.right})"


# --------------------------------------------------------------------------- #
# Statements
# --------------------------------------------------------------------------- #
@dataclass
class ColumnDef:
    name: str
    type: Any
    nullable: bool = True
    primary_key: bool = False


@dataclass
class CreateTable:
    name: str
    columns: List[ColumnDef]
    if_not_exists: bool = False


@dataclass
class DropTable:
    name: str
    if_exists: bool = False


@dataclass
class Insert:
    table: str
    columns: Optional[List[str]]
    rows: List[List[Any]]


@dataclass
class SelectItem:
    expr: Any                      # None means `*`
    alias: Optional[str] = None


@dataclass
class Select:
    table: str
    items: List[SelectItem] = field(default_factory=list)
    star: bool = False
    where: Any = None
    order_by: List = field(default_factory=list)   # [(column_name, descending), ...]
    limit: Optional[int] = None
    offset: Optional[int] = None


@dataclass
class Update:
    table: str
    assignments: List = field(default_factory=list)  # [(column_name, expr), ...]
    where: Any = None


@dataclass
class Delete:
    table: str
    where: Any = None