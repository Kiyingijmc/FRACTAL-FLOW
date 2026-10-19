#!/usr/bin/env python3
"""Static gate: find log statements that print authentication material.

Scans MQL5 (.mq5/.mqh) for Print/PrintFormat/Comment/Alert/printf calls and Python
(.py) for print()/logging calls. A finding means a log call passes (or labels) a
value that is, or derives from, a secret: nonces, proofs, transcripts, MACs, session
keys, the shared secret. Lengths (StringLen/ArraySize/len) are NOT findings.

Severity:  HIGH   auth material (nonce/proof/transcript/mac/key/secret/entropy)
           MEDIUM raw frame/body/wire/payload dumps
           LOW    identifiers (session_id) - not secret by themselves; reported, not failing
Exit code: 0 clean at/above --fail-on (default MEDIUM), 1 findings, 2 usage/IO error.

This is a *source* gate. It does not inspect runtime logs; scan those separately
(see --scan-text) and rotate the test secret if anything is found there.
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys
from dataclasses import dataclass

SEV = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
HIGH_TOKEN = re.compile(
    r"(nonce|proof|transcript|secret|c2s|s2c|session_?key|entropy|hmac|passw|token)"
    r"|(^|_)(mac|key)($|_)", re.I)
MED_TOKEN = re.compile(r"^(body|wire|frame|payload|raw|msg|message|data)(_\w+)?$", re.I)
LOW_TOKEN = re.compile(r"session_?id", re.I)
# identifiers naming a location/handle (e.g. args.secret_env = the env VAR NAME), not a value
NAME_ONLY = re.compile(r"(_env|_name|_path|_file|_dir|_var)$", re.I)
LABEL = re.compile(
    r"\b(transcript\w*|proof|nonce|client_nonce|server_nonce|secret|session_?key|c2s|s2c|mac|hmac|key|signature)\b"
    r"\s*[=:]\s*%[-+ #0]*\d*[sdxXuliI]", re.I)
MQL_LOGGERS = ("Print", "PrintFormat", "Comment", "Alert", "printf", "SendNotification", "SendMail")
SAFE_WRAP = re.compile(r"\b(StringLen|ArraySize|ArrayRange|sizeof|GetLastError|len|ArrayCopy)\s*\(")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    severity: str
    why: str
    snippet: str


# ------------------------------------------------------------------ MQL5 --------
def _mask_comments(src: str) -> str:
    """Blank out // and /* */ comments (keeping newlines/offsets); respect string/char literals."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c in "\"'":
            q, j = c, i + 1
            while j < n and src[j] != q:
                j += 2 if src[j] == "\\" else 1
            out.append(src[i:j + 1]); i = j + 1
        elif src.startswith("//", i):
            j = src.find("\n", i); j = n if j < 0 else j
            out.append(" " * (j - i)); i = j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2); j = n if j < 0 else j + 2
            out.append("".join("\n" if ch == "\n" else " " for ch in src[i:j])); i = j
        else:
            out.append(c); i += 1
    return "".join(out)


def _balanced(src: str, start: int) -> int:
    """src[start-1] == '('. Return index just past the matching ')', honoring literals."""
    depth, i, n = 1, start, len(src)
    while i < n and depth:
        c = src[i]
        if c in "\"'":
            q, i = c, i + 1
            while i < n and src[i] != q:
                i += 2 if src[i] == "\\" else 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        i += 1
    return i


def _split_args(text: str) -> list[str]:
    args, depth, cur, i, n = [], 0, [], 0, len(text)
    while i < n:
        c = text[i]
        if c in "\"'":
            q, j = c, i + 1
            while j < n and text[j] != q:
                j += 2 if text[j] == "\\" else 1
            cur.append(text[i:j + 1]); i = j + 1; continue
        if c in "([{": depth += 1
        elif c in ")]}": depth -= 1
        if c == "," and depth == 0:
            args.append("".join(cur)); cur = []
        else:
            cur.append(c)
        i += 1
    args.append("".join(cur))
    return [a.strip() for a in args]


def _strip_safe(arg: str) -> str:
    """Remove StringLen(...)/ArraySize(...)/... calls and string-literal ternaries."""
    while True:
        m = SAFE_WRAP.search(arg)
        if not m:
            break
        arg = arg[:m.start()] + "0" + arg[_balanced(arg, m.end()):]
    return re.sub(r"\?\s*\"[^\"]*\"\s*:\s*\"[^\"]*\"", "", arg)


def _classify_tokens(text: str) -> tuple[str, str] | None:
    best: tuple[str, str] | None = None
    for tok in re.findall(r"[A-Za-z_]\w*", text):
        if NAME_ONLY.search(tok):
            continue
        sev = ("HIGH" if HIGH_TOKEN.search(tok) else "MEDIUM" if MED_TOKEN.match(tok)
               else "LOW" if LOW_TOKEN.search(tok) else None)
        if sev and (best is None or SEV[sev] > SEV[best[0]]):
            best = (sev, tok)
    return best


def scan_mql5(path: pathlib.Path, text: str) -> list[Finding]:
    masked = _mask_comments(text)
    findings: list[Finding] = []
    for m in re.finditer(r"\b(" + "|".join(MQL_LOGGERS) + r")\s*\(", masked):
        end = _balanced(masked, m.end())
        args = _split_args(masked[m.end():end - 1])
        fmt = args[0] if args else ""
        line = masked.count("\n", 0, m.start()) + 1
        snippet = " ".join(masked[m.start():end].split())[:160]
        hit = _classify_tokens(" , ".join(_strip_safe(a) for a in args[1:]))
        if hit and len(args) > 1:
            findings.append(Finding(str(path), line, hit[0], f"value argument '{hit[1]}' is logged", snippet))
            continue
        lab = LABEL.search(fmt)
        printed = [a for a in (_strip_safe(x) for x in args[1:]) if not re.fullmatch(r"[\s0-9]*", a)]
        if lab and "%" in fmt and printed:
            findings.append(Finding(str(path), line, "HIGH", f"format labels a value as '{lab.group(1)}'", snippet))
        elif len(args) == 1 and "%" not in fmt:
            hit = _classify_tokens(_strip_safe(fmt) if not fmt.startswith('"') else "")
            if hit:
                findings.append(Finding(str(path), line, hit[0], f"value '{hit[1]}' is logged", snippet))
    return findings


# ---------------------------------------------------------------- Python --------
class _PyVisitor(ast.NodeVisitor):
    LOG_ATTRS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}

    def __init__(self, path: str, lines: list[str]):
        self.path, self.lines, self.findings = path, lines, []

    def _is_logger(self, f: ast.expr) -> bool:
        if isinstance(f, ast.Name):
            return f.id == "print"
        if isinstance(f, ast.Attribute) and f.attr in self.LOG_ATTRS:
            recv = f.value        # logging.info / log.info / self.logger.info ; NOT parser.error
            name = recv.id if isinstance(recv, ast.Name) else recv.attr if isinstance(recv, ast.Attribute) else ""
            return "log" in name.lower()
        return False

    def _names(self, node: ast.AST) -> list[str]:
        out: list[str] = []

        def walk(n: ast.AST) -> None:
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("len", "bool", "int"):
                return  # lengths / flags are not secret
            if isinstance(n, ast.Name):
                out.append(n.id)
            elif isinstance(n, ast.Attribute):
                out.append(n.attr); walk(n.value)
                return
            for ch in ast.iter_child_nodes(n):
                walk(ch)
        walk(node)
        return out

    def visit_Call(self, node: ast.Call) -> None:
        if self._is_logger(node.func):
            for arg in [*node.args, *[k.value for k in node.keywords]]:
                hit = _classify_tokens(" ".join(self._names(arg)))
                if hit:
                    snip = " ".join(self.lines[node.lineno - 1].split())[:160]
                    self.findings.append(Finding(self.path, node.lineno, hit[0], f"value '{hit[1]}' is logged", snip))
                    break
        self.generic_visit(node)


def scan_python(path: pathlib.Path, text: str) -> list[Finding]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [Finding(str(path), exc.lineno or 0, "HIGH", "unparseable Python (cannot certify)", "")]
    v = _PyVisitor(str(path), text.splitlines())
    v.visit(tree)
    return v.findings


# ------------------------------------------------------------------ driver ------
def scan_path(path: pathlib.Path) -> list[Finding]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix in (".mq5", ".mqh"):
        return scan_mql5(path, text)
    if path.suffix == ".py":
        return scan_python(path, text)
    return []


def scan_runtime_text(path: pathlib.Path, secret_values: list[str]) -> list[Finding]:
    """Log-file mode: flag any line containing a literal secret value or a long hex blob after a sensitive label."""
    out: list[Finding] = []
    blob = re.compile(r"(nonce|proof|transcript|mac|key)\w*\s*[=:]\s*[0-9a-fA-F]{32,}", re.I)
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if any(s and s in line for s in secret_values):
            out.append(Finding(str(path), i, "HIGH", "literal secret value present", "<redacted>"))
        elif blob.search(line):
            out.append(Finding(str(path), i, "HIGH", "sensitive label followed by hex blob", line[:80] + "..."))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="files or directories (.mq5 .mqh .py)")
    ap.add_argument("--fail-on", choices=list(SEV), default="MEDIUM")
    ap.add_argument("--scan-text", action="store_true", help="treat paths as runtime logs")
    ap.add_argument("--secret-env", action="append", default=[], help="env var whose VALUE must not appear in logs")
    args = ap.parse_args(argv)
    import os
    secrets = [os.environ.get(n, "") for n in args.secret_env]
    files: list[pathlib.Path] = []
    for p in map(pathlib.Path, args.paths):
        if p.is_dir():
            files += sorted(x for x in p.rglob("*") if x.suffix in (".mq5", ".mqh", ".py", ".log", ".txt") and x.is_file())
        elif p.is_file():
            files.append(p)
        else:
            print(f"error: {p} not found", file=sys.stderr); return 2
    findings: list[Finding] = []
    for f in files:
        findings += scan_runtime_text(f, secrets) if args.scan_text else scan_path(f)
    findings.sort(key=lambda x: (x.path, x.line))
    for f in findings:
        print(f"{f.severity:6s} {f.path}:{f.line}: {f.why}\n       {f.snippet}")
    bad = [f for f in findings if SEV[f.severity] >= SEV[args.fail_on]]
    print(f"\nscanned={len(files)} findings={len(findings)} failing(>={args.fail_on})={len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
