# HALT Cross-Task Memory Store

- **Spec ID:** HALT-10
- **Version:** 1.0.0 (2026-08-25)
- **Depends on:** HALT-01 (D20), HALT-04 (formats style)

The Memory Store M is durable knowledge that OUTLIVES individual Task Instances: environment facts, reusable methods, user/authority preferences, post-mortems. It is deliberately boring: flat files, stable IDs, no retrieval magic — because per MemChar, construction/maintenance cost dominates memory-system economics, and per field experience, an index a fresh session can grep beats a clever database it cannot reach after a crash.

---

## 1. Boundary: W vs M

| | Workspace W (task artifacts) | Store M (cross-task knowledge) |
|---|---|---|
| Lifetime | one Task Instance | many tasks |
| Truth role | task state (ranks 1–4) | referenced knowledge (rank ~5; verify before reliance on time-sensitive items) |
| Written by | roles per grants | any agent via MEM protocol entries |
| Contains | journals, graphs, artifacts | env facts, methods/SOP refs, preferences, post-mortem digests |

**Rule MB-1.** Progress never lives in M ("we finished step 12"); method never lives only in W ("always probe before resume"). Violating this either pollutes the store with stale status or loses lessons at archive time.
**Rule MB-2.** At ARCHIVED (FST-3), the coordinator MUST propose M write-backs: what generalizes? (methods, pitfalls, authority preferences observed). Proposals go through the same supersede-not-edit pipeline as everything else.

---

## 2. Entry Format

```json
{"id":"MEM-0042",
 "kind":"env|method|preference|pitfall|postmortem",
 "scope":"global|project:<name>|user:<name>",
 "statement":"Free-tier model quotas on provider P are per-day; lowering concurrency slows the wall but never removes it.",
 "evidence_refs":["T-20260824-wave9","J-shard…seq…"],
 "created":"2026-08-24T17:20:00+08:00",
 "supersedes":["MEM-0017"],
 "freshness":"recheck-after:2026-09-30|stable"}
```

Rules:

- **Rule ME-1 (stable IDs + supersession).** Entries are never edited; corrections supersede (chain preserved). Reads resolve to chain heads.
- **Rule ME-2 (declarative phrasing).** Statements are facts about the world ("X is Y"), not imperatives to future agents ("always do Z") — imperatives age into traps when context shifts; facts remain checkable. Method recipes live in SOP cards / method entries that cite their trigger conditions instead.
- **Rule ME-3 (evidence-linked).** Every entry cites at least one task/evidence ref. Unlinked assertions are drafts, flagged `status:draft`, and do not outrank claims in the truth ladder until backed.
- **Rule ME-4 (bounded size & indexing).** The store keeps a compact index (`MEM-INDEX.md`: id → kind/scope/one-line gist). If the index exceeds what a fresh session reads comfortably (~hundreds of lines), it is re-summarized by consolidation passes — never silently truncated.

---

## 3. Read Protocol (freshness gate)

Before relying on an entry:

1. Resolve supersession chain to head.
2. Check `freshness`: if `recheck-after` passed OR the entry concerns mutable external state (quotas, tool paths, credentials existence), RE-VERIFY against reality before use.
3. Cite the entry id wherever its content influenced a Decision Record (INV-9 traceability extends to knowledge).

---

## 4. Write Protocol

```
W1 DRAFT   compose statement per ME-2, classify kind/scope
W2 LINK    attach evidence refs
W3 CHECK   search store for near-duplicates → supersede or merge instead of add
W4 COMMIT  append entry + update index atomically (one commit unit)
```

Consolidation (background job, MemChar admission-control principle): periodic pass merges duplicate chains, archives stale drafts, re-summarizes index — scheduled as S0 work with its own journal, never blocking task hot paths.

---

## 5. What Belongs in M (inclusion test)

Include when: (a) true beyond current task, (b) would change a future decision, (c) verifiable or honestly dated. Exclude: task progress (→W), raw data dumps (→artifacts), speculative opinions without evidence, anything the source authority would not recognize as theirs (preferences need provenance).

---

*End of HALT-10.*
