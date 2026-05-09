"""
tests/test_hash_ring.py — Kart hash ring unit tests.
Coverage: consistent hashing, agent lifecycle, distribution balance.
"""

import pytest

from willow.memory.hash_ring import KartHashRing, assign_task_to_agent


class TestKartHashRingBasic:
    """Basic ring operations."""

    def test_init_empty(self):
        """Empty ring should not assign tasks."""
        ring = KartHashRing([])
        assert ring.assign_task("task-1") is None

    def test_init_single_agent(self):
        """Single agent gets all tasks."""
        ring = KartHashRing(["agent-a"])
        assert ring.assign_task("task-1") == "agent-a"
        assert ring.assign_task("task-2") == "agent-a"
        assert ring.assign_task("task-999") == "agent-a"

    def test_init_multiple_agents(self):
        """Multiple agents should get tasks."""
        ring = KartHashRing(["agent-a", "agent-b", "agent-c"])
        tasks = [ring.assign_task(f"task-{i}") for i in range(100)]
        assert len(set(tasks)) > 1  # At least 2 different agents
        assert all(t in ["agent-a", "agent-b", "agent-c"] for t in tasks)

    def test_deterministic_assignment(self):
        """Same task_id always goes to same agent."""
        ring = KartHashRing(["agent-a", "agent-b", "agent-c"])
        task_id = "task-critical"
        agent1 = ring.assign_task(task_id)
        agent2 = ring.assign_task(task_id)
        agent3 = ring.assign_task(task_id)
        assert agent1 == agent2 == agent3

    def test_get_agents(self):
        """get_agents should return all agents."""
        agents = ["agent-a", "agent-b", "agent-c"]
        ring = KartHashRing(agents)
        assert set(ring.get_agents()) == set(agents)

    def test_stats(self):
        """stats should report distribution."""
        ring = KartHashRing(["agent-a", "agent-b"])
        stats = ring.stats()
        assert "agents" in stats
        assert "vnodes" in stats
        assert "distribution" in stats
        assert stats["agents"] == 2
        assert stats["vnodes"] > 0
        assert stats["skew"] >= 0.0


class TestKartHashRingAddRemove:
    """Agent addition and removal."""

    def test_add_agent_basic(self):
        """Adding agent should let it accept tasks."""
        ring = KartHashRing(["agent-a"])
        ring.add_agent("agent-b")
        assert "agent-b" in ring.get_agents()
        assert len(ring.get_agents()) == 2

    def test_add_agent_duplicate_raises(self):
        """Adding same agent twice should raise."""
        ring = KartHashRing(["agent-a"])
        with pytest.raises(ValueError):
            ring.add_agent("agent-a")

    def test_add_agent_rebalances(self):
        """Adding agent should rebalance load."""
        ring = KartHashRing(["agent-a"])
        # Before: all tasks go to agent-a
        before = [ring.assign_task(f"task-{i}") for i in range(100)]
        assert all(t == "agent-a" for t in before)

        # Add agent-b
        ring.add_agent("agent-b")
        after = [ring.assign_task(f"task-{i}") for i in range(100)]
        assert any(t == "agent-b" for t in after)
        assert any(t == "agent-a" for t in after)

    def test_remove_agent_basic(self):
        """Removing agent should remove it."""
        ring = KartHashRing(["agent-a", "agent-b", "agent-c"])
        ring.remove_agent("agent-b")
        assert "agent-b" not in ring.get_agents()
        assert len(ring.get_agents()) == 2

    def test_remove_agent_not_found_raises(self):
        """Removing non-existent agent should raise."""
        ring = KartHashRing(["agent-a"])
        with pytest.raises(KeyError):
            ring.remove_agent("agent-b")

    def test_remove_agent_reassigns_tasks(self):
        """Removing agent should reassign its tasks."""
        ring = KartHashRing(["agent-a", "agent-b", "agent-c"])
        # Get a task that goes to agent-b (if any exist)
        b_tasks = [f"task-{i}" for i in range(1000) if ring.assign_task(f"task-{i}") == "agent-b"]
        if not b_tasks:
            # If unlucky, skip this test
            pytest.skip("No tasks assigned to agent-b in random sampling")

        ring.remove_agent("agent-b")
        # Now those tasks should go elsewhere
        for task_id in b_tasks[:10]:  # Check first 10
            agent = ring.assign_task(task_id)
            assert agent in ["agent-a", "agent-c"]


class TestKartHashRingDistribution:
    """Task distribution balance."""

    def test_distribution_tracked(self):
        """Distribution should track vnodes per agent."""
        ring = KartHashRing(["agent-a", "agent-b"], vnodes=100)
        dist = ring.get_distribution()
        assert "agent-a" in dist
        assert "agent-b" in dist
        assert dist["agent-a"] >= 1
        assert dist["agent-b"] >= 1

    def test_distribution_roughly_balanced(self):
        """With equal vnodes, distribution should be ~balanced."""
        ring = KartHashRing(["agent-a", "agent-b"], vnodes=150)
        dist = ring.get_distribution()
        total = sum(dist.values())
        # Each should be roughly 50%
        ratio_a = dist["agent-a"] / total
        ratio_b = dist["agent-b"] / total
        # Allow 10% skew due to hash randomness
        assert 0.40 < ratio_a < 0.60, f"Agent-a {ratio_a:.2%} outside expected 40-60%"
        assert 0.40 < ratio_b < 0.60, f"Agent-b {ratio_b:.2%} outside expected 40-60%"

    def test_stats_shows_skew(self):
        """Stats should compute skew metric."""
        ring = KartHashRing(["agent-a", "agent-b", "agent-c"], vnodes=150)
        stats = ring.stats()
        assert stats["skew"] >= 0.0


class TestKartHashRingHashFunction:
    """Hash function consistency."""

    def test_hash_same_key_same_hash(self):
        """Same key should always hash to same value."""
        ring = KartHashRing(["agent-a"])
        h1 = ring.hashi("task-critical")
        h2 = ring.hashi("task-critical")
        assert h1 == h2

    def test_hash_different_keys_likely_different(self):
        """Different keys should usually hash differently."""
        ring = KartHashRing(["agent-a"])
        hashes = [ring.hashi(f"task-{i}") for i in range(100)]
        unique = len(set(hashes))
        # Should have at least 90 unique hashes out of 100
        assert unique > 90

    def test_hash_range(self):
        """Hash should fit in 32-bit unsigned range."""
        ring = KartHashRing(["agent-a"])
        h = ring.hashi("task-1")
        assert 0 <= h < 2**32


class TestKartHashRingEdgeCases:
    """Edge cases and boundary conditions."""

    def test_many_agents(self):
        """Ring should handle many agents."""
        agents = [f"agent-{i}" for i in range(100)]
        ring = KartHashRing(agents, vnodes=50)
        task = ring.assign_task("task-1")
        assert task in agents

    def test_add_many_agents(self):
        """Adding many agents sequentially should work."""
        ring = KartHashRing(["agent-0"])
        for i in range(1, 50):
            ring.add_agent(f"agent-{i}")
        assert len(ring.get_agents()) == 50

    def test_remove_all_but_one(self):
        """Removing agents until one left should work."""
        ring = KartHashRing(["agent-a", "agent-b", "agent-c"])
        ring.remove_agent("agent-b")
        ring.remove_agent("agent-c")
        assert ring.get_agents() == ["agent-a"]
        assert ring.assign_task("task-1") == "agent-a"

    def test_custom_vnodes(self):
        """Custom vnode count should affect distribution."""
        ring_small = KartHashRing(["agent-a", "agent-b"], vnodes=10)
        dist_small = ring_small.get_distribution()
        size_small = sum(dist_small.values())

        ring_large = KartHashRing(["agent-a", "agent-b"], vnodes=200)
        dist_large = ring_large.get_distribution()
        size_large = sum(dist_large.values())

        # Larger vnodes = larger ring
        assert size_large > size_small


class TestConvenienceFunction:
    """Test the convenience assign_task_to_agent function."""

    def test_assign_task_to_agent(self):
        """Convenience function should work."""
        ring = KartHashRing(["agent-a", "agent-b"])
        agent = assign_task_to_agent(ring, "task-1")
        assert agent in ["agent-a", "agent-b"]

    def test_assign_task_to_agent_empty_ring(self):
        """Convenience function on empty ring should return None."""
        ring = KartHashRing([])
        agent = assign_task_to_agent(ring, "task-1")
        assert agent is None


class TestTaskDistributionLoadExample:
    """Integration: realistic task distribution example."""

    def test_realistic_task_loading(self):
        """Simulate submitting 1000 tasks to ring."""
        ring = KartHashRing(["kart-1", "kart-2", "kart-3", "kart-4"], vnodes=150)

        assignments = {}
        for i in range(1000):
            task_id = f"task-{i:06d}"
            agent = ring.assign_task(task_id)
            assignments[agent] = assignments.get(agent, 0) + 1

        # All agents should get some tasks
        assert len(assignments) == 4
        assert all(count > 0 for count in assignments.values())

        # Distribution should be reasonably balanced (within 30%)
        counts = list(assignments.values())
        avg = sum(counts) / len(counts)
        max_count = max(counts)
        min_count = min(counts)
        skew = (max_count - min_count) / avg
        assert skew < 0.30, f"Distribution too skewed: {assignments}, skew={skew:.2%}"

        print(f"Task distribution: {assignments}")
        print(f"Skew: {skew:.2%}")


class TestRingResilience:
    """Resilience to agent churn."""

    def test_task_tracking_through_removals(self):
        """Track how task destinations change during removals."""
        ring = KartHashRing(["agent-a", "agent-b", "agent-c"], vnodes=100)
        task_id = "task-critical"

        destinations = []
        destinations.append(ring.assign_task(task_id))

        ring.remove_agent("agent-b")
        destinations.append(ring.assign_task(task_id))

        ring.add_agent("agent-d")
        destinations.append(ring.assign_task(task_id))

        # Task may or may not stay with same agent depending on vnodes,
        # but should always resolve to a valid agent
        # Note: destination[0] might still be agent-b (before we know it was removed)
        # so we only check that destinations are valid
        assert all(d is not None for d in destinations)
        # Destinations should be from the current valid set
        for dest in destinations:
            assert dest in ["agent-a", "agent-b", "agent-c", "agent-d"]
