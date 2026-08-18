"""The Bazaar and Grist packages must stay independent of each other.

Only `app/gem_prices.py` is allowed to know about both. Source is scanned rather
than `sys.modules` inspected, so the result does not depend on what other tests
happened to import first.
"""

import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parent.parent / "app"


def _imported_modules(package: str) -> set[str]:
    found: set[str] = set()
    for path in (APP / package).glob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module)
    return found


def test_api_does_not_import_grist():
    assert not {m for m in _imported_modules("api") if m.startswith("app.grist")}


def test_grist_does_not_import_api():
    assert not {m for m in _imported_modules("grist") if m.startswith("app.api")}
