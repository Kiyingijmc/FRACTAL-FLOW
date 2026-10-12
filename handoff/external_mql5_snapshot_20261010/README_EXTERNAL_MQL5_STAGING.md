# External MQL5 Source Evidence Staging — 2026-10-10

## Purpose

This directory is a **temporary, provenance-preserving snapshot staging area** for relevant MQL5 source files that live outside the `~/projects/FractalFlow` repository, especially files under the active MetaTrader 5 terminal data directory. It exists so a project snapshot can carry those files and the evidence needed to identify their original locations.

It is not a declaration that any copied file is canonical, current, deployed, compiled, or loaded by MT5.

## Non-negotiable safety rules

1. **Copy, never move.** The staging operation must not edit, rename, overwrite, or delete originals.
2. **Do not infer identity from a filename.** Canonical repository files, deployed terminal copies, nested deployed includes, global includes, packaged variants, backups, and test harnesses must remain distinct roles.
3. **Record absolute original paths and SHA-256 hashes** for every copied file, plus size and UTC timestamp where available. Hash the source before copying and the staged copy after copying; they must match.
4. **Keep every variant.** Do not silently select one EA/include version or reconcile diffs during staging.
5. **No secrets.** Do not stage environment files, credentials, shared secrets, private keys, account tokens, or logs containing secrets. If uncertain, omit and record the omission.
6. **Snapshot the working tree as-is.** Do not reset, clean, stash, or overwrite existing repository work. This folder itself may be untracked and should be included in the handoff snapshot.
7. **No automatic cleanup.** Do not delete this folder as part of copying, hashing, or snapshot creation.
8. **Cleanup is a separate, explicit gate.** Only after a fresh GPT session has examined the snapshot, confirmed each original path exists (or recorded that it no longer exists), independently recomputed source and staged SHA-256 hashes, compared variants, and confirmed that the archive contains the staged files and manifests may cleanup be considered. The session must provide a report and an exact, narrowly scoped cleanup command. The user executes it after reviewing the report. A missing path, hash mismatch, ambiguity, or unavailable terminal is a STOP condition: preserve the folder.

## Expected contents

- `files/`: copies grouped by provenance role; the directory names must not imply canonical status.
- `EXTERNAL_MQL5_SOURCE_INVENTORY.tsv`: one row per source file with role, original absolute path, staged relative path, SHA-256 before/after, byte size, source mtime UTC, and copy status.
- `SHA256SUMS_STAGED.txt`: hashes of staged source copies, relative to this directory.
- `STAGING_RUN_METADATA.txt`: date, host, repository root, terminal data root, script version, and any paths that were inaccessible or omitted.
- This README.

## Roles to preserve distinctly

At minimum, classify discovered files as one of:

- `REPOSITORY_CANONICAL` — already in the project; normally do not duplicate into this external staging folder.
- `MT5_DEPLOYED_NESTED` — deployed EA/include copy within the terminal's nested Experts/Indicators/Scripts or project-specific folder.
- `MT5_GLOBAL_INCLUDE` — relevant files under the terminal's `MQL5/Include` tree.
- `PACKAGED_VARIANT` — separately named packaged EA or alternate source build.
- `BACKUP_OR_PRE_SYNC` — backup or pre-sync copy; retain as evidence, never promote implicitly.
- `TEST_OR_DIAGNOSTIC` — self-tests, smoke helpers, diagnostic harnesses.
- `UNCLASSIFIED` — role not established; retain and request review.

The same basename at different paths is not a duplicate until byte hashes and provenance have been compared.

## Verification checklist for the fresh GPT session

- [ ] Read this README and the inventory before source analysis.
- [ ] Treat the repository snapshot and this staging folder as evidence, not as live filesystem access.
- [ ] Recompute hashes for every staged file and verify against the manifest.
- [ ] Inspect the original-path inventory and distinguish currently reachable originals from paths merely recorded historically.
- [ ] If live WSL/Windows access is unavailable, explicitly state that original location and deployment identity are **not independently verified**. Do not claim confirmation from a snapshot alone.
- [ ] Compare repository canonical, deployed nested, global include, packaged, and backup variants without overwriting any.
- [ ] Record exact source/deployment identity and remaining differences in the HPL/evidence log.
- [ ] Confirm the final snapshot archive contains this folder and the manifests, and verify the archive after creation.
- [ ] Only then may the session recommend cleanup. Preserve the inventory, hashes, and original files; cleanup must never touch original MT5 files.

## Important limitation

A hash proves byte identity between the specific bytes hashed; it does not prove that MT5 loaded or compiled those bytes. Deployment identity still requires path reconciliation and suitable terminal/compiler/runtime evidence.
