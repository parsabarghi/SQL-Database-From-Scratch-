"""Table / column schema definitions."""

from dataclasses import dataclass, field
from typing import List, Optional

from .datatypes import DataType
from .errors import SchemaError


@dataclass
class Column:
    name: str
    type: DataType
    nullable: bool = True
    primary_key: bool = False

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type.value,
            "nullable": self.nullable,
            "primary_key": self.primary_key,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            name=d["name"],
            type=DataType(d["type"]),
            nullable=d.get("nullable", True),
            primary_key=d.get("primary_key", False),
        )


@dataclass
class TableSchema:
    name: str
    columns: List[Column] = field(default_factory=list)
    first_page: Optional[int] = None

    def __post_init__(self):
        seen = set()
        for c in self.columns:
            if c.name in seen:
                raise SchemaError(f"duplicate column name: {c.name}")
            seen.add(c.name)

    def index_of(self, name: str) -> Optional[int]:
        n = name.lower()
        for i, c in enumerate(self.columns):
            if c.name == n:
                return i
        return None

    def column(self, name: str) -> Column:
        i = self.index_of(name)
        if i is None:
            raise SchemaError(f"no such column: {name}")
        return self.columns[i]

    @property
    def primary_key_index(self) -> Optional[int]:
        for i, c in enumerate(self.columns):
            if c.primary_key:
                return i
        return None

    def to_dict(self):
        return {
            "name": self.name,
            "first_page": self.first_page,
            "columns": [c.to_dict() for c in self.columns],
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            name=d["name"],
            columns=[Column.from_dict(c) for c in d["columns"]],
            first_page=d.get("first_page"),
        )