"""A hand-written SQL lexer."""

from .errors import ParseError

KEYWORDS = {
    "CREATE", "TABLE", "DROP", "INSERT", "INTO", "VALUES",
    "SELECT", "FROM", "WHERE", "UPDATE", "SET", "DELETE",
    "AND", "OR", "NOT", "NULL", "TRUE", "FALSE",
    "ORDER", "BY", "ASC", "DESC", "LIMIT", "OFFSET",
    "PRIMARY", "KEY", "UNIQUE", "IF", "EXISTS", "AS", "DEFAULT",
    "INT", "INTEGER", "REAL", "TEXT", "BOOLEAN", "BOOL", "FLOAT", "DOUBLE",
    "VARCHAR", "CHAR", "NUMERIC", "DECIMAL",
}

_PUNCT = set("(),;*")
_OPERATORS_2 = ("<=", ">=", "<>", "!=")
_OPERATORS_1 = set("=<>+-/")


class Token:
    __slots__ = ("kind", "value", "pos")

    def __init__(self, kind: str, value, pos: int):
        self.kind = kind      # 'keyword' | 'ident' | 'number' | 'string' | 'op' | 'punct' | 'eof'
        self.value = value
        self.pos = pos

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r})"


def tokenize(sql: str):
    tokens = []
    i = 0
    n = len(sql)

    while i < n:
        c = sql[i]

        # -- whitespace ---------------------------------------------------- #
        if c.isspace():
            i += 1
            continue

        # -- line comment -------------------------------------------------- #
        if c == "-" and i + 1 < n and sql[i + 1] == "-":
            while i < n and sql[i] != "\n":
                i += 1
            continue

        # -- block comment ------------------------------------------------- #
        if c == "/" and i + 1 < n and sql[i + 1] == "*":
            end = sql.find("*/", i + 2)
            if end == -1:
                raise ParseError("unterminated block comment")
            i = end + 2
            continue

        # -- identifier / keyword ------------------------------------------ #
        if c.isalpha() or c == "_":
            j = i
            while j < n and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            word = sql[i:j]
            upper = word.upper()
            if upper in KEYWORDS:
                tokens.append(Token("keyword", upper, i))
            else:
                tokens.append(Token("ident", word, i))
            i = j
            continue

        # -- number --------------------------------------------------------- #
        if c.isdigit() or (c == "." and i + 1 < n and sql[i + 1].isdigit()):
            j = i
            seen_dot = False
            while j < n:
                ch = sql[j]
                if ch.isdigit():
                    j += 1
                elif ch == "." and not seen_dot:
                    seen_dot = True
                    j += 1
                else:
                    break
            text = sql[i:j]
            tokens.append(Token("number", text, i))
            i = j
            continue

        # -- string literal -------------------------------------------------- #
        if c == "'":
            j = i + 1
            buf = []
            while j < n:
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":   # escaped quote
                        buf.append("'")
                        j += 2
                        continue
                    break
                buf.append(sql[j])
                j += 1
            if j >= n:
                raise ParseError(f"unterminated string literal starting at {i}")
            tokens.append(Token("string", "".join(buf), i))
            i = j + 1
            continue

        # -- punctuation ----------------------------------------------------- #
        if c in _PUNCT:
            tokens.append(Token("punct", c, i))
            i += 1
            continue

        # -- operators -------------------------------------------------------- #
        two = sql[i:i + 2]
        if two in _OPERATORS_2:
            tokens.append(Token("op", two, i))
            i += 2
            continue
        if c in _OPERATORS_1:
            tokens.append(Token("op", c, i))
            i += 1
            continue

        raise ParseError(f"unexpected character {c!r} at position {i}")

    tokens.append(Token("eof", None, n))
    return tokens