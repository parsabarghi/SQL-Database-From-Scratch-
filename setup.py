import os

FILES = [
    "pydb/__init__.py",
    "pydb/cli.py",
    "pydb/database.py",
    "pydb/catalog.py",
    "pydb/executor.py",
    "pydb/parser.py",
    "pydb/tokenizer.py",
    "pydb/ast_nodes.py",
    "pydb/schema.py",
    "pydb/row.py",
    "pydb/datatypes.py",
    "pydb/result.py",
    "pydb/errors.py",
    "pydb/storage/__init__.py",
    "pydb/storage/pager.py",
    "pydb/storage/slotted.py",
    "pydb/storage/heap.py",
]

for path in FILES:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        open(path, "w").close()
        print(f"created {path}")
    else:
        print(f"exists  {path}")

print("\nDone. Now u can use this on your pc if you need it. Parsa:>")