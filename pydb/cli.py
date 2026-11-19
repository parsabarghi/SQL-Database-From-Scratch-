"""A tiny REPL so the engine can be exercised before the UI exists.

    python -m pydb.cli ./mydb
"""

import sys

from .database import Database


BANNER = r"""
  ___      ___  ___
 | _ \_  _|   \| _ )    a relational database, from scratch
 |  _/ || | |) | _ \    version 0.1.0
 |_|  \_, |___/|___/
      |__/
"""

HELP = """\
Commands (no leading backslash needed if you type valid SQL):
  \\q, \\quit      exit
  \\h, \\help      show this message
  \\t, \\tables    list tables
  \\d <table>      describe a table
  \\drop <table>   to drop a table 
  \\reset          to rest everything
  \\f              flush to disk

SQL statements must end with a semicolon.
"""


def run_sql(db: Database, sql: str):
    for result in db.execute_script(sql):
        print(result.to_table())
        print()


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    path = argv[0] if argv else "mydb"

    db = Database(path)
    print(BANNER)
    print(f"  data directory: {path}")
    print("  type \\h for help, \\q to quit\n")

    buffer = ""
    try:
        while True:
            prompt = "pydb> " if not buffer.strip() else "  ...> "
            try:
                line = input(prompt)
            except KeyboardInterrupt:
                print("^c")
                buffer = ""
                continue
            except EOFError:
                print()
                break

            stripped = line.strip()

            # meta-commands only work outside a multi-line statement
            if stripped.startswith("\\"):
                cmd, _, arg = stripped.partition(" ")
                cmd = cmd.lower()

                if cmd in ("\\q", "\\quit", "\\exit"):
                    break
                if cmd in ("\\h", "\\help"):
                    print(HELP)
                    continue
                if cmd in ("\\t", "\\tables"):
                    names = db.tables()
                    print("\n".join(names) if names else "(no tables)")
                    continue
                if cmd == "\\d":
                    if not arg:
                        print("usage: \\d <table>")
                        continue
                    try:
                        info = db.table_info(arg)
                    except Exception as exc:
                        print(f"error: {exc}\n")
                        continue
                    print(f"table {arg}")
                    for c in info:
                        flags = []
                        if c["primary_key"]:
                            flags.append("PRIMARY KEY")
                        if not c["nullable"]:
                            flags.append("NOT NULL")
                        suffix = (" " + " ".join(flags)) if flags else ""
                        print(f"  {c['name']:<20} {c['type']:<8}{suffix}")
                    print()
                    continue
                if cmd == "\\drop":
                    if not arg:
                        print("usage: \\drop <table>")
                    try:
                        db.execute(f"DROP TABLE {arg}")
                        print(f"table '{arg}' dropped.\n")
                    except Exception as exc:
                        print(f"error: {exc}\n")
                    continue
                if cmd == "\\reset":
                    answer = input("wipe the entire database? [y/N] ").strip().lower()
                    if answer == "y":
                        db.reset()
                        print("database wiped.\n")
                    else:
                        print("cancelled.\n")
                    continue

                if cmd == "\\f":
                    db.flush()
                    print("flushed.\n")
                    continue

                print(f"unknown command: {cmd}\n")
                continue

            buffer += " " + line

            if ";" not in buffer:
                continue

            try:
                run_sql(db, buffer)
            except Exception as exc:
                print(f"error: {exc}\n")
            finally:
                buffer = ""
    finally:
        db.close()
        print("bye.")


if __name__ == "__main__":
    main()