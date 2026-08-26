# HALT Recovery

- **Spec ID:** HALT-05
- **Version:** 1.0.0 (2026-08-25)
- **Depends on:** HALT-02 (FSM-T `RECOVERING`), HALT-04 (formats)

Recovery is the standard door back into `EXECUTING` (FST-1): every session start, every worker pickup, every resumption after pause passes through it. It is a fixed, mechanical procedure — an agent performing recovery follows this document; it does not improvise.

---

## 1. Entry Conditions

Enter `RECOVERING` when ANY of:

- E1. A fresh agent/session takes over a task (the normal case: AX-1 says assume nothing carried over).
- E2. A child instance returns control to its parent (parent re-verifies before trusting).
- E3. An interruption is detected: dead executor, missing heartbeats, crashed process.
- E4. Ordered resume from `SUSPENDED`.
- E5. Any doubt about state consistency ("something looks wrong" is a legal trigger).

---

## 2. The Recovery Procedure (normative order)

```
R0  SAFETY     Do not write any state artifact yet. Read-only until R6 passes.
R1 ORIENT      Read checkpoint.json (fast orientation ONLY — it is rank 4).
R2 GROUND      Reconstruct truth:
               a) journal tail scan (last ~100 events + all events of
                  active/ambiguous entities)
               b) disk scan of artifacts/ vs registry.json (existence,
                  checksum-class)
               c) ledger tails of active batch nodes
R3 DETECT      Classify findings:
               - dangling tx_ids?                → R4-tx
               - RUNNING nodes w/o live contract?→ R4-orphan
               - uncommitted tail (torn journal
                 line / unregistered files)?     → R4-tail
               - checkpoint contradicts journal+disk? → R4-cache
               - nothing anomalous               → R5
R4 RESOLVE     Deterministic repairs (each emits a journal event):
   R4-tx       complete-if-deterministic else quarantine parts;
               affected nodes → PENDING (INV-3)
   R4-orphan   executor presumed dead (AX-3): node → RETRYABLE with
               failure_class transient-agent; partial units stay valid
               via skip-by-evidence
   R4-tail     torn/uncommitted content: keep bytes under tmp/recovered/,
               truncate live log at last verified seq, register recovered
               fragments as quarantined artifacts (never silently discard)
   R4-cache    REBUILD checkpoint from journal+graph (it loses; INV-2);
               never "fix" the journal to match the cache
   R4-s3       probable-done-unverifiable external effects (S3 without
               receipt): surface to human via steering channel with full
               context; mark the node BLOCKED(gate) pending adjudication
R5 FRONTIER    Recompute frontier(G) from scratch (FR-1); verify every
               READY node's deps are journal-backed DONE.
R6 CONSISTENCY Self-check: does every state have supporting evidence?
               (walk = mini audit). Fail ⇒ loop R2 once with wider window;
               still failing ⇒ escalate to human with diagnostic bundle.
R7 HANDOFF     Write recovery NOTE (what was found, what was repaired),
               update checkpoint, emit resume-ready summary:
               "task X, frontier {…}, recommended next: …".
```

Exit condition: frontier exists and ≥1 node may be legally contracted. Only now may the FSM-T flip to `EXECUTING`.

**Rule RC-1 (read-only till consistent).** No dispatching, no graph edits, no artifact writes before R6 passes — recovery itself must not create the mess it exists to fix.
**Rule RC-2 (disk adjudicates).** Where journal and disk disagree about *work existence*, disk wins for additive work (files exist ⇒ work probably happened; register it) and journal wins for *intent* (what the work was supposed to be).
**Rule RC-3 (bounded effort).** Recovery MUST cost ≪ the work it recovers. If R2 scans exceed budget on huge tasks, use indexed checkpoints (per-shard journals, §6) instead of full scans.

---

## 3. Interruption Point Taxonomy (what R4 must handle)

| Interrupted between… | Loss exposure | Handling |
|---|---|---|
| two units of a batch | ≤1 unit's budget | ledger shows ok-prefix; resume at next unit |
| unit write and unit ledger line | one unit possibly done-but-unmarked | read-back check: verify artifact → mark ok; else redo unit |
| VERIFYING pass and DONE commit | verification redone (cheap) | rerun verifier; idempotent by design |
| S3 action and RECEIPT capture | worst case: unknown external state | R4-s3 human adjudication |
| parent dispatch and child start | nothing (child never lived) | orphan contract cleanup |
| child mid-flight and parent notify | child partials + silent death | heartbeat timeout → R4-orphan |

The table's message: **every row has a procedure**; there is no interruption point requiring clairvoyance.

---

## 4. Checkpoint Regeneration Algorithm

```
rebuild_checkpoint(journal, task-graph):
    replay STATE_TRANSITION events → node states (last-writer-per-entity wins)
    nodes_done   := count(state == DONE)
    active       := contracts issued minus contracts closed by N03/N06/N04…
    frontier     := compute per FR rules from rebuilt states
    counters     := fold ARTIFACT_REGISTERED / unit ledgers
    next_hint    := derived from frontier priorities
```

Deterministic given inputs; run twice, compare outputs (cheap self-check against replay bugs).

---

## 5. Steering After Interruption (the motivating scenario)

Scenario (user-specified requirement): coordinator dispatched parallel workers; human sent a correction ("also require X", "stop approach Y"); the coordinator session died instantly; context is gone.

HALT handling:

1. At send time, the steering input was logged (`STEERING_LOGGED`, weight 3) into `steering/inbox.md` + journal BEFORE being acted upon (HALT-09 §2). It survived.
2. Recovery (new session) reads the steering channel as part of R2; unresolved steering entries are treated as highest-priority amendments:
   - each gets an AMENDMENT event,
   - affected Specs amended (TG-1 route),
   - frontier recomputed (FR-2),
   - in-flight contracts inconsistent with the new directive get recalled or bounded-amended (HALT-07 §7).
3. If the steering arrived but was NEVER journaled (human sent it through a side channel that died), the human repeats it to the new session; the new session logs it with provenance "re-stated post-interruption". The lesson is codified in HALT-09: **a steering input that isn't durable doesn't exist** — hence the durable inbox is mandatory infrastructure, not a nicety.

This closes the user's required scenario end-to-end.

---

## 6. Scaling: Sharded Journals & Indexed Recovery (Tier 2)

For very large tasks (10⁴+ units):

- Journal shards per phase/node-group: `journal.<shard>.jsonl` with disjoint seq ranges recorded in a small index file;
- Node-level "commit stamps": each node records its last known good seq, so recovery scans only active/ambiguous shards;
- Ledger-first recovery: for pure batch progress, ledger tails suffice to reconstruct position; journal consulted only for transitions (MemChar hot/cold principle applied to recovery cost).

---

## 7. Anti-Patterns (observed failures this procedure forbids)

- AP-1 "Trust the last status report." (Claims ≠ evidence.)
- AP-2 "Redo everything to be safe." (Violates INV-5 skip-by-evidence; burns budget; can overwrite good work with worse work.)
- AP-3 "Patch the checkpoint forward." (Cache repair masquerading as truth repair.)
- AP-4 "Resume where the conversation left off." (Conversation is gone; that's the premise.)
- AP-5 "Silent quarantine." (Dropping suspicious artifacts without registering them destroys the audit trail and invites repeat offenses.)

---

*End of HALT-05. Next: HALT-06 — nesting SOP instances inside nodes.*


---

## Note (v1.0.2)

Recovery integrity walks assume registry Rule AR-3 ((path, checksum) immutability): stale-checksum false FAILs indicate an AR-3 violation upstream, not disk corruption. Worker completion is verified disk-side per Rule PD-J1 before any DONE is trusted during recovery replay.
