from ..base import logger as log
from rich.tree import Tree
from rich.console import Console
from rich.text import Text
from rich.style import Style

STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_MANUAL = "manual"

_console = Console(stderr=True)

_WARN_STYLE = Style(color="yellow")
_MANUAL_STYLE = Style(color="cyan")

_root: Tree = None
_scope: list[str] = []
_cache: dict[str, Tree] = {}


def push(name: str):
    _scope.append(name)


def pop():
    _scope.pop()


def _get_or_create(path: str) -> Tree:
    if path in _cache:
        return _cache[path]
    parts = path.split("/")
    label = parts[-1]
    parent_path = "/".join(parts[:-1])
    if parent_path:
        parent = _get_or_create(parent_path)
        n = parent.add(label)
    else:
        global _root
        _root = Tree(label)
        n = _root
    _cache[path] = n
    return n


def _node() -> Tree:
    if not _scope:
        return _root
    return _get_or_create("/".join(_scope))


def add_item(status: str, msg: str):
    if status == STATUS_OK:
        log.info(msg)
    elif status == STATUS_WARN:
        _node().add(Text(f"* {msg}", style=_WARN_STYLE))
    elif status == STATUS_MANUAL:
        _node().add(Text(f"* {msg}", style=_MANUAL_STYLE))


def add_warning(msg: str):
    _node().add(Text(f"* {msg}", style=_WARN_STYLE))


def clear():
    _cache.clear()
    _scope.clear()


def print_summary():
    if _root and len(_root.children) > 0:
        _console.print()
        _console.print(_root)
        _console.print()
