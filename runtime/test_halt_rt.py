"""
HALT v1.1 reference runtime — fixture tests.

Each test injects one incident class from the field run (see
../12-validation-report.md §5) and asserts the runtime handles it.
Run:  python -m pytest test_halt_rt.py -v     (or just: python test_halt_rt.py)
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from halt_rt import HaltRuntime, HaltError  # noqa: E402

PASS = []
FAIL = []


def check(name, fn):
    try:
        fn()
        PASS.append(name)
        print(f"PASS  {name}")
    except Exception as e:  # noqa: BLE001
        FAIL.append((name, repr(e)))
        print(f"FAIL  {name}: {e!r}")


def fresh_ws():
    """Create a fresh temp workspace dir and chdir into it so that
    relative artifact paths resolve inside the sandbox."""
    d = tempfile.mkdtemp(prefix="halt-rt-")
    os.chdir(d)
    return d


# ---------------------------------------------------------------- fixtures

def test_seq_derivation_no_collision():
    """I-3 / A-1 Rule J-4: a brand-new runtime instance (fresh process
    equivalent) derives seq from the journal tail, never from a cache."""
    ws = fresh_ws()
    try:
        rt1 = HaltRuntime(ws, "t-seq")
        rt1.note("first")
        rt1.close()                      # instance "dies"

        rt2 = HaltRuntime.resume(ws)     # new instance resumes
        ev = rt2.note("second")          # must get seq = last+1
        s1 = rt1.seq_last if False else None
        seqs = [e["seq"] for e in rt2._events]
        assert len(seqs) == len(set(seqs)), f"collision: {seqs}"
        assert int(ev["seq"]) == int(seqs[-2]) + 1
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def test_torn_write_registry_rebuild():
    """I-1: registry torn to 0 bytes -> rebuilt from journal truth."""
    ws = fresh_ws()
    try:
        rt = HaltRuntime(ws, "t-torn")
        art = os.path.join(ws, "artifacts", "a.txt")
        with open(art, "w", encoding="utf-8") as f:
            f.write("payload")
        rt.register_artifact("A-X", "artifacts/a.txt", "data")
        rt.close()

        # simulate torn write: truncate registry to 0 bytes
        reg_path = os.path.join(ws, "artifacts", "registry.json")
        with open(reg_path, "wb"):
            pass
        assert os.path.getsize(reg_path) == 0

        rt2 = HaltRuntime.resume(ws)
        assert "A-X" in rt2.registry, "registry not rebuilt from journal"
        assert rt2.verify_artifact("A-X"), "rebuilt entry fails integrity"
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def test_same_path_supersession_blocked():
    """I-4 / A-2 Rule AR-3: registering different content on a taken path
    raises instead of silently invalidating the old checksum."""
    ws = fresh_ws()
    try:
        rt = HaltRuntime(ws, "t-supersede")
        p1 = os.path.join(ws, "artifacts", "out.md")
        with open(p1, "w", encoding="utf-8") as f:
            f.write("version one")
        rt.register_artifact("A-V1", "artifacts/out.md", "doc")

        # overwrite the file on disk, then attempt re-registration on same path+id
        with open(p1, "w", encoding="utf-8") as f:
            f.write("version two -- different content")
        try:
            rt.register_artifact("A-V1b", "artifacts/out.md", "doc")
            raise AssertionError("AR-3 should have raised")
        except HaltError as e:
            assert "AR-3" in str(e)

        # conformant route: versioned path + new id
        p2 = os.path.join(ws, "artifacts", "out.v2.md")
        shutil.copyfile(p1, p2)
        rt.register_artifact("A-V2", "artifacts/out.v2.md", "doc")
        walk = rt.integrity_walk()
        # A-V1 now legitimately FAILs: its checksum froze "version one",
        # but the file was mutated out-of-band during the attempted violation.
        assert walk["A-V1"].startswith("FAIL"), walk
        assert walk["A-V2"] == "PASS", walk
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def test_silent_worker_death_detected():
    """I-7 / A-3 Rule PD-J1: worker 'completed' but wrote nothing ->
    DONE is impossible until disk evidence exists."""
    ws = fresh_ws()
    try:
        rt = HaltRuntime(ws, "t-silent")
        rt.add_node("N1", "produce artifact")
        rt.transition("N1", "READY")
        rt.transition("N1", "RUNNING")
        # worker claims completion; nothing written to disk.
        missing = os.path.join(ws, "artifacts", "n1-out.md")
        assert not os.path.exists(missing), "test precondition broken"
        # coordinator-side verification (PD-J1): no disk -> cannot verify
        try:
            rt.register_artifact("A-N1", "artifacts/n1-out.md", "doc",
                                 node_id="N1")
            raise AssertionError("registering a missing artifact should raise")
        except HaltError as e:
            assert "missing" in str(e).lower()
        # therefore N1 stays RUNNING; retry writes for real this time:
        with open(missing, "w", encoding="utf-8") as f:
            f.write("# real output\n")
        rt.register_artifact("A-N1", "artifacts/n1-out.md", "doc", node_id="N1")
        rt.transition("N1", "VERIFYING", evidence=["A-N1"])
        rt.transition("N1", "DONE", evidence=["A-N1 verified"])
        st = rt.status()
        assert st["nodes"]["N1"] == "DONE"
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def test_session_death_resume():
    """I-5 / AX-1: kill at any point; resume rebuilds everything."""
    ws = fresh_ws()
    try:
        rt = HaltRuntime(ws, "t-resume")
        rt.add_node("N1", "a"); rt.add_node("N2", "b")
        rt.transition("N1", "READY")
        rt.transition("N1", "RUNNING")
        art = os.path.join(ws, "artifacts", "x.txt")
        with open(art, "w", encoding="utf-8") as f:
            f.write("x")
        rt.register_artifact("A-X", "artifacts/x.txt", "data", node_id="N1")
        seq_before = rt.seq_last
        n_events_before = len(rt._events)
        rt.close()   # hard death

        rt2 = HaltRuntime.resume(ws)
        # prior events preserved verbatim, in order
        assert [e["seq"] for e in rt2._events[:n_events_before]] == \
               [str(i+1) for i in range(n_events_before)]
        # resume appends exactly one NOTE; seq continues from the tail (J-4)
        assert len(rt2._events) == n_events_before + 1
        assert int(rt2._events[-1]["seq"]) == n_events_before + 1
        assert rt2._events[-1]["payload"]["incident"] == "resumed from ledger"
        states = {n["node_id"]: n["state"] for n in rt2.graph["nodes"]}
        assert states == {"N1": "RUNNING", "N2": "PENDING"}
        assert rt2.verify_artifact("A-X")
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def test_illegal_transition_refused():
    """FSM legality: PENDING->DONE etc. must be refused loudly."""
    ws = fresh_ws()
    try:
        rt = HaltRuntime(ws, "t-fsm")
        rt.add_node("N1", "x")
        for bad in ("DONE", "VERIFYING", "FAILED"):
            try:
                rt.transition("N1", bad)
                raise AssertionError(f"{bad} should be illegal from PENDING")
            except HaltError:
                pass
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def test_double_writer_lease():
    """04 single-writer: second live writer refuses loudly."""
    ws = fresh_ws()
    try:
        rt = HaltRuntime(ws, "t-lock")
        try:
            HaltRuntime(ws, "t-lock")
            raise AssertionError("second writer should be refused")
        except HaltError as e:
            assert "lease" in str(e).lower()
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def test_gate_rejection_cycle():
    """I-6: sponsor rejection -> steering logged -> amendment cycle events
    appended without breaking ledger integrity."""
    ws = fresh_ws()
    try:
        rt = HaltRuntime(ws, "t-gate")
        rt.steering("ST-001", "reject v1; reasons: deduction too weak")
        rt.decision("DR-9", "open amendment cycle AC-1")
        rt.note("amendment cycle opened")
        # ledger remains strictly increasing and parseable
        seqs = [int(e["seq"]) for e in rt._events]
        assert seqs == sorted(seqs) and len(seqs) == len(set(seqs))
    finally:
        shutil.rmtree(ws, ignore_errors=True)


# ---------------------------------------------------------------- main

if __name__ == "__main__":
    check("seq derivation prevents collisions (J-4)",
          test_seq_derivation_no_collision)
    check("torn registry rebuilt from journal (I-1)",
          test_torn_write_registry_rebuild)
    check("same-path supersession blocked, versioned path OK (AR-3)",
          test_same_path_supersession_blocked)
    check("silent worker death detected before DONE (PD-J1)",
          test_silent_worker_death_detected)
    check("session death resume from ledger alone (AX-1)",
          test_session_death_resume)
    check("illegal FSM transitions refused",
          test_illegal_transition_refused)
    check("double-writer lease enforced",
          test_double_writer_lease)
    check("gate rejection cycle keeps ledger sane",
          test_gate_rejection_cycle)

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)
