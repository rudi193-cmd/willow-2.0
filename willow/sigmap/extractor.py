"""
willow/sigmap/extractor.py — AST-based code signature extractor.
b17: SMAP1  ΔΣ=42

Extracts up to 30 code signatures from Python source using ast module,
with regex fallback for FastAPI routes and non-Python language support
(JS/TS, Go, Rust, Ruby).
"""
import ast
import re
from pathlib import Path
from typing import Optional

_MAX_SIGS = 30

# ── Python AST extractor ──────────────────────────────────────────────────────

def _annotation_str(node: Optional[ast.expr]) -> str:
    """Convert an AST annotation node to a string representation."""
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return "..."


def _args_str(args: ast.arguments) -> str:
    """Render function arguments as a compact string."""
    parts = []
    # positional-only args (before /)
    for i, arg in enumerate(args.posonlyargs):
        ann = f": {_annotation_str(arg.annotation)}" if arg.annotation else ""
        parts.append(f"{arg.arg}{ann}")
    if args.posonlyargs:
        parts.append("/")
    # regular args
    n_defaults = len(args.defaults)
    n_args = len(args.args)
    for i, arg in enumerate(args.args):
        ann = f": {_annotation_str(arg.annotation)}" if arg.annotation else ""
        default_idx = i - (n_args - n_defaults)
        if default_idx >= 0:
            default = f" = {ast.unparse(args.defaults[default_idx])}"
        else:
            default = ""
        parts.append(f"{arg.arg}{ann}{default}")
    if args.vararg:
        ann = f": {_annotation_str(args.vararg.annotation)}" if args.vararg.annotation else ""
        parts.append(f"*{args.vararg.arg}{ann}")
    elif args.kwonlyargs:
        parts.append("*")
    for i, arg in enumerate(args.kwonlyargs):
        ann = f": {_annotation_str(arg.annotation)}" if arg.annotation else ""
        default = ""
        if i < len(args.kw_defaults) and args.kw_defaults[i] is not None:
            default = f" = {ast.unparse(args.kw_defaults[i])}"
        parts.append(f"{arg.arg}{ann}{default}")
    if args.kwarg:
        ann = f": {_annotation_str(args.kwarg.annotation)}" if args.kwarg.annotation else ""
        parts.append(f"**{args.kwarg.arg}{ann}")
    return ", ".join(parts)


def _is_dataclass_or_basemodel(node: ast.ClassDef) -> bool:
    """Return True if this class is a dataclass or Pydantic BaseModel subclass."""
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "dataclass":
            return True
        if isinstance(dec, ast.Attribute) and dec.attr == "dataclass":
            return True
    for base in node.bases:
        base_str = ast.unparse(base)
        if "BaseModel" in base_str or "BaseSettings" in base_str:
            return True
    return False


def _class_fields(node: ast.ClassDef) -> list[str]:
    """Extract field annotations from a dataclass/BaseModel class body."""
    fields = []
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            name = item.target.id
            ann = _annotation_str(item.annotation)
            fields.append(f"{name}: {ann}")
    return fields[:10]  # cap at 10 fields


def _fastapi_decorator_sig(decorator: ast.expr, func_name: str) -> Optional[str]:
    """If decorator is a FastAPI route decorator, return a sig string."""
    try:
        dec_str = ast.unparse(decorator)
        # Match router.get("/path"), app.post("/path"), etc.
        m = re.match(r'(\w+)\.(get|post|put|patch|delete)\((["\'])(.+?)\3', dec_str)
        if m:
            method = m.group(2).upper()
            path = m.group(4)
            return f"{method} {path} → {func_name}()"
    except Exception:
        pass
    return None


def extract(source: str, filepath: str = "") -> list[str]:
    """Return up to 30 signature strings from Python source.

    Uses ast.parse as primary parser. Falls back to [] on syntax error.
    Handles: classes, functions, async functions, FastAPI routes, class methods,
    ALL_CAPS constants, dataclasses, BaseModel subclasses.
    """
    sigs: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if len(sigs) >= _MAX_SIGS:
            break

        # ── Top-level classes ────────────────────────────────────────────────
        if isinstance(node, ast.ClassDef) and _is_top_level(tree, node):
            bases = [ast.unparse(b) for b in node.bases]
            base_str = f"({', '.join(bases)})" if bases else ""
            if _is_dataclass_or_basemodel(node):
                fields = _class_fields(node)
                if fields:
                    sigs.append(f"class {node.name}{base_str}: [{', '.join(fields)}]")
                else:
                    sigs.append(f"class {node.name}{base_str}")
            else:
                sigs.append(f"class {node.name}{base_str}")

            # Class-level ALL_CAPS constants (up to 3)
            caps_count = 0
            for item in node.body:
                if caps_count >= 3:
                    break
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and target.id.isupper():
                            try:
                                val = ast.unparse(item.value)
                            except Exception:
                                val = "..."
                            sigs.append(f"  {target.id} = {val}")
                            caps_count += 1
                            if len(sigs) >= _MAX_SIGS:
                                break
                elif isinstance(item, ast.AnnAssign):
                    if (isinstance(item.target, ast.Name) and
                            item.target.id.isupper()):
                        ann = _annotation_str(item.annotation)
                        sigs.append(f"  {item.target.id}: {ann}")
                        caps_count += 1

            # Class methods
            for item in node.body:
                if len(sigs) >= _MAX_SIGS:
                    break
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = item.name
                    # Skip private (single underscore prefix), allow dunder only __init__
                    if name.startswith("__") and name.endswith("__") and name != "__init__":
                        continue
                    if name.startswith("_") and not name.startswith("__"):
                        continue
                    prefix = "async " if isinstance(item, ast.AsyncFunctionDef) else ""
                    args = _args_str(item.args)
                    ret = f" -> {_annotation_str(item.returns)}" if item.returns else ""
                    sigs.append(f"  {prefix}def {name}({args}){ret}")

        # ── Top-level functions ──────────────────────────────────────────────
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_top_level(tree, node):
            name = node.name
            # Skip private _ prefix functions
            if name.startswith("_"):
                continue

            # FastAPI route decorators
            route_sig = None
            for dec in node.decorator_list:
                route_sig = _fastapi_decorator_sig(dec, name)
                if route_sig:
                    break

            prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
            args = _args_str(node.args)
            ret = f" -> {_annotation_str(node.returns)}" if node.returns else ""
            if route_sig:
                sigs.append(route_sig)
            else:
                sigs.append(f"{prefix}def {name}({args}){ret}")

    # Top-level ALL_CAPS constants (module-level)
    caps_count = 0
    for node in ast.walk(tree):
        if caps_count >= 3 or len(sigs) >= _MAX_SIGS:
            break
        if isinstance(node, ast.Assign) and _is_top_level(tree, node):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper() and len(target.id) > 1:
                    try:
                        val = ast.unparse(node.value)
                    except Exception:
                        val = "..."
                    sigs.append(f"{target.id} = {val}")
                    caps_count += 1

    return sigs[:_MAX_SIGS]


def _is_top_level(tree: ast.Module, node: ast.AST) -> bool:
    """Return True if node is a direct child of the module body."""
    return node in tree.body


# ── Non-Python regex extractors (ported from SigMap JS) ──────────────────────

_JS_PATTERNS = [
    # Export declarations
    re.compile(r'^export\s+(default\s+)?(async\s+)?function\s+(\w+)', re.MULTILINE),
    re.compile(r'^export\s+(default\s+)?class\s+(\w+)', re.MULTILINE),
    re.compile(r'^export\s+const\s+(\w+)\s*=\s*(async\s+)?\(', re.MULTILINE),
    re.compile(r'^export\s+const\s+(\w+)\s*=\s*(async\s+)?function', re.MULTILINE),
    # Top-level class/function
    re.compile(r'^(async\s+)?function\s+(\w+)\s*\(', re.MULTILINE),
    re.compile(r'^class\s+(\w+)(?:\s+extends\s+(\w+))?', re.MULTILINE),
    # Arrow functions assigned to const
    re.compile(r'^const\s+(\w+)\s*=\s*(async\s+)?\(.*?\)\s*=>', re.MULTILINE),
]

_GO_PATTERNS = [
    re.compile(r'^func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(', re.MULTILINE),
    re.compile(r'^type\s+(\w+)\s+struct\s*\{', re.MULTILINE),
    re.compile(r'^type\s+(\w+)\s+interface\s*\{', re.MULTILINE),
]

_RS_PATTERNS = [
    re.compile(r'^pub\s+(async\s+)?fn\s+(\w+)\s*[<(]', re.MULTILINE),
    re.compile(r'^(async\s+)?fn\s+(\w+)\s*[<(]', re.MULTILINE),
    re.compile(r'^pub\s+struct\s+(\w+)', re.MULTILINE),
    re.compile(r'^struct\s+(\w+)', re.MULTILINE),
    re.compile(r'^pub\s+enum\s+(\w+)', re.MULTILINE),
    re.compile(r'^enum\s+(\w+)', re.MULTILINE),
    re.compile(r'^impl(?:<[^>]+>)?\s+(\w+)', re.MULTILINE),
]

_RB_PATTERNS = [
    re.compile(r'^\s*def\s+(self\.)?(\w+)', re.MULTILINE),
    re.compile(r'^\s*class\s+(\w+)(?:\s*<\s*(\w+))?', re.MULTILINE),
    re.compile(r'^\s*module\s+(\w+)', re.MULTILINE),
]


def _extract_regex(source: str, patterns: list[re.Pattern]) -> list[str]:
    """Extract signature-like strings using a list of regex patterns."""
    sigs = []
    seen = set()
    source.splitlines()
    for pat in patterns:
        for m in pat.finditer(source):
            line_start = source.rfind("\n", 0, m.start()) + 1
            line_end = source.find("\n", m.start())
            if line_end == -1:
                line_end = len(source)
            line = source[line_start:line_end].strip()
            if line and line not in seen:
                seen.add(line)
                sigs.append(line[:120])  # cap line length
    return sigs[:_MAX_SIGS]


def extract_file(path: Path) -> list[str]:
    """Dispatch to language-specific extractor by file extension.

    Reads the file from disk. Returns [] on read errors.
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    ext = path.suffix.lower()
    if ext == ".py":
        return extract(source, str(path))
    elif ext in (".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"):
        return _extract_regex(source, _JS_PATTERNS)
    elif ext == ".go":
        return _extract_regex(source, _GO_PATTERNS)
    elif ext == ".rs":
        return _extract_regex(source, _RS_PATTERNS)
    elif ext == ".rb":
        return _extract_regex(source, _RB_PATTERNS)
    else:
        return []
