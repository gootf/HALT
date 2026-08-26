# 12 — Validation Report: HALT v1.0.1 Field Run `halt-fieldrun-01`

**Status**: Final · **Run period**: 2026-08-25 – 2026-08-26 (J-1..87) · **Executor**: human-coordinated LLM agent (single coordinator + subagent fan-outs) · **Workload**: multi-session generative knowledge work (a structured document synthesized under evolving acceptance criteria), not batch extraction.

This report closes roadmap item 11§8-1 ("field validation precedes runtime"). It converts every real incident from the run into (a) a verdict on the existing clause set and (b) an amendment target for v1.0.2. The follow-on runtime (v1.1) will convert each incident into a replayable fixture.

---

## 1. Verdict summary

The run's headline claims all held:

- **Persistence over context loss**: the coordinator session died/crashed **at least 9 times** across two calendar days (user-reported interruptions: 6 during the test phase alone). Every resumption was performed purely from the workspace ledger (`journal.jsonl` + `checkpoint.json` + `task-graph.json`) with zero memory of the dead session. AX-1 is confirmed as the load-bearing axiom.
- **Recovery procedures**: R4 disk-adjudication resolved both graph-ahead-of-disk incidents without data loss.
- **Amendment & steering machinery**: one sponsor V3 rejection triggered a full amendment cycle (AC-2) including a multi-agent debate phase; steering inputs were logged as ST-xxx and survived session deaths.
- **Human gates**: sponsor fork decisions (ladder replacement, boundary-fork rulings) were routed through the gate as designed (VR-3).

What failed was **not** the architecture but three under-specified clauses. All three failures produced silent or delayed corruption that was caught by manual audit, not by the protocol itself. That distinction drives every amendment below.

**Scorecard: 10 incident classes — 6 handled by spec, 2 hard gaps, 2 partial.**

---

## 2. Incident register

| # | Incident (empirical) | Clause engaged | Verdict | Root cause | Amendment |
|---|---|---|---|---|---|
| I-1 | Registry torn write: crashed script truncated `registry.json` to 0 bytes mid-write | 04 (WAL discipline; registry = rebuildable projection) | ✅ HANDLED — rebuilt `{}` from journal truth | None | — |
| I-2 | Graph ahead of disk: N2/N3 marked DONE in task-graph, artifacts absent (crash during registration) | 05 §R4 (disk adjudication) | ✅ HANDLED | None | — |
| I-3 | **Seq-collision storm**: 26 duplicated seq values (5–35), zero content loss | 04 (seq semantics) | ❌ GAP — collisions detected only by post-hoc audit | Seq counter cached in-process; after instance death, recovery streams restarted it at stale values (three writer streams shared one namespace: original run → recovery wave → R4 backfill wave) | **A-1** |
| I-4 | **Same-path version inversion**: A-N2v2/v3 registered on identical path; later integrity walk reported 4 false FAILs (stale checksums vs overwritten paths); v2/v3 precedence required registry key-order forensics | 04 (registry integrity model) | ❌ GAP — version supersession undefined | Registry treated `(path, checksum)` as re-writable pair; no rule forcing new artifact-id or versioned path on content change | **A-2** |
| I-5 | Session death ×5+ with clean resumptions | AX-1, 05 R0–R7, checkpoint | ✅ HANDLED — strongest confirmation of the core claim | None | — |
| I-6 | Sponsor V3 rejection → amendment cycle → ladder redesign → re-delivery → acceptance | 02 GE, 09 gates, VR-3 | ✅ HANDLED (incl. debate-phase sub-workspaces) | None | — |
| I-7 | **Subagent silent death**: fan-out writers returned `status=completed` with zero files written (3 rounds); cause traced to final-answer generation failure, reading budget crowding out writing budget | 07 parallel dispatch; C-VERIFY | ⚠️ PARTIAL — caught only because coordinator inspected disk manually | Spec's death typology assumes process-visible deaths (kill/timeout); LLM workers exhibit **silent completion-without-artifact**, which "completed" status masks | **A-3** |
| I-8 | Auditor mis-journaling: J-73 recorded "14/14 PASS" when the recalibration had returned FAIL; corrected next event via AMENDMENT (J-74) | 11 conformance; amendment semantics | ✅ BASICALLY HANDLED — correction path worked | Audit conclusions not required to be independently recomputable at record time | **A-4** (lightweight) |
| I-9 | Read-back caught markdown rendering defects (setext-H2 risk) post-delivery | C-VERIFY read-back discipline | ✅ HANDLED | None | — |
| I-10 | Two rounds of external review integrated without breaking internal consistency (5 docs round 1, 5 docs round 2) | 09 steering inbox | ✅ HANDLED | None | — |

---

## 3. Amendments adopted → HALT v1.0.2

All four are additive clarifications; no architecture change. Full text in `provenance.md` §v1.0.2; summaries:

- **A-1 (04§journal)**: *Seq derivation rule.* Append-time seq MUST be computed as `1 + max(seq over existing journal lines)` by reading the journal tail. Cached counters across process restarts are non-conformant. (From I-3.)
- **A-2 (04§registry)**: *(path, checksum) immutability.* Registering new content on an already-registered path requires either a new artifact id or a versioned path. Integrity walks then never produce stale-checksum false FAILs; precedence between versions is carried by ids, not insertion order. (From I-4.)
- **A-3 (07§worker completion + C-VERIFY)**: *Artifact-presence verification.* A worker's terminal status is evidence of nothing; DONE may be recorded only after the coordinator verifies artifact presence on disk (existence + checksum for declared artifacts). Silent-no-output is added to the death typology as a first-class mode for LLM-type executors, alongside kill/timeout. Dispatch contracts SHOULD include incremental write requirements (skeleton-first) so that even silent deaths leave recoverable residue. (From I-7.)
- **A-4 (11§audit records)**: *Recomputability duty.* An audit record must contain enough detail (inputs, method, per-item results) for an independent reader to recompute the verdict; a bare scoreline is non-conformant. (From I-8.)

Explicitly **not** adopted this round: seq-space partitioning per writer stream (A-1's tail-derivation suffices at current scale; revisit if parallel journal appenders become real), mandatory content-hash trees for artifacts (no incident demanded it).

---

## 4. What this run does and does not validate

Validated:
1. Human-executability of the full protocol loop (INIT→decompose→execute→audit→amend→gate→deliver→archive).
2. Crash-resilience of the persistence layout under repeated real session deaths.
3. Gate and amendment machinery under genuine sponsor disagreement.
4. Ledger-only resumption by a fresh coordinator instance.

Not yet validated (drives v1.1):
1. **Machine replayability** — incidents were adjudicated by a human-coordinated agent; fixtures must make them assertable without judgment calls.
2. **Parallel dispatch under true process kills** — I-7 covered LLM silent death only.
3. **Multi-writer journals** — single-writer lease held trivially; concurrent appenders remain untested.
4. Cross-task memory store (10) — untouched by this workload.

---

## 5. Fixture map for the v1.1 reference runtime

Each incident class becomes a named test; the runtime fails CI if any regresses:

| Fixture | Injects | Asserts |
|---|---|---|
| `test_torn_write_registry` | Truncated registry file mid-write | Rebuild from journal yields consistent registry; task continues |
| `test_seq_collision_recovery` | Journal tail with max seq N; fresh "process" appends | Next seq == N+1 (never restarts from cached counter) |
| `test_graph_ahead_r4` | Graph marks node DONE, artifact missing | R4 adjudicates disk-side; backfill events appended; graph reconciled |
| `test_same_path_supersession` | Register v2 content on registered path | Rejected or auto-versioned; integrity walk reports 0 false FAILs |
| `test_silent_worker_death` | Worker returns completed, writes nothing | Coordinator verification blocks DONE; retry/re-dispatch per contract |
| `test_session_death_resume` | Kill coordinator between any two operations | Fresh instance resumes solely from ledger; frontier recomputes |
| `test_gate_rejection_cycle` | Sponsor rejects at V3 | Amendment cycle opens; re-delivery routes through same gate |
| `test_audit_amendment` | Audit record contradicts recomputation | AMENDMENT appended; original preserved |

---

## 6. Provenance note

Every claim above traces to ledger events J-1..87 in `TEST/tmp/halt-ws/journal.jsonl` and to session transcript the coordinator session transcript (JSONL export, filename on file locally). Sampled quotes (sponsor rulings ST-015..027, audit IDs AUD-N5-r1/N9-r2/N10-v3/N11-v4/N12-v5/N14-final) are cited in-line. This report supersedes the "validation pending" caveat in 11§D.
