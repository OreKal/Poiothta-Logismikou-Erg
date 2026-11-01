"""Fail when production logging calls include a student's email address."""

import ast
import sys
from pathlib import Path


LOG_METHODS = {"debug", "info", "warning", "error", "critical", "exception"}


def has_email_argument(call: ast.Call) -> bool:
    return any(
        isinstance(node, ast.Attribute) and node.attr == "email"
        for argument in call.args
        for node in ast.walk(argument)
    ) or any(
        isinstance(node, ast.Attribute) and node.attr == "email"
        for keyword in call.keywords
        for node in ast.walk(keyword.value)
    )


def scan(source_root: Path) -> list[tuple[Path, int]]:
    findings = []
    for path in source_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in LOG_METHODS
                and has_email_argument(node)
            ):
                findings.append((path, node.lineno))
    return findings


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {Path(sys.argv[0]).name} <production-source-directory>", file=sys.stderr)
        return 2

    source_root = Path(sys.argv[1])
    if not source_root.is_dir():
        print(f"Source directory does not exist: {source_root}", file=sys.stderr)
        return 2

    findings = scan(source_root)
    if findings:
        for path, line in findings:
            print(f"{path.relative_to(source_root)}:{line}: logger call includes an email address")
        return 1

    print("PASS: no email addresses in logging calls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
