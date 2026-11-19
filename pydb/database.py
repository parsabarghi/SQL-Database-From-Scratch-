"""The Database object — the single entry point for clients (and the future UI)."""

import os
from typing import List

from .catalog import Catalog
from .executor import Executor
from .parser import parse, parse_script
from .result import Result
from .schema import TableSchema
from .storage.heap import HeapFile
from .storage.pager import Pager

DATA_FILE = "data.db"
CATALOG_FILE = "catalog.json"


class Database:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(path, exist_ok=True)

        self.pager = Pager(os.path.join(path, DATA_FILE))
        self.catalog = Catalog(os.path.join(path, CATALOG_FILE))
        self.executor = Executor(self)
        self._heaps = {}

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def execute(self, sql: str) -> Result:
        """Execute a single SQL statement and return a Result."""
        return self.executor.execute(parse(sql))

    def execute_script(self, script: str) -> List[Result]:
        """Execute a `;`-separated script, returning one Result per statement."""
        return [self.executor.execute(stmt) for stmt in parse_script(script)]

    def tables(self) -> List[str]:
        return self.catalog.names()

    def schema(self, table: str) -> TableSchema:
        return self.catalog.get(table)

    def table_info(self, table: str) -> List[dict]:
        """Lightweight, UI-friendly description of a table's columns."""
        schema = self.catalog.get(table)
        return [
            {
                "name": c.name,
                "type": c.type.value,
                "nullable": c.nullable,
                "primary_key": c.primary_key,
            }
            for c in schema.columns
        ]

    def flush(self):
        self.pager.flush()

    def close(self):
        self.pager.close()

    def reset(self):
        self.pager.close()
        for name in ("data.db", "catalog.json"):
            path = os.path.join(self.path, name)
            if os.path.exists(path):
                os.remove(path)

        # Recreate the storage layer from scratch.
        self.pager = Pager(os.path.join(self.path, DATA_FILE))
        self.catalog = Catalog(os.path.join(self.path, CATALOG_FILE))
        self.executor = Executor(self)
        self._heaps = {}
    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    def heap_for(self, schema: TableSchema) -> HeapFile:
        heap = self._heaps.get(schema.name)
        if heap is None:
            heap = HeapFile(self.pager, schema.first_page) # pyright: ignore[reportArgumentType]
            self._heaps[schema.name] = heap
        return heap

    # ------------------------------------------------------------------ #
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __repr__(self):
        return f"<Database path={self.path!r} tables={len(self.catalog.tables)}>"