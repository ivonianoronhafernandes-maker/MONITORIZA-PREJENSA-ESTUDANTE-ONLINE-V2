"""Interface language: Tetum (the language of the source code), English or Indonesia.

The screen texts are written in Tetum inside the pages. For another language the page modules are
loaded through an import hook that swaps every known Tetum text for its translation (see
``i18n_dict.py``) before the code runs. A single text therefore has the same meaning everywhere in a
module, which keeps filters such as "All Classes" working in every language.

``ensure(language)`` is called at the top of App.py on every Streamlit rerun: when the saved language
changed, the page modules are dropped from ``sys.modules`` and loaded again in the new language.
"""
from __future__ import annotations

import ast
import importlib.abc
import importlib.machinery
import sqlite3
import sys

from src.core.config import settings
from src.core.i18n_dict import DICT

LANGUAGES = ["Tetum", "English", "Indonesia"]
DEFAULT = "Tetum"
_COLUMN = {"English": 0, "Indonesia": 1}
# Modules whose texts are translated (and reloaded when the language changes).
_PREFIXES = ("src.ui",)
_MODULES = {
    "src.services.attendance_service", "src.services.import_service", "src.services.settings_service",
    "src.services.report_service", "src.services.course_service", "src.services.class_service",
}
_state = {"lang": None}


def current_language() -> str:
    """Saved language, read straight from SQLite (the app database may not exist yet on first start)."""
    try:
        con = sqlite3.connect(str(settings.database_path), timeout=2)
        try:
            row = con.execute("SELECT value FROM app_settings WHERE key = 'language'").fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return DEFAULT
    return row[0] if row and row[0] in LANGUAGES else DEFAULT


def _table(lang: str) -> dict[str, str]:
    col = _COLUMN.get(lang)
    if col is None:
        return {}
    return {k: v[col] for k, v in DICT.items()}


def translate(text: str, lang: str) -> str:
    """Translate one string (used by App.py; the page modules use the import hook below)."""
    table = _table(lang)
    return _swap(text, table, _long_keys(table)) if table else text


def t(text: str) -> str:
    return translate(text, _state["lang"] or DEFAULT)


def _long_keys(table: dict[str, str]) -> list[str]:
    return sorted((k for k in table if len(k.strip()) >= 14), key=len, reverse=True)


def _swap(value: str, table: dict[str, str], long_keys: list[str]) -> str:
    stripped = value.strip()
    if stripped in table and stripped:
        lead = value[: len(value) - len(value.lstrip())]
        tail = value[len(value.rstrip()):]
        return lead + table[stripped] + tail
    if value in table:
        return table[value]
    if len(value) > 25 or "<" in value or "**" in value:
        for key in long_keys:
            if key in value:
                value = value.replace(key, table[key])
    return value


class _Transformer(ast.NodeTransformer):
    def __init__(self, table: dict[str, str]):
        self.table = table
        self.long_keys = _long_keys(table)

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, str) and node.value:
            node.value = _swap(node.value, self.table, self.long_keys)
        return node


class _Loader(importlib.machinery.SourceFileLoader):
    table: dict[str, str] = {}

    def get_code(self, fullname):  # never use the .pyc cache: it would mix languages
        return self.source_to_code(self.get_data(self.path), self.path)

    def source_to_code(self, data, path, *, _optimize=-1):
        tree = ast.parse(data, filename=str(path))
        tree = ast.fix_missing_locations(_Transformer(type(self).table).visit(tree))
        return compile(tree, str(path), "exec", dont_inherit=True, optimize=_optimize)


class _Finder(importlib.abc.MetaPathFinder):
    def __init__(self, table: dict[str, str]):
        self.loader_cls = type("TranslatingLoader", (_Loader,), {"table": table})

    def find_spec(self, fullname, path=None, target=None):
        if not (fullname.startswith(_PREFIXES) or fullname in _MODULES):
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec and isinstance(spec.loader, importlib.machinery.SourceFileLoader):
            spec.loader = self.loader_cls(spec.loader.name, spec.loader.path)
        return spec


def _purge() -> None:
    for name in list(sys.modules):
        if name.startswith(_PREFIXES) or name in _MODULES:
            del sys.modules[name]
            parent, _, child = name.rpartition(".")
            package = sys.modules.get(parent)
            if package is not None and hasattr(package, child):  # `from pkg import mod` reads this attribute
                delattr(package, child)


def ensure(lang: str | None = None) -> str:
    """Make the page modules match ``lang`` (default: the saved language). Returns the language in use."""
    lang = lang or current_language()
    if lang == _state["lang"]:
        return lang
    sys.meta_path[:] = [f for f in sys.meta_path if not isinstance(f, _Finder)]
    _purge()
    table = _table(lang)
    if table:
        sys.meta_path.insert(0, _Finder(table))
    _state["lang"] = lang
    return lang
