import ast
from pathlib import Path

CORE_FORBIDDEN = {
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


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    modules.update(
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    )
    return modules


def _has_prefix(module: str, prefixes: set[str]) -> bool:
    return any(
        module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes
    )


def test_core_imports_point_inward() -> None:
    source_root = Path(__file__).parents[2] / "src" / "antfarm"
    forbidden_by_area = {
        "domain": CORE_FORBIDDEN
        | {
            "antfarm.adapters",
            "antfarm.application",
            "antfarm.config",
            "antfarm.ports",
        },
        "ports": CORE_FORBIDDEN
        | {"antfarm.adapters", "antfarm.application", "antfarm.config"},
        "application": CORE_FORBIDDEN | {"antfarm.adapters", "antfarm.config"},
    }

    for area, forbidden in forbidden_by_area.items():
        for path in (source_root / area).glob("*.py"):
            violations = {
                module for module in _imports(path) if _has_prefix(module, forbidden)
            }
            assert not violations, f"{path}: {sorted(violations)}"
