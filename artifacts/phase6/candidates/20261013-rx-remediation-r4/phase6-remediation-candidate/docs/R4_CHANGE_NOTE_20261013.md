# R4 change note — 2026-10-13

## Purpose
R4 corrects a test-quality defect found during independent review of R3. The R3 frame-limit test compared an index relative to the extracted `OnInit()` body against an index relative to the entire EA source file. Such offsets are not comparable and could not establish the intended ordering.

## Changes
- Replaced the mixed-coordinate assertion with offsets calculated inside the same extracted `OnInit()` body.
- Asserted that the `InpMaxFrameBytes > 65536` guard precedes `FFBP_LoadFence()` and `ConnectBridge()` inside `OnInit()`.
- Confirmed from source that `SocketConnect()` is called inside `ConnectBridge()`, so the test checks the caller's order rather than looking for a socket call that is not present in `OnInit()`.
- Added a separate structural check for the `ReadFrame()` capacity guard and maximum buffered size.
- Removed generated Python cache directories from the package.
- Regenerated candidate test evidence and the internal SHA-256 manifest.

## Verification
- Full candidate suite: **22 passed in 8.04 s**.
- Static EA/invariant/frame-limit suite: **14 passed in 0.06 s**.
- The first R4 test attempt failed because it looked for `SocketConnect()` directly inside `OnInit()`. Source inspection showed that the call is nested in `ConnectBridge()`; the test was corrected to assert that `OnInit()` validates the input before invoking `ConnectBridge()`. The final runs above are the passing results.

## Limits and disposition
These are source-structure and Python-side tests only. No MetaEditor compile, MT5 terminal runtime, current Oct 12 source reconciliation, current EX5 identity, or broker-state test was performed. The full repository archive available here is dated Oct 9, while the canonical Oct 12 EA hash recorded in evidence is `95bc98a023869e1abca4b1a7e2186de2dd9228b802c4d9b52e3ccc460c53dcb8`; this candidate is not proven to be a patch against that exact file.

**Disposition remains BLOCKED / DEMO-ONLY / NO RELEASE APPROVAL.** No canonical repository files, deployed MT5 source/EX5, Git history, or live state files were changed.
