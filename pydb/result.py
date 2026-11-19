"""The result object returned by every executed statement.

This is the *only* thing a future UI layer needs to consume.
"""

from dataclasses import dataclass, field
from typing import Any, List, Tuple


@dataclass
class Result:
    columns: List[str] = field(default_factory=list)
    rows: List[Tuple[Any, ...]] = field(default_factory=list)
    rowcount: int = 0
    message: str = ""

    # ------------------------------------------------------------------ #
    @property
    def is_query(self) -> bool:
        return bool(self.columns)

    def __iter__(self):
        return iter(self.rows)

    def __len__(self):
        return len(self.rows)

    def __repr__(self):
        if self.is_query:
            return f"<Result {len(self.rows)} row(s) x {len(self.columns)} col(s)>"
        return f"<Result {self.message or str(self.rowcount) + ' row(s) affected'}>"

    # ------------------------------------------------------------------ #
    def to_table(self, max_width: int = 40) -> str:
        """Render as a plain-text table (handy for the CLI; the UI can ignore it)."""
        if not self.is_query:
            return self.message or f"{self.rowcount} row(s) affected"

        def fmt(v):
            if v is None:
                return "NULL"
            if isinstance(v, bool):
                return "true" if v else "false"
            return str(v)

        header = list(self.columns)
        body = [[fmt(v) for v in row] for row in self.rows]

        widths = [len(h) for h in header]
        for row in body:
            for i, cell in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(cell))
        widths = [min(w, max_width) for w in widths]

        def clip(s, w):
            return s if len(s) <= w else s[: max(0, w - 1)] + "…"

        lines = [
            " | ".join(clip(h, widths[i]).ljust(widths[i]) for i, h in enumerate(header)),
            "-+-".join("-" * w for w in widths),
        ]
        for row in body:
            lines.append(
                " | ".join(clip(c, widths[i]).ljust(widths[i]) for i, c in enumerate(row))
            )
        lines.append(f"({len(body)} row{'s' if len(body) != 1 else ''})")
        return "\n".join(lines)