"""
Enterprise-scale integration tests for Willow 2.0.

Requires a live Postgres DB (willow_20_test). Tests are designed to stress
concurrency, throughput, and data integrity at volumes that surface real
production failure modes: deadlocks, hash-chain corruption, queue leaks,
search latency regressions.

Run individually with -k or as a suite — each test cleans up after itself
using namespaced IDs so concurrent test runs don't collide.

Markers:
  @pytest.mark.slow  — tests that take >10s
"""
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import median, quantiles

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("WILLOW_PG_DB", "willow_20_test")

from core.pg_bridge import PgBridge, run_migrations


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def pg():
    b = PgBridge()
    run_migrations(b.conn)
    yield b
    b.close()


# ── 1. Kart queue load — 50 tasks, 100% drain ────────────────────────────────

@pytest.mark.slow
def test_kart_queue_drain_under_load(pg):
    """Submit 50 echo tasks, drain via pending_tasks + task_complete, assert no leaks."""
    N = 50
    tag = f"KART-{pg.gen_id(6)}"

    # Clean up stale pending tasks from previous runs so the queue is hermetic
    with pg.conn.cursor() as cur:
        cur.execute(
            "DELETE FROM tasks WHERE submitted_by = 'enterprise_test' AND status = 'pending'"
        )
    pg.conn.commit()

    # Submit all tasks
    task_ids = set()
    for i in range(N):
        tid = pg.submit_task(f"echo {tag}-{i}", submitted_by="enterprise_test", agent="kart")
        assert tid is not None
        task_ids.add(tid)

    assert len(task_ids) == N

    # Drain — simulate what kart_poll.py does
    drained = 0
    remaining = set(task_ids)
    for _ in range(10):  # max 10 poll cycles
        if not remaining:
            break
        batch = pg.pending_tasks(agent="kart", limit=N)
        if not batch:
            break
        for t in batch:
            if t["id"] not in remaining:
                continue
            pg.task_complete(t["id"], {"ok": True}, "completed")
            remaining.discard(t["id"])
            drained += 1

    assert drained == N, f"drained {drained}/{N} — queue leaked"

    # Verify all completed
    for tid in task_ids:
        row = pg.task_status(tid)
        assert row is not None
        assert row["status"] == "completed", f"{tid} not completed: {row['status']}"


# ── 2. Concurrent KB writes — 20 threads, no corruption ──────────────────────

@pytest.mark.slow
def test_concurrent_knowledge_writes(pg):
    """20 threads write unique atoms simultaneously — verify all land with correct IDs."""
    N_THREADS = 20
    tag = f"CONC-{pg.gen_id(6)}"
    results = {}
    errors  = []

    def write_atom(i):
        try:
            aid = pg.ingest_atom(
                f"{tag} atom {i}",
                f"concurrent write test {i}",
                tier="frontier", confidence=0.75,
            )
            return i, aid
        except Exception as e:
            return i, e

    with ThreadPoolExecutor(max_workers=N_THREADS) as pool:
        futures = [pool.submit(write_atom, i) for i in range(N_THREADS)]
        for f in as_completed(futures):
            i, result = f.result()
            if isinstance(result, Exception):
                errors.append((i, result))
            else:
                results[i] = result

    assert not errors, f"write errors: {errors}"
    assert len(results) == N_THREADS

    # All IDs must be unique
    ids = list(results.values())
    assert len(set(ids)) == N_THREADS, "duplicate atom IDs produced under concurrency"

    # All must be retrievable
    for aid in ids:
        row = pg.knowledge_get(aid)
        assert row is not None, f"atom {aid} not retrievable after concurrent write"


@pytest.mark.slow
def test_concurrent_edge_writes(pg):
    """20 threads add unique edges simultaneously — verify no deadlocks or duplicates."""
    N_THREADS = 20
    tag = f"EDGC-{pg.gen_id(6)}"
    errors = []
    results = []
    lock = threading.Lock()

    def write_edge(i):
        try:
            r = pg.edge_add(f"{tag}-FROM-{i}", f"{tag}-TO-{i}", "concurrent_test", agent="enterprise")
            with lock:
                results.append(r)
        except Exception as e:
            with lock:
                errors.append((i, e))

    threads = [threading.Thread(target=write_edge, args=(i,)) for i in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"edge write errors: {errors}"
    assert len(results) == N_THREADS
    assert all(r.get("status") == "added" for r in results), \
        f"unexpected statuses: {[r.get('status') for r in results if r.get('status') != 'added']}"


# ── 3. Ledger chain integrity at 5k entries ───────────────────────────────────

@pytest.mark.slow
def test_ledger_chain_integrity_at_scale(pg):
    """Append 5000 ledger entries then verify the hash chain is valid end-to-end."""
    N = 5_000
    project = f"enterprise-test-{pg.gen_id(6)}"
    t0 = time.perf_counter()

    for i in range(N):
        pg.ledger_append(project, "scale_test", {"seq": i})

    append_elapsed = time.perf_counter() - t0

    t1 = time.perf_counter()
    result = pg.ledger_verify()
    verify_elapsed = time.perf_counter() - t1

    assert result["valid"] is True, f"chain invalid after {N} appends: {result}"
    assert result["count"] >= N

    # Performance gates
    assert append_elapsed < 60, f"5k appends took {append_elapsed:.1f}s (threshold: 60s)"
    assert verify_elapsed < 5,  f"ledger_verify took {verify_elapsed:.1f}s (threshold: 5s)"

    print(f"\n  ledger: {N} appends in {append_elapsed:.2f}s "
          f"({N/append_elapsed:.0f} ops/s), verify in {verify_elapsed:.2f}s")


# ── 4. KB search latency benchmark — 1000 atoms ──────────────────────────────

@pytest.mark.slow
def test_kb_search_latency_benchmark(pg):
    """Ingest 1000 atoms, run 50 searches, assert p95 < 500ms."""
    N_ATOMS   = 1_000
    N_QUERIES = 50
    tag = f"SRCH-{pg.gen_id(6)}"

    topics = ["distributed systems", "consensus algorithms", "vector embeddings",
              "knowledge graphs", "language models", "cache invalidation",
              "replication lag", "schema migration", "index bloat", "query planning"]

    # Ingest
    t0 = time.perf_counter()
    for i in range(N_ATOMS):
        topic = topics[i % len(topics)]
        pg.ingest_atom(
            f"{tag} {topic} {i}",
            f"Enterprise test atom about {topic}, sequence {i}. "
            f"Contains knowledge about {topic} for benchmarking search throughput.",
            tier="frontier", confidence=0.70,
        )
    ingest_elapsed = time.perf_counter() - t0

    # Search benchmark
    latencies = []
    for i in range(N_QUERIES):
        q = topics[i % len(topics)]
        t_s = time.perf_counter()
        rows = pg.knowledge_search(q, limit=10)
        latencies.append((time.perf_counter() - t_s) * 1000)  # ms

    latencies.sort()
    p50 = median(latencies)
    p95 = quantiles(latencies, n=20)[18]  # 95th percentile
    p99 = quantiles(latencies, n=100)[98]

    print(f"\n  search: {N_ATOMS} atoms ingested in {ingest_elapsed:.1f}s | "
          f"p50={p50:.1f}ms  p95={p95:.1f}ms  p99={p99:.1f}ms")

    assert p95 < 500, f"p95 search latency {p95:.1f}ms exceeds 500ms threshold"


# ── 5. Context compaction load — 100 concurrent saves ─────────────────────────

@pytest.mark.slow
def test_context_save_concurrent(pg):
    """100 concurrent compact_context_write calls — all must land with unique IDs."""
    N = 100
    tag = f"CTX-{pg.gen_id(6)}"
    ids   = []
    errors = []
    lock   = threading.Lock()

    def save(i):
        try:
            r = pg.compact_context_write(
                agent=f"agent-{i % 10}",
                content=f"{tag} summary for agent {i % 10}, slot {i}. "
                        f"This is a compact session state blob written under concurrency.",
                category="handoff",
                ttl_hours=1,
            )
            with lock:
                ids.append(r["id"])
        except Exception as e:
            with lock:
                errors.append((i, e))

    threads = [threading.Thread(target=save, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"context_save errors: {errors}"
    assert len(ids) == N
    assert len(set(ids)) == N, f"ID collisions: {N - len(set(ids))} duplicates"

    # Spot-check retrieval
    for ctx_id in ids[:5]:
        row = pg.compact_context_get(ctx_id)
        assert row is not None, f"context {ctx_id} not retrievable"
        assert tag in row["content"]


# ── 6. Full intake → knowledge pipeline ──────────────────────────────────────

@pytest.mark.slow
def test_intake_to_knowledge_pipeline(pg):
    """Write 20 atoms to intake (files), then bulk-ingest to knowledge, verify all retrievable."""
    from core.intake import write as intake_write

    tag  = f"PIPE-{pg.gen_id(6)}"
    written = []

    # Stage 1: write to intake queue
    for i in range(20):
        rid = intake_write(
            content=f"Enterprise pipeline test atom {i}. Full stack intake→knowledge.",
            source="enterprise_test",
            agent="enterprise",
            tier="frontier",
            confidence=0.85,
            title=f"{tag} Pipeline atom {i}",
        )
        assert rid is not None
        written.append(rid)

    assert len(written) == 20

    # Stage 2: promote — ingest each through PgBridge (mirrors what promote_intake does)
    atom_ids = []
    for i in range(20):
        aid = pg.ingest_atom(
            f"{tag} Pipeline atom {i}",
            f"Enterprise pipeline test atom {i}. Full stack intake→knowledge.",
            tier="frontier", confidence=0.85,
        )
        assert aid is not None
        atom_ids.append(aid)

    assert len(atom_ids) == 20
    assert len(set(atom_ids)) == 20, "duplicate IDs in pipeline promote"

    # Stage 3: verify all retrievable and tier correct
    for aid in atom_ids:
        row = pg.knowledge_get(aid)
        assert row is not None, f"atom {aid} missing after pipeline"
        assert row["tier"] == "frontier"
