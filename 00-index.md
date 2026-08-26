# HALT — Hierarchical Automaton for Long-horizon Tasks

**Version 1.0.2 · 2026-08-26 · Status: Stable** — v1.0.1 semantic hardening; v1.0.2 field-run amendments (see `12-validation-report.md`)
A process specification for running long-horizon tasks with AI agents — interruptible at any point, persistently memorized, arbitrarily nestable.

---

## Why

Long tasks fail not because agents can't reason, but because state lives in the wrong place: in conversations that vanish, in claims nobody verified, in checkpoints that outrun reality. HALT moves task truth into durable, auditable structures so that **any interruption costs at most its own unit of work** — and a brand-new session resumes from evidence, not memory. It composes four proven lineages (see `provenance.md`): hierarchical state machines (Statecharts), transactional workflow engines (AgentR), execution-state memory (MAGE/HiAgent/SciBORG), and manage-execute-audit separation (LongHorizon-Harness) — then hardens them against the failure modes observed in real multi-week agent operations (~40-slot parallel waves: worker death rates swinging 25%→75% within an hour; silent deaths; claim-vs-disk divergences; steering inputs lost to session death).

## The one-sentence model

> A task is a directed graph of nodes driven by journaled transactional state machines; progress exists only where write→verify→commit has completed; any agent — new or old, human or machine — resumes by asking *"where is my last provably stable position?"* and recomputing what may legally run next.

## Document Map

| Doc | Title | Read for |
|---|---|---|
| [01-core-model.md](01-core-model.md) | Core Model | axioms, definitions D1–D24, commit rule, side-effect classes S0–S3, truth hierarchy, invariants INV-1…10 |
| [02-lifecycle-fsm.md](02-lifecycle-fsm.md) | Lifecycle FSMs | node & task state machines, transition tables, verification levels, frontier computation, retry matrix |
| [03-sop-interface.md](03-sop-interface.md) | Uniform SOP Interface | SOP card, invocation/result documents, failure escalation map |
| [04-persistence-layout.md](04-persistence-layout.md) | Persistence Layout | workspace tree, journal/checkpoint/graph/registry formats |
| [05-recovery.md](05-recovery.md) | Recovery | R0–R7 procedure, interruption taxonomy, checkpoint regeneration, the interrupted-steering scenario |
| [06-nesting-composition.md](06-nesting-composition.md) | Nesting & Composition | parent-child contracts, namespace isolation, failure containment, depth limits |
| [07-parallel-dispatch.md](07-parallel-dispatch.md) | Parallel Dispatch | self-addressing contracts, slot accounting, adaptive modes, merge discipline |
| [08-roles-and-authority.md](08-roles-and-authority.md) | Roles & Authority | role partitions, grants, team patterns (works for humans too) |
| [09-human-gates-and-steering.md](09-human-gates-and-steering.md) | Human Gates & Steering | durable steering inbox, approval gates, escalation bundles |
| [10-memory-store.md](10-memory-store.md) | Memory Store | cross-task knowledge: W/M boundary, entry format, freshness gate |
| [11-conformance-and-derivations.md](11-conformance-and-derivations.md) | Conformance | self-audit checklist, requirement coverage, limitations |
| [12-validation-report.md](12-validation-report.md) | Validation Report | Field run `halt-fieldrun-01`: incident register, per-clause verdicts, amendments A-1..A-4, v1.1 fixture map |
| [glossary.md](glossary.md) | Glossary | every defined term, one authoritative definition each |
| [provenance.md](provenance.md) | Provenance | which paper/practice each mechanism comes from |
| zh/01-core-model.md | 中文版：核心模型 | Chinese edition of the core document |

## Reading Paths

- **Implementer:** 01 → 02 → 04 → 05 → 03 → then rest on demand.
- **Operator / sponsor:** 01 §1–2, §7; 09; 11 §C.
- **SOP author:** 03 → 06 → 02 §4.
- **Skeptic:** 05 §3 (interruption taxonomy) and 11 §D (honest limitations).

## Conformance Tiers

- **Tier 0 Trivial** — single session, restart-cheap: skip ceremony.
- **Tier 1 Standard** (default) — full artifact set + commit rule + recovery.
- **Tier 2 Critical/Fleet** — adds tx grouping, receipts everywhere, periodic audit walks, mirrored journals.

## Status & Scope Notes

v1 assumes single-writer-per-journal (one coordinator per instance); human-clock trust; semantic quality judged at V3 by humans. Multi-coordinator HA, formal verification tooling, and reference runtime are explicitly out of scope (see 11 §D). Feedback loops welcome through the same channels the spec prescribes: durably, please.
