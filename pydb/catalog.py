"""The system catalog — table schemas, persisted as JSON.

Only DDL statements mutate the catalog; row inserts grow the heap page chain
directly, so no catalog write is needed on the hot path.
"""

import json
import os
from typing import Dict, List

from .errors import ExecutionError
from .schema import TableSchema

CATALOG_VERSION = 1


class Catalog:
    def __init__(self, path: str):
        self.path = path
        self.tables: Dict[str, TableSchema] = {}
        self._load()

    # ------------------------------------------------------------------ #
    def _load(self):
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        for name, tdict in raw.get("tables", {}).items():
            self.tables[name] = TableSchema.from_dict(tdict)

    def save(self):
        payload = {
            "version": CATALOG_VERSION,
            "tables": {name: t.to_dict() for name, t in self.tables.items()},
        }
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp, self.path)          # atomic on POSIX & Windows

    # ------------------------------------------------------------------ #
    def exists(self, name: str) -> bool:
        return name.lower() in self.tables

    def get(self, name: str) -> TableSchema:
        schema = self.tables.get(name.lower())
        if schema is None:
            raise ExecutionError(f"no such table: {name}")
        return schema

    def add(self, schema: TableSchema):
        self.tables[schema.name] = schema
        self.save()

    def remove(self, name: str):
        self.tables.pop(name.lower(), None)
        self.save()

    def names(self) -> List[str]:
        return sorted(self.tables)