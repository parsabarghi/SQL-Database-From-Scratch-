"""Statement execution engine: AST in, Result out."""

from . import ast_nodes as ast
from .datatypes import coerce
from .errors import ConstraintError, ExecutionError
from .result import Result
from .row import decode_row, encode_row
from .schema import Column, TableSchema
from .storage.heap import HeapFile

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def truthy(value) -> bool:
    """SQL WHERE semantics: only TRUE keeps a row."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return len(value) > 0
    return bool(value)


def sort_key(value):
    """A total ordering key that is safe to compare across mixed types."""
    if value is None:
        return (0, 0)
    if isinstance(value, bool):
        return (1, int(value))
    if isinstance(value, (int, float)):
        return (2, value)
    return (3, str(value))


def compare(op: str, left, right):
    if left is None or right is None:
        return None                        # SQL three-valued logic
    try:
        if op == "=":
            return left == right
        if op in ("!=", "<>"):
            return left != right
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
    except TypeError:
        raise ExecutionError(
            f"cannot compare {type(left).__name__} with {type(right).__name__}"
        )
    raise ExecutionError(f"unsupported comparison operator: {op}")


# --------------------------------------------------------------------------- #
# executor
# --------------------------------------------------------------------------- #
class Executor:
    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------ #
    @property
    def catalog(self):
        return self.db.catalog

    @property
    def pager(self):
        return self.db.pager

    def execute(self, stmt) -> Result:
        if isinstance(stmt, ast.CreateTable):
            return self._create_table(stmt)
        if isinstance(stmt, ast.DropTable):
            return self._drop_table(stmt)
        if isinstance(stmt, ast.Insert):
            return self._insert(stmt)
        if isinstance(stmt, ast.Select):
            return self._select(stmt)
        if isinstance(stmt, ast.Update):
            return self._update(stmt)
        if isinstance(stmt, ast.Delete):
            return self._delete(stmt)
        raise ExecutionError(f"cannot execute {type(stmt).__name__}")

    # ------------------------------------------------------------------ #
    # DDL
    # ------------------------------------------------------------------ #
    def _create_table(self, stmt: ast.CreateTable) -> Result:
        name = stmt.name

        if self.catalog.exists(name):
            if stmt.if_not_exists:
                return Result(message=f"table '{name}' already exists (skipped)")
            raise ExecutionError(f"table '{name}' already exists")

        if not stmt.columns:
            raise ExecutionError("a table must have at least one column")

        columns = [
            Column(c.name, c.type, c.nullable, c.primary_key) for c in stmt.columns
        ]
        for col in columns:
            if col.primary_key:
                col.nullable = False

        if sum(1 for c in columns if c.primary_key) > 1:
            raise ExecutionError("only a single-column PRIMARY KEY is supported")

        first_page = self.pager.allocate_page().page_no
        self.catalog.add(TableSchema(name, columns, first_page))
        return Result(message=f"table '{name}' created")

    def _drop_table(self, stmt: ast.DropTable) -> Result:
        name = stmt.name
        if not self.catalog.exists(name):
            if stmt.if_exists:
                return Result(message=f"table '{name}' does not exist (skipped)")
            raise ExecutionError(f"no such table: {name}")

        # NOTE: pages of a dropped table are not reclaimed (v1 limitation).
        self.catalog.remove(name)
        self.db._heaps.pop(name, None)
        return Result(message=f"table '{name}' dropped")

    # ------------------------------------------------------------------ #
    # INSERT
    # ------------------------------------------------------------------ #
    def _insert(self, stmt: ast.Insert) -> Result:
        schema = self.catalog.get(stmt.table)
        heap = self.db.heap_for(schema)
        ncols = len(schema.columns)

        if stmt.columns:
            target_idx = []
            for cname in stmt.columns:
                idx = schema.index_of(cname)
                if idx is None:
                    raise ExecutionError(
                        f"no such column: {cname!r} "
                        f"(table '{schema.name}' has: "
                        f"{', '.join(c.name for c in schema.columns)})"
                    )
                target_idx.append(idx)
        else:
            target_idx = list(range(ncols))

        inserted = 0
        for row_no, exprs in enumerate(stmt.rows, start=1):
            if len(exprs) != len(target_idx):
                raise ExecutionError(
                    f"table '{schema.name}' expects "
                    f"{len(target_idx)} value(s) "
                    f"({', '.join(schema.columns[i].name for i in target_idx)}), "
                    f"but row {row_no} supplies {len(exprs)}"
                )

            values: list = [None] * ncols
            provided = [False] * ncols

            for idx, expr in zip(target_idx, exprs):
                # Defensive: should never fire now, but if it does we
                # want a real message, not an IndexError traceback.
                if idx < 0 or idx >= ncols:
                    raise ExecutionError(
                        f"internal error: column index {idx} is out of "
                        f"range for table '{schema.name}' "
                        f"({ncols} columns)"
                    )
                raw = self._eval_const(expr)
                values[idx] = coerce(raw, schema.columns[idx].type)
                provided[idx] = True

            self._check_constraints(schema, heap, values, provided)
            heap.insert(encode_row(schema, values))
            inserted += 1

        return Result(
            rowcount=inserted,
            message=f"{inserted} row(s) inserted into '{schema.name}'",
        )
    def _check_constraints(self, schema, heap, values, provided=None, skip_rid=None):
        for i, col in enumerate(schema.columns):
            if values[i] is None and not col.nullable:
                raise ConstraintError(f"column '{col.name}' cannot be NULL")

        pk_idx = schema.primary_key_index
        if pk_idx is None:
            return

        key = values[pk_idx]
        for rid, rec in heap.scan():
            if skip_rid is not None and rid == skip_rid:
                continue
            row = decode_row(schema, rec)
            if row[pk_idx] == key:
                raise ConstraintError(
                    f"duplicate PRIMARY KEY value {key!r} for column "
                    f"'{schema.columns[pk_idx].name}'"
                )

    # ------------------------------------------------------------------ #
    # SELECT
    # ------------------------------------------------------------------ #
    def _select(self, stmt: ast.Select) -> Result:
        schema = self.catalog.get(stmt.table)
        heap = self.db.heap_for(schema)

        # --- scan + filter ------------------------------------------------ #
        rows = []
        for _rid, rec in heap.scan():
            values = decode_row(schema, rec)
            if stmt.where is not None and not truthy(self._eval(stmt.where, values, schema)):
                continue
            rows.append(values)

        # --- ORDER BY ------------------------------------------------------ #
        if stmt.order_by:
            for col_name, desc in reversed(stmt.order_by):
                expr = self._resolve_order_expr(schema, stmt, col_name)
                rows.sort(
                    key=lambda r: sort_key(self._eval(expr, r, schema)),
                    reverse=desc,
                )

        # --- projection ----------------------------------------------------- #
        if stmt.star:
            out_columns = [c.name for c in schema.columns]
            out_rows = [tuple(r) for r in rows]
        else:
            out_columns = []
            for n, item in enumerate(stmt.items):
                if item.alias:
                    out_columns.append(item.alias)
                elif isinstance(item.expr, ast.ColumnRef):
                    out_columns.append(item.expr.name)
                else:
                    out_columns.append(f"column{n + 1}")

            out_rows = [
                tuple(self._eval(item.expr, r, schema) for item in stmt.items)
                for r in rows
            ]

        # --- OFFSET / LIMIT -------------------------------------------------- #
        if stmt.offset:
            out_rows = out_rows[stmt.offset:]
        if stmt.limit is not None:
            out_rows = out_rows[: stmt.limit]

        return Result(columns=out_columns, rows=out_rows, rowcount=len(out_rows))

    def _resolve_order_expr(self, schema, stmt: ast.Select, name: str):
        """ORDER BY may reference a real column or a projection alias."""
        if schema.index_of(name) is not None:
            return ast.ColumnRef(name)
        for item in stmt.items:
            if item.alias == name:
                return item.expr
        raise ExecutionError(f"cannot ORDER BY unknown column '{name}'")

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #
    def _update(self, stmt: ast.Update) -> Result:
        schema = self.catalog.get(stmt.table)
        heap = self.db.heap_for(schema)

        targets = []
        for rid, rec in heap.scan():
            values = decode_row(schema, rec)
            if stmt.where is not None and not truthy(self._eval(stmt.where, values, schema)):
                continue
            targets.append((rid, values))

        assignments = []
        for col_name, expr in stmt.assignments:
            idx = schema.index_of(col_name)
            if idx is None:
                raise ExecutionError(f"no such column: {col_name}")
            assignments.append((idx, expr))

        updated = 0
        for rid, old_values in targets:
            new_values = list(old_values)
            for idx, expr in assignments:
                raw = self._eval(expr, old_values, schema)
                new_values[idx] = coerce(raw, schema.columns[idx].type)

            self._check_constraints(schema, heap, new_values, skip_rid=rid)
            heap.update(rid, encode_row(schema, new_values))
            updated += 1

        return Result(rowcount=updated, message=f"{updated} row(s) updated")

    # ------------------------------------------------------------------ #
    # DELETE
    # ------------------------------------------------------------------ #
    def _delete(self, stmt: ast.Delete) -> Result:
        schema = self.catalog.get(stmt.table)
        heap = self.db.heap_for(schema)

        targets = []
        for rid, rec in heap.scan():
            values = decode_row(schema, rec)
            if stmt.where is not None and not truthy(self._eval(stmt.where, values, schema)):
                continue
            targets.append(rid)

        for rid in targets:
            heap.delete(rid)

        return Result(rowcount=len(targets), message=f"{len(targets)} row(s) deleted")

    # ------------------------------------------------------------------ #
    # expression evaluation
    # ------------------------------------------------------------------ #
    def _eval(self, expr, row, schema):
        if isinstance(expr, ast.Literal):
            return expr.value

        if isinstance(expr, ast.ColumnRef):
            idx = schema.index_of(expr.name)
            if idx is None:
                raise ExecutionError(f"no such column: {expr.name}")
            return row[idx]

        if isinstance(expr, ast.UnaryOp):
            value = self._eval(expr.operand, row, schema)
            if expr.op == "NOT":
                if value is None:
                    return None
                return not truthy(value)
            if expr.op == "-":
                return None if value is None else -value
            raise ExecutionError(f"unsupported unary operator: {expr.op}")

        if isinstance(expr, ast.BinaryOp):
            op = expr.op
            if op == "AND":
                left = truthy(self._eval(expr.left, row, schema))
                right = truthy(self._eval(expr.right, row, schema))
                return left and right
            if op == "OR":
                left = truthy(self._eval(expr.left, row, schema))
                right = truthy(self._eval(expr.right, row, schema))
                return left or right

            left = self._eval(expr.left, row, schema)
            right = self._eval(expr.right, row, schema)
            return compare(op, left, right)

        raise ExecutionError(f"cannot evaluate expression: {expr!r}")

    def _eval_const(self, expr):
        """Evaluate an expression that may not reference any column."""
        if isinstance(expr, ast.Literal):
            return expr.value
        if isinstance(expr, ast.UnaryOp):
            value = self._eval_const(expr.operand)
            if expr.op == "-":
                return None if value is None else -value
            if expr.op == "NOT":
                return None if value is None else (not truthy(value))
        raise ExecutionError("only literal values are allowed in this context")