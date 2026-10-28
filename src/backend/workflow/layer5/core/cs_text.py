"""
core/cs_text.py — Literal/comment-aware C# text helpers (no Roslyn needed).

Generated ViewModels are patched textually; counting braces naively breaks on bodies such as
`Debug.WriteLine("}")` or `$"{x}"`. Every helper here works on a "masked" copy of the source in
which string/char literals and comments are blanked (same length, newlines kept), so brackets
and keywords are only ever matched in real code.
"""
from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Iterable

_PAIRS = {"{": "}", "(": ")", "[": "]"}

# Modifiers that start a member declaration (masked text, line anchored).
_DECL_START = (
    r"(?m)^[ \t]*(?:(?:public|private|protected|internal|static|virtual|override|async|sealed|new"
    r"|partial|extern|unsafe)\s+)+"
)
_RETURN_TYPE = r"[\w<>\[\],.?:\s]*?"
_SKIP_DIRS = {"bin", "obj", "node_modules", ".git"}


# ── Lexing ──────────────────────────────────────────────────────────────────

def _scan_char(text: str, i: int) -> int:
    """End index of the char literal starting at text[i] == "'" (i + 1 if it is not one)."""
    n = len(text)
    k = i + 2 if i + 1 < n and text[i + 1] == "\\" else i + 1
    k += 1
    limit = min(n, i + 12)
    while k < limit and text[k] != "'":
        k += 1
    return k + 1 if k < limit and text[k] == "'" else i + 1


def _skip_interpolation(text: str, k: int) -> int:
    """End index of the `{...}` hole of an interpolated string starting at text[k] == "{"."""
    depth, n = 0, len(text)
    while k < n:
        c = text[k]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return k + 1
        elif c in '@$"':
            end = _scan_string(text, k)
            if end > k:
                k = end
                continue
        elif c == "'":
            k = _scan_char(text, k)
            continue
        k += 1
    return n


def _scan_string(text: str, i: int) -> int:
    """End index of the string literal starting at text[i] (i itself if none starts there)."""
    n, j = len(text), i
    verbatim = interpolated = False
    while j < n and text[j] in "@$" and j - i < 3:
        verbatim |= text[j] == "@"
        interpolated |= text[j] == "$"
        j += 1
    if j >= n or text[j] != '"':
        return i
    q = j
    while q < n and text[q] == '"':
        q += 1
    run = q - j
    if not verbatim and run >= 3:  # raw string literal """..."""
        end = text.find('"' * run, q)
        return n if end == -1 else end + run
    k = j + 1
    while k < n:
        c = text[k]
        if verbatim:
            if c == '"':
                if k + 1 < n and text[k + 1] == '"':
                    k += 2
                    continue
                return k + 1
        else:
            if c == "\\":
                k += 2
                continue
            if c == '"':
                return k + 1
            if c == "\n":  # unterminated literal: stop at the line end
                return k
        if interpolated and c == "{":
            if k + 1 < n and text[k + 1] == "{":
                k += 2
                continue
            k = _skip_interpolation(text, k)
            continue
        k += 1
    return n


def mask_non_code(text: str) -> str:
    """Same-length copy of `text` with literals and comments replaced by spaces."""
    out = list(text)
    i, n = 0, len(text)

    def blank(a: int, b: int) -> None:
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            end = text.find("\n", i)
            end = n if end == -1 else end
        elif ch == "/" and nxt == "*":
            end = text.find("*/", i + 2)
            end = n if end == -1 else end + 2
        elif ch == "'":
            end = _scan_char(text, i)
            if end == i + 1:
                i += 1
                continue
        elif ch in '@$"':
            end = _scan_string(text, i)
            if end == i:
                i += 1
                continue
        else:
            i += 1
            continue
        blank(i, end)
        i = end
    return "".join(out)


def find_matching(text: str, open_idx: int, masked: str | None = None) -> int:
    """Index of the bracket closing text[open_idx] ("{", "(" or "["), or -1 if unbalanced."""
    m = masked if masked is not None else mask_non_code(text)
    opener = m[open_idx]
    closer = _PAIRS[opener]
    depth = 0
    for k in range(open_idx, len(m)):
        c = m[k]
        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return k
    return -1


def split_top_level(text: str, start: int, end: int, masked: str | None = None) -> list[str]:
    """Split text[start:end] on commas that are not nested in (), [] or {}."""
    m = masked if masked is not None else mask_non_code(text)
    parts, depth, last = [], 0, start
    for k in range(start, end):
        c = m[k]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            parts.append(text[last:k])
            last = k + 1
    parts.append(text[last:end])
    return [p.strip() for p in parts]


# ── Method bodies ───────────────────────────────────────────────────────────

def _body_after_params(text: str, m: str, paren: int) -> tuple[int, int] | None:
    close = find_matching(text, paren, m)
    if close < 0:
        return None
    k = close + 1
    while k < len(m) and m[k].isspace():
        k += 1
    if k < len(m) and m[k] == "{":
        body_close = find_matching(text, k, m)
        if body_close > 0:
            return k, body_close
    return None


def find_method(text: str, name: str) -> tuple[int, int, int] | None:
    """(declaration start, body "{" index, body "}" index) of the first method `name` with a block body."""
    m = mask_non_code(text)
    pattern = re.compile(_DECL_START + _RETURN_TYPE + r"\b" + re.escape(name) + r"\s*\(")
    for mt in pattern.finditer(m):
        body = _body_after_params(text, m, mt.end() - 1)
        if body:
            return mt.start(), body[0], body[1]
    return None


def replace_method_body(text: str, name: str, body: str, indent: str = "        ") -> tuple[str, bool]:
    """Replace the block body of method `name`; returns (new text, replaced?)."""
    loc = find_method(text, name)
    if not loc:
        return text, False
    _, open_b, close_b = loc
    line_start = text.rfind("\n", 0, close_b) + 1
    closing_indent = text[line_start:close_b] if not text[line_start:close_b].strip() else "    "
    lines = textwrap.dedent(body).strip("\n").splitlines()
    inner = "\n".join(f"{indent}{ln}" if ln.strip() else "" for ln in lines)
    return f"{text[:open_b + 1]}\n{inner}\n{closing_indent}{text[close_b:]}", True


def extract_method_body(code: str) -> str:
    """Inner body when `code` is a whole method declaration (LLM output), else `code` stripped."""
    m = mask_non_code(code)
    mt = re.search(_DECL_START + _RETURN_TYPE + r"\b\w+\s*\(", m)
    if not mt or m[:mt.start()].strip():
        return code.strip()
    body = _body_after_params(code, m, mt.end() - 1)
    if not body:
        return code.strip()
    return textwrap.dedent(code[body[0] + 1:body[1]]).strip("\n")


# ── Solution lookups ────────────────────────────────────────────────────────

def _iter_cs_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if not root or not Path(root).is_dir():
            continue
        for path in Path(root).rglob("*.cs"):
            if not _SKIP_DIRS.intersection(path.parts):
                yield path


def _any_file_matches(pattern: re.Pattern, roots: Iterable[Path]) -> bool:
    for path in _iter_cs_files(roots):
        try:
            if pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
                return True
        except OSError:
            continue
    return False


def declares_namespace(namespace: str, roots: Iterable[Path]) -> bool:
    """True when some .cs file under `roots` declares `namespace <namespace>` (file-scoped or block)."""
    return _any_file_matches(re.compile(r"^\s*namespace\s+" + re.escape(namespace) + r"\s*[;{]", re.M), roots)


def declares_type(type_name: str, roots: Iterable[Path], kind: str = "interface") -> bool:
    """True when some .cs file under `roots` declares `<kind> <type_name>`."""
    return _any_file_matches(re.compile(rf"\b{kind}\s+{re.escape(type_name)}\b"), roots)
