import ast
from pathlib import Path


def test_domain_and_application_do_not_import_external_frameworks() -> None:
    source_root = Path(__file__).parents[2] / "src" / "antfarm"
    forbidden = {
        "adapters",
        "aiohttp",
        "camel",
        "fastapi",
        "httpx",
        "oasis",
        "ollama",
        "openai",
        "requests",
        "sqlalchemy",
        "sqlite3",
    }
    for area in ("domain", "application", "ports"):
        for path in (source_root / area).glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = {
                node.names[0].name.split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
            }
            imports.update(
                (node.module or "").split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
            )
            assert imports.isdisjoint(forbidden), path
