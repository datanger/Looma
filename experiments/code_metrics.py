"""Small, reproducible source-code metric collector.

For the paper's programmability comparison, point this tool at directories that
contain only the implementation/orchestration code for each method. Shared
business logic should live outside those directories and is not counted.
"""

from __future__ import annotations

import argparse
import ast
import json
import tokenize
from pathlib import Path


IGNORED_TOKEN_TYPES = {
    tokenize.ENCODING,
    tokenize.ENDMARKER,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.NEWLINE,
    tokenize.NL,
    tokenize.COMMENT,
}


def python_sloc(path: Path) -> int:
    significant_lines: set[int] = set()
    with path.open("rb") as handle:
        for token in tokenize.tokenize(handle.readline):
            if token.type in IGNORED_TOKEN_TYPES:
                continue
            for line in range(token.start[0], token.end[0] + 1):
                significant_lines.add(line)
    return len(significant_lines)


def file_metrics(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    return {
        "path": str(path),
        "sloc": python_sloc(path),
        "functions": sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for node in ast.walk(tree)
        ),
        "classes": sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree)),
        "imports": sum(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree)),
        "calls": sum(isinstance(node, ast.Call) for node in ast.walk(tree)),
    }


def analyze_path(root: Path) -> dict:
    files = [root] if root.is_file() else sorted(root.rglob("*.py"))
    files = [path for path in files if "__pycache__" not in path.parts]
    rows = [file_metrics(path) for path in files]
    return {
        "root": str(root),
        "python_files": len(rows),
        "sloc": sum(row["sloc"] for row in rows),
        "functions": sum(row["functions"] for row in rows),
        "classes": sum(row["classes"] for row in rows),
        "imports": sum(row["imports"] for row in rows),
        "calls": sum(row["calls"] for row in rows),
        "files": rows,
    }


def parse_target(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("target must use LABEL=PATH")
    label, raw_path = value.split("=", 1)
    path = Path(raw_path).resolve()
    if not label or not path.exists():
        raise argparse.ArgumentTypeError(f"invalid target: {value}")
    return label, path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("targets", nargs="+", type=parse_target, metavar="LABEL=PATH")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = {
        "metric_definition": (
            "Python SLOC = source lines containing at least one non-comment, "
            "non-whitespace tokenize token. Shared business code should be excluded "
            "from per-framework orchestration directories."
        ),
        "implementations": {
            label: analyze_path(path) for label, path in args.targets
        },
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
