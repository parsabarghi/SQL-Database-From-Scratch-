"""Recursive-descent SQL parser."""

from . import ast_nodes as ast
from .datatypes import DataType
from .errors import ExecutionError, ParseError
from .tokenizer import Token, tokenize


class Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.i = 0

    # ------------------------------------------------------------------ #
    # token helpers
    # ------------------------------------------------------------------ #
    @property
    def cur(self) -> Token:
        return self.toks[self.i]

    def advance(self) -> Token:
        t = self.toks[self.i]
        self.i += 1
        return t

    def at_keyword(self, *kws) -> bool:
        t = self.cur
        return t.kind == "keyword" and t.value in kws

    def accept_keyword(self, *kws) -> bool:
        if self.at_keyword(*kws):
            self.i += 1
            return True
        return False

    def expect_keyword(self, kw: str):
        if not self.accept_keyword(kw):
            raise ParseError(f"expected {kw}, found {self.cur.value!r}")

    def accept_punct(self, p: str) -> bool:
        if self.cur.kind == "punct" and self.cur.value == p:
            self.i += 1
            return True
        return False

    def expect_punct(self, p: str):
        if not self.accept_punct(p):
            raise ParseError(f"expected {p!r}, found {self.cur.value!r}")

    def accept_op(self, *ops) -> bool:
        if self.cur.kind == "op" and self.cur.value in ops:
            self.i += 1
            return True
        return False

    def expect_ident(self) -> str:
        t = self.cur
        if t.kind != "ident":
            raise ParseError(f"expected an identifier, found {t.value!r}")
        self.i += 1
        return t.value.lower()

    def expect_int(self) -> int:
        t = self.cur
        if t.kind != "number" or "." in t.value:
            raise ParseError(f"expected an integer, found {t.value!r}")
        self.i += 1
        return int(t.value)

    # ------------------------------------------------------------------ #
    # entry point
    # ------------------------------------------------------------------ #
    def parse_statement(self):
        t = self.cur
        if t.kind != "keyword":
            raise ParseError(f"expected a statement, found {t.value!r}")

        if t.value == "CREATE":
            stmt = self.parse_create()
        elif t.value == "DROP":
            stmt = self.parse_drop()
        elif t.value == "INSERT":
            stmt = self.parse_insert()
        elif t.value == "SELECT":
            stmt = self.parse_select()
        elif t.value == "UPDATE":
            stmt = self.parse_update()
        elif t.value == "DELETE":
            stmt = self.parse_delete()
        else:
            raise ParseError(f"unsupported statement: {t.value}")

        self.accept_punct(";")
        if self.cur.kind != "eof":
            raise ParseError(f"unexpected trailing token: {self.cur.value!r}")
        return stmt

    # ------------------------------------------------------------------ #
    # DDL
    # ------------------------------------------------------------------ #
    def parse_create(self):
        self.expect_keyword("CREATE")
        self.expect_keyword("TABLE")

        if_not_exists = False
        if self.accept_keyword("IF"):
            self.expect_keyword("NOT")
            self.expect_keyword("EXISTS")
            if_not_exists = True

        name = self.expect_ident()
        self.expect_punct("(")

        columns = []
        while True:
            columns.append(self.parse_column_def())
            if not self.accept_punct(","):
                break

        self.expect_punct(")")
        return ast.CreateTable(name, columns, if_not_exists)

    def parse_column_def(self):
        name = self.expect_ident()

        t = self.cur
        if t.kind != "keyword":
            raise ParseError(f"expected a column type, found {t.value!r}")
        self.i += 1
        try:
            dtype = DataType.from_name(t.value)
        except ExecutionError as exc:
            raise ParseError(str(exc))

        nullable = True
        primary_key = False

        while True:
            if self.accept_keyword("PRIMARY"):
                self.expect_keyword("KEY")
                primary_key = True
                nullable = False
            elif self.accept_keyword("NOT"):
                self.expect_keyword("NULL")
                nullable = False
            elif self.accept_keyword("NULL"):
                nullable = True
            elif self.accept_keyword("UNIQUE"):
                pass
            else:
                break

        return ast.ColumnDef(name, dtype, nullable, primary_key)

    def parse_drop(self):
        self.expect_keyword("DROP")
        self.expect_keyword("TABLE")
        if_exists = False
        if self.accept_keyword("IF"):
            self.expect_keyword("EXISTS")
            if_exists = True
        return ast.DropTable(self.expect_ident(), if_exists)

    # ------------------------------------------------------------------ #
    # DML
    # ------------------------------------------------------------------ #
    def parse_insert(self):
        self.expect_keyword("INSERT")
        self.expect_keyword("INTO")
        table = self.expect_ident()

        columns = None
        if self.accept_punct("("):
            columns = []
            while True:
                columns.append(self.expect_ident())
                if not self.accept_punct(","):
                    break
            self.expect_punct(")")

        self.expect_keyword("VALUES")

        rows = []
        while True:
            self.expect_punct("(")
            values = []
            while True:
                values.append(self.parse_expr())
                if not self.accept_punct(","):
                    break
            self.expect_punct(")")
            rows.append(values)
            if not self.accept_punct(","):
                break

        return ast.Insert(table, columns, rows)

    def parse_select(self):
        self.expect_keyword("SELECT")

        star = False
        items = []

        if self.accept_punct("*"):
            star = True
        else:
            while True:
                expr = self.parse_expr()
                alias = None
                if self.accept_keyword("AS"):
                    alias = self.expect_ident()
                elif self.cur.kind == "ident":
                    alias = self.advance().value.lower()
                items.append(ast.SelectItem(expr, alias))
                if not self.accept_punct(","):
                    break

        self.expect_keyword("FROM")
        table = self.expect_ident()

        where = None
        if self.accept_keyword("WHERE"):
            where = self.parse_expr()

        order_by = []
        if self.accept_keyword("ORDER"):
            self.expect_keyword("BY")
            while True:
                col = self.expect_ident()
                desc = False
                if self.accept_keyword("DESC"):
                    desc = True
                else:
                    self.accept_keyword("ASC")
                order_by.append((col, desc))
                if not self.accept_punct(","):
                    break

        limit = None
        offset = None
        if self.accept_keyword("LIMIT"):
            limit = self.expect_int()
        if self.accept_keyword("OFFSET"):
            offset = self.expect_int()

        return ast.Select(table, items, star, where, order_by, limit, offset)

    def parse_update(self):
        self.expect_keyword("UPDATE")
        table = self.expect_ident()
        self.expect_keyword("SET")

        assignments = []
        while True:
            col = self.expect_ident()
            if not self.accept_op("="):
                raise ParseError(f"expected '=' after column {col!r}")
            assignments.append((col, self.parse_expr()))
            if not self.accept_punct(","):
                break

        where = None
        if self.accept_keyword("WHERE"):
            where = self.parse_expr()

        return ast.Update(table, assignments, where)

    def parse_delete(self):
        self.expect_keyword("DELETE")
        self.expect_keyword("FROM")
        table = self.expect_ident()
        where = None
        if self.accept_keyword("WHERE"):
            where = self.parse_expr()
        return ast.Delete(table, where)

    # ------------------------------------------------------------------ #
    # expressions
    # ------------------------------------------------------------------ #
    def parse_expr(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.accept_keyword("OR"):
            left = ast.BinaryOp("OR", left, self.parse_and())
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.accept_keyword("AND"):
            left = ast.BinaryOp("AND", left, self.parse_not())
        return left

    def parse_not(self):
        if self.accept_keyword("NOT"):
            return ast.UnaryOp("NOT", self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_primary()
        if self.cur.kind == "op" and self.cur.value in ("=", "!=", "<>", "<", "<=", ">", ">="):
            op = self.advance().value
            right = self.parse_primary()
            return ast.BinaryOp(op, left, right)
        return left

    def parse_primary(self):
        # unary minus
        if self.cur.kind == "op" and self.cur.value == "-":
            self.i += 1
            return ast.UnaryOp("-", self.parse_primary())

        # parenthesised expression
        if self.accept_punct("("):
            expr = self.parse_expr()
            self.expect_punct(")")
            return expr

        t = self.cur

        if t.kind == "number":
            self.i += 1
            if "." in t.value:
                return ast.Literal(float(t.value))
            return ast.Literal(int(t.value))

        if t.kind == "string":
            self.i += 1
            return ast.Literal(t.value)

        if t.kind == "keyword":
            if t.value == "NULL":
                self.i += 1
                return ast.Literal(None)
            if t.value == "TRUE":
                self.i += 1
                return ast.Literal(True)
            if t.value == "FALSE":
                self.i += 1
                return ast.Literal(False)

        if t.kind == "ident":
            self.i += 1
            return ast.ColumnRef(t.value.lower())

        raise ParseError(f"unexpected token in expression: {t.value!r}")


def parse(sql: str):
    """Parse a single SQL statement."""
    return Parser(tokenize(sql)).parse_statement()


def parse_script(sql: str):
    """Parse a `;`-separated script into a list of statements."""
    tokens = tokenize(sql)
    chunks = []
    current = []

    for t in tokens:
        if t.kind == "punct" and t.value == ";":
            if current:
                chunks.append(current)
                current = []
        elif t.kind == "eof":
            if current:
                chunks.append(current)
        else:
            current.append(t)

    return [
        Parser(chunk + [Token("eof", None, 0)]).parse_statement()
        for chunk in chunks
    ]