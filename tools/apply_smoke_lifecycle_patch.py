#!/usr/bin/env python3
"""Guarded, backup-first patch for the FFBP smoke-server lifecycle mismatch."""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
from pathlib import Path
import sys


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"ABORT: {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="repository root (default: current directory)")
    args = parser.parse_args()
    root = Path(args.repo).resolve()
    server_path = root / "tools/ffbp_mt5_session_smoke_server.py"
    test_path = root / "tests/test_ffbp_mt5_smoke_server.py"
    if not server_path.is_file() or not test_path.is_file():
        fail("expected server/test paths not found under repository root")

    server = server_path.read_text(encoding="utf-8")
    test = test_path.read_text(encoding="utf-8")

    arg_anchor = '    ap.add_argument("--shared-secret", required=True)\n    args = ap.parse_args()\n'
    if server.count(arg_anchor) != 1:
        fail("server argument anchor not found exactly once; inspect current source before patching")

    hold_blocks = [
        (
            '            print("FFBP_SMOKE_DIAG connection_hold_seconds=30", flush=True)\n'
            '            time.sleep(30)\n            return 0\n',
            30.0,
        ),
        (
            '            print("FFBP_SMOKE_DIAG connection_hold_seconds=3", flush=True)\n'
            '            time.sleep(3)\n            return 0\n',
            3.0,
        ),
    ]
    matches = [(block, seconds) for block, seconds in hold_blocks if server.count(block) == 1]
    if len(matches) != 1:
        fail("expected exactly one known 30-second or 3-second hold block; inspect source")
    hold_block, default_hold = matches[0]
    if sum(server.count(block) for block, _ in hold_blocks) != 1:
        fail("hold block is ambiguous; inspect source")

    popen_anchor = (
        '            "--shared-secret",\n'
        '            secret.decode(),\n'
        '        ],\n'
    )
    if test.count(popen_anchor) != 1:
        fail("test Popen argument anchor not found exactly once; inspect test before patching")
    if "--hold-seconds" in test:
        fail("test already mentions --hold-seconds; refusing duplicate patch")

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    server_backup = server_path.with_name(server_path.name + f".pre-remediation-{stamp}.bak")
    test_backup = test_path.with_name(test_path.name + f".pre-remediation-{stamp}.bak")
    if server_backup.exists() or test_backup.exists():
        fail("backup path already exists; rerun to generate a new timestamp")

    # Create both backups before writing either source file.
    shutil.copy2(server_path, server_backup)
    shutil.copy2(test_path, test_backup)

    new_arg_anchor = (
        '    ap.add_argument("--shared-secret", required=True)\n'
        f'    ap.add_argument("--hold-seconds", type=float, default={default_hold:.1f})\n'
        '    args = ap.parse_args()\n'
        '    if args.hold_seconds < 0:\n'
        '        ap.error("--hold-seconds must be non-negative")\n'
    )
    new_hold_block = (
        '            print(\n'
        '                f"FFBP_SMOKE_DIAG connection_hold_seconds={args.hold_seconds:g}",\n'
        '                flush=True,\n'
        '            )\n'
        '            if args.hold_seconds:\n'
        '                time.sleep(args.hold_seconds)\n'
        '            return 0\n'
    )
    new_popen_anchor = (
        '            "--shared-secret",\n'
        '            secret.decode(),\n'
        '            "--hold-seconds",\n'
        '            "0",\n'
        '        ],\n'
    )

    patched_server = server.replace(arg_anchor, new_arg_anchor).replace(hold_block, new_hold_block)
    patched_test = test.replace(popen_anchor, new_popen_anchor)

    # Guard the result before touching the files.
    if patched_server.count('ap.add_argument("--hold-seconds"') != 1:
        fail("post-patch server guard failed; originals remain intact, backups created")
    if patched_server.count("time.sleep(args.hold_seconds)") != 1:
        fail("post-patch hold guard failed; originals remain intact, backups created")
    if patched_test.count('"--hold-seconds"') != 1 or patched_test.count('"0"') < 1:
        fail("post-patch test guard failed; originals remain intact, backups created")
    # Protocol assertions live in the server and client test respectively.
    for invariant in (
        'if ack.message_type != "ACK":',
        'if ack.sequence != 3:',
    ):
        if invariant not in patched_server:
            fail(f"expected server ACK assertion disappeared: {invariant}")
    if 'assert "FFBP_SMOKE_PASS" in output' not in patched_test:
        fail("expected smoke success assertion disappeared from test")

    server_path.write_text(patched_server, encoding="utf-8")
    test_path.write_text(patched_test, encoding="utf-8")

    print("PATCH_APPLIED")
    print(f"SERVER={server_path}")
    print(f"SERVER_BACKUP={server_backup}")
    print(f"TEST={test_path}")
    print(f"TEST_BACKUP={test_backup}")
    print(f"DEFAULT_HOLD_SECONDS={default_hold:g}")
    print("TEST_HOLD_SECONDS=0")
    print("NOTE=Handshake and ACK assertions intentionally unchanged.")
    print("NEXT=Run py_compile, focused pytest, git diff --check, and inspect diff.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
