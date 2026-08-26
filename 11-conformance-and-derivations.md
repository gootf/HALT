# HALT Conformance Self-Audit & Rule Derivations

- **Spec ID:** HALT-11
- **Version:** 1.0.1 (2026-08-25) — semantics hardening after four external reviews
- **Depends on:** all previous

One instrument: the checklist a system runs on itself before claiming conformance.

---

## A. Conformance Checklist

Answer per item: PASS / FAIL / N-A(tier). Any FAIL at MUST level ⇒ not conforming.

### A1. Durability (INV-1)
- [ ] All four artifacts exist inside W (C-ART)
- [ ] No procedure requires conversation-only information
- [ ] Commit rule implemented: write→verify→commit→point per unit (C-UNIT/C-VERIFY)

### A2. Truth discipline (INV-2, truth hierarchy)
- [ ] Checkpoint regenerated-from-journal path exists and was exercised once
- [ ] Conflict resolution walks the ladder; disk adjudicates existence disputes
- [ ] Claims (self, worker, human) never advance state without evidence

### A3. Recoverability (INV-3/5, AX-4)
- [ ] Recovery procedure R0–R7 followed verbatim on a live interruption test
- [ ] Dangling tx resolution defined (complete-or-quarantine)
- [ ] Skip-by-evidence demonstrated: partial batch resumed without redo
- [ ] Torn-tail handling exercised (truncate-after-inspect, fragments kept)

### A4. History integrity (INV-4)
- [ ] Journal append-only enforced by tooling; corrections are superseding events
- [ ] Quarantined paths preserved with successor references (N14)

### A5. Verification separation (INV-6)
- [ ] V-levels declared per node; V2 auditors read-only & fresh-context
- [ ] Executor completion claims route through VERIFYING only (FSN-4)

### A6. Context bounding (INV-7)
- [ ] Contracts self-contained (PD-C1); worker first action = read own contract
- [ ] Detail-on-demand: compression at boundaries + selective re-expansion
- [ ] Over-budget node ⇒ decomposed further, not stretched (decomposition error class)

### A7. Failure containment (INV-8)
- [ ] Child terminal states well-defined; partial outputs preserved
- [ ] Retry matrix classes implemented w/ health probes (RT-1)
- [ ] Three-strike escalation fires (FSN-3)

### A8. Parallel safety (HALT-07)
- [ ] Disjoint write scopes; deterministic numeric-key merge
- [ ] Generated contracts + generator self-checks (PD-C2/C3)
- [ ] Rolling first-death rate drives mode ladder; probes precede resume (PD-H1..3)

### A9. Human integration (HALT-09)
- [ ] Steering inbox durable; ingestion protocol S1–S4 implemented
- [ ] Gates persist questions before waiting; timeout ≠ consent (GA-1/2)
- [ ] Escalation bundles carry data + safe default (AD-1/2)

### A10. Memory hygiene (HALT-10)
- [ ] W/M boundary respected (progress vs knowledge)
- [ ] Supersede-not-edit; freshness gate on read
- [ ] Index bounded; declarative phrasing

### A11. Auditability (INV-9)
- [ ] Full walk possible: any state → evidence chain → authority
- [ ] Decision records present for every consequential fork
- [ ] (v1.0.2) Every audit record is independently recomputable: it carries its inputs, method, and per-item results — a bare scoreline (e.g. "14/14 PASS") without the itemized basis is non-conformant, because an auditor's own mis-journaling then becomes indistinguishable from a true pass. *(Empirical: field run I-8.)*

---

## C. Source-document requirement coverage

| Requirement (from the source problem document, see provenance) | Where satisfied |
|---|---|
| 超长期任务可用 | tiers, sharded journals (04 §8, 05 §6), context bounding (INV-7) |
| 记忆可持久化 | four artifacts (01 §4, 04), memory store (10) |
| 随时任意位置打断可接续 | FSM-N transactional states, commit rule, recovery R0–R7, interruption taxonomy (05 §3) |
| 嵌套其他SOP | uniform interface (03), nesting/composition (06) |
| 统一接口协议 | SOP card + invocation/result docs (03 §2, §4) |
| 恢复机制在最高层 | FSM-T RECOVERING as mandatory door (02 FST-1); coordinator-owned |
| 事务式提交/回滚 | micro-commit + tx_id + quarantine (01 §5, 05 R4-tx) |
| 接续判断标准（三条件） | stable position def (01 §5): valid state record ∧ verifiable effects ∧ explicit next-transition — operationalized by R6 consistency check |
| 执行者≠检查者 | INV-6; roles (08); MEA mapping |
| 状态树/失败分支保留 | graph extension-only; quarantine-with-successors (INV-4); MAGE lineage in provenance |
| 并行派发、子代理死亡应对 | HALT-07 entire + dead-type-derived rules |
| 人工提醒后中断场景 | 05 §5 + 09 §3b normative walkthrough |
| 循环/迭代型工作（研究回路、修订循环） | D4 modeling note: iteration unrolled as successor chains (N12/N14), bounded by budgets |
| 开放目标任务（质量/创新类验收） | VR-3 judging-authority protocol; V3 gated revise loop |
| 执行中目标演化 | HALT-02 §10 goal-evolution rules GE-1..4 (Sponsor authority + blast-radius walk + survivor credit) |

---

## D. Known Limitations (honesty section)

1. **Clock trust.** ts fields assume loosely sane local clocks; malicious clock skew unhandled.
2. **Concurrent coordinators.** Single-writer-per-journal assumed; multi-coordinator HA is out of scope v1 (would need consensus layer).
3. **S3 receipt gaps.** Protocol shrinks but cannot eliminate unverifiable external effects; human adjudication path is the backstop, not a solution.
4. **Semantic verification.** V1/V2 verify structure/provenance; final quality judgments remain human (V3) — by design, not oversight.
5. **Cost of ceremony.** Tier-1 overhead on tiny tasks is real; Tier 0 exists as pressure valve. Mis-tiering wastes either safety or effort.
6. **Composition not yet empirically validated.** Each lineage mechanism carries its own evidence (see provenance.md), but HALT *as a whole* — the specific commit granularity, frontier rule, three-strike threshold, S0–S3 classes, R0–R7 ordering — is engineering synthesis validated only by a prior field run at reduced scope. Conformance (§A) certifies protocol adherence, not task efficacy. Acquiring that evidence (controlled runs comparing Tier-1 vs ad-hoc execution on matched tasks) is future work.

## 8. Roadmap (v1.x candidates, priority order)

Derived from the four external reviews (2026-08-25) after adjudication; each item names its source review:

| Priority | Item | Source |
|---|---|---|
| v1.1 | **Reference runtime + kill-process test suite** (Tier-1, single node, batch nodes: ledger, R0–R7, frontier, skip-by-evidence; crash between unit-write/ledger-line, between VERIFYING/DONE, steering landed vs not) | 参考3 P0, 参考2 §21–22 |
| v1.1 | **HALT-Bench suites**: Interruption / Worker-Failure / Steering / Parallel / Epistemic, with metrics (recovery rate, lost-work, duplicate-work, false-completion, overheads) | 参考2 §22, 参考4 (UltraHorizon as stress model) |
| v1.1 | **Evidence Matrix upgrade of provenance.md**: per AX/INV/Rule → origin, evidence type, directness, confidence, status ∈ {established, supported, synthesized, heuristic, unvalidated} | 参考2 §23, 参考4 §12 |
| v1.1 | **Typed task-graph edges**: DEPENDS_ON / SUPERSEDES / INVALIDATES / SUPPORTS / DERIVED_FROM | 参考2 §17 |
| v1.2 | **Split HALT-Exec / HALT-Judge documents** (execution protocol vs epistemic governance), keeping one brand, honest about what is mechanical | 参考3 P1, 参考2 §18 |
| v1.2 | **Delegation ladder for authority gradient** (AUTO → AUTO_WITH_BUDGET → STANDING_AUTHORITY → REVIEW_REQUIRED → EXPLICIT_APPROVAL) replacing binary human/agent gates where appropriate | 参考2 §20 |
| v1.2 | **ARCHIVED terminal sub-states**: PROCESS_COMPLETE / CONTENT_ACCEPTED / TASK_CLOSED | 参考2 §19 |
| v1.2 | **Graph compaction policy** for long quarantined chains (archive snapshot + id/successor stubs) | 参考3 §H |
| v1.2 | **Runtime-enforced write scopes** (chroot/Landlock/workspace jail) to back INV-10 with mechanism, not just policy | 参考3 §G/P2 |
| v1.2 | Steering inbox as JSONL projection of STEERING_LOGGED events (single source, consumption cursor) | 参考3 §I |
| v1.3 | **Formal semantics annex** (state space, transition function S′=T(S,a,e), invariant proofs: committed state survives crash) | 参考1 缺陷1, 参考2 §21 |
| v1.3 | **Cost/complexity model** (expected-loss vs overhead; when Tier-1 pays) | 参考1 缺陷2 |
| v1.3 | Learning layer: failure-pattern → policy update loop feeding Memory Store | 参考1 缺陷4 |

Directed reading list (verified real on arXiv/Cambridge, 2026-08-25): State-Aware Runtime (Cambridge ORP, working paper), AgentRewind 2608.14380, ScienceFlow 2608.14354, Who Broke the System? 2607.07989, UltraHorizon 2509.21766, Coordination as an Architectural Layer 2605.03310, AgentDojo 2406.13352. These inform the roadmap above; they do NOT retroactively validate v1.

---

*End of HALT-11.*
