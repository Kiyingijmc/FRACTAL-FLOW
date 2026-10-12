# FRACTAL FLOW — ARCHITECTURAL HARDENING RECOMMENDATIONS
Version: 1.0
Status: Pre-Implementation Architectural Hardening

This document outlines architectural risks, governance gaps, and system complexity hazards identified during the pre-implementation audit, providing concrete mitigations and recommended follow-up documentation before Phase 1 coding commences.

---

## 1. Absence of Concrete Configuration Schema & Versioning Specification
* **Architectural Risk:**
  AGENTS.md Invariant #39 mandates: *"Configuration is versioned; news overlays must not overwrite the latest base configuration."* However, no doc defines the concrete file format (e.g. JSON/YAML/TOML), validation schema, or exact overlay merge semantics for system configuration files.
* **Failure Scenario:**
  A dynamic news restriction overlay mutates base system parameters in memory, corrupting baseline risk parameters permanently across restarts.
* **Concrete Mitigation:**
  1. Define a JSON Schema specification (`config.schema.json`) with strict versioning fields (`config_version`, `parent_config_version`).
  2. Implement configuration immutability in memory: base configuration objects MUST be read-only structs. Overlays generate ephemeral combined config instances (`ActiveConfiguration = BaseConfig.ApplyOverlay(NewsOverlay)`) without mutating `BaseConfig`.

---

## 2. Lack of Continuous Integration (CI) and Automated Architectural Guardrails
* **Architectural Risk:**
  The project currently has no CI pipeline workflows (e.g., `.github/workflows/ci.yml`), static analyzers, or automated doc-consistency checkers. Future coding agents or human contributors could re-introduce state machine contradictions or violate architectural invariants without detection.
* **Failure Scenario:**
  A developer commits code allowing Layer 2 PDE to directly call Layer 6 MT5 execution API, violating Invariant #3 without failing an automated test gate.
* **Concrete Mitigation:**
  1. Create a GitHub Actions workflow `.github/workflows/ci.yml` running unit, integration, and lineage invariant tests on every commit/PR.
  2. Add an AST-based static analyzer or lint rule enforcing layer isolation (e.g., prohibiting imports of Layer 6 execution modules inside Layer 2 strategy modules).

---

## 3. Scope vs. Effort Complexity across 17 Interdependent Strategy Engines
* **Architectural Risk:**
  FRACTAL FLOW specifies 17 distinct engines across 8 layers. Attempting a monolithic initial build creates high risk of architectural gridlock and incomplete safety mechanisms.
* **Failure Scenario:**
  Phase 1–4 modules built with mock stubs that are never replaced before Phase 6 live execution testing, leading to unhandled edge cases in live order routing.
* **Concrete Mitigation:**
  1. Strictly enforce the 8-phase implementation order defined in `CODEX_HANDOFF.md §3`. No live MT5 gateway code (Phase 6) may be committed until Phase 1–5 primitives, data quality, structure, opportunity, news, and risk engines are 100% verified via automated unit/integration test suites.
  2. Maintain a modular monolith folder structure (`src/primitives`, `src/engines/pde`, `src/gateway/mt5`), ensuring each engine can be tested in isolation using synthetic event streams.

---

## 4. Unspecified License & Governance Artifacts
* **Architectural Risk:**
  The repository lacks a `LICENSE` file or explicit open-source / proprietary license header.
* **Concrete Mitigation:**
  Add a standard `LICENSE` file (e.g., MIT, Apache 2.0, or Proprietary) in the repository root prior to initial source code contribution.

---

## 5. Broker Execution Edge Cases & Market Micromodel Gaps
* **Architectural Risk:**
  Forex brokers introduce real-world execution anomalies: asymmetrical slippage, requotes, spread widening during session rolls (21:00 UTC), partial order fills, and asynchronous disconnects.
* **Concrete Mitigation:**
  1. Implement an explicit `BrokerConstraints` state object evaluating current spread percentile, quote age, and broker stop-level distance before order submission.
  2. Require MT5 Gateway to handle asynchronous order states (`EXEC_UNKNOWN`, `EXEC_PARTIAL`) using persistent request tracking (`client_order_id`) and state reconciliation before retrying or cancelling.

---

## 6. Persistence & Event Sourcing Architecture
* **Architectural Risk:**
  `docs/14_RECONCILIATION.md` references event sourcing and state recovery after crash, but no database schema or state persistence mechanism (e.g., SQLite, RocksDB, PostgreSQL, JSON append log) is specified.
* **Concrete Mitigation:**
  Write a dedicated specification `docs/20_PERSISTENCE_SCHEMA.md` defining:
  - SQLite/RocksDB table schemas for state envelopes, opportunities, decisions, and broker order mappings.
  - Append-only event log schema for zero-loss crash recovery.
