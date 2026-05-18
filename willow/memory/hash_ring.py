"""
willow/memory/hash_ring.py — Consistent hash ring for task distribution.
b17: KART1  ΔΣ=42

Stolen from ultrabug/uhashring (ketama-compatible).
Minimal virtual-node implementation for Kart agent pool:
- Agents join/leave without thundering herd
- Task assignment by hash(task_id) to minimize re-assignment
- Bounded memory: virtual nodes proportional to ring size

Usage:
    ring = KartHashRing(agents=["agent-a", "agent-b", "agent-c"])
    target = ring.assign_task("task-12345")  # Returns "agent-b" (example)

    ring.add_agent("agent-d")      # 25% new work to agent-d
    ring.remove_agent("agent-b")   # Rebalance agent-b's work
"""

from bisect import insort
from hashlib import md5
from typing import Optional


class KartHashRing:
    """Consistent hash ring for task assignment to agents."""

    def __init__(self, agents: list[str] = None, vnodes: int = 150):
        """Initialize ring with agents and virtual nodes.

        Args:
            agents: Initial list of agent names
            vnodes: Virtual nodes per agent (default 150 for good distribution)
        """
        self._agents = {}           # agent_name -> {"vnodes": int, "weight": 1}
        self._ring = {}             # hash -> agent_name
        self._keys = []             # sorted list of hashes
        self._default_vnodes = vnodes

        if agents:
            for agent in agents:
                self.add_agent(agent)

    def hashi(self, key: str) -> int:
        """Ketama-compatible hash from key.

        Uses MD5 first 4 bytes as per ketama.
        """
        dh = md5(str(key).encode("utf-8")).digest()
        return (dh[3] << 24) | (dh[2] << 16) | (dh[1] << 8) | dh[0]

    def _create_ring(self) -> None:
        """Regenerate ring from current agent set."""
        self._ring = {}
        self._keys = []

        # Distribute vnodes across all agents
        total_vnodes = sum(conf["vnodes"] for conf in self._agents.values())
        if total_vnodes == 0:
            return

        for agent_name, conf in self._agents.items():
            vnodes = conf["vnodes"]
            for i in range(vnodes):
                vnode_key = f"{agent_name}-{i}"
                h = self.hashi(vnode_key)
                self._ring[h] = agent_name
                insort(self._keys, h)

    def assign_task(self, task_id: str) -> Optional[str]:
        """Return agent name for this task_id.

        Returns None if no agents in ring.
        """
        if not self._ring:
            return None

        h = self.hashi(task_id)

        # Binary search: find first key >= hash
        # If we go past the end, wrap to 0
        idx = self._bisect_right(h)
        if idx >= len(self._keys):
            idx = 0

        if idx < len(self._keys):
            return self._ring[self._keys[idx]]
        return None

    def _bisect_right(self, h: int) -> int:
        """Find insertion point for h in sorted keys.

        Returns index where h would be inserted to keep list sorted.
        Used for ring lookup: find first key > h.
        """
        lo, hi = 0, len(self._keys)
        while lo < hi:
            mid = (lo + hi) // 2
            if self._keys[mid] <= h:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def add_agent(self, agent: str, vnodes: int = None) -> None:
        """Add agent to ring, minimal re-assignment.

        New agent gets vnodes from existing pool.
        Only tasks that hash to the new vnodes are reassigned.
        """
        if agent in self._agents:
            raise ValueError(f"Agent {agent} already in ring")

        if vnodes is None:
            vnodes = self._default_vnodes

        self._agents[agent] = {"vnodes": vnodes, "weight": 1}
        self._create_ring()

    def remove_agent(self, agent: str) -> None:
        """Remove agent, re-assign its tasks.

        Tasks on removed agent's vnodes are reassigned to remaining agents
        (whichever vnode they hash nearest to after the removed vnodes disappear).
        """
        if agent not in self._agents:
            raise KeyError(f"Agent {agent} not in ring")

        del self._agents[agent]
        self._create_ring()

    def get_agents(self) -> list[str]:
        """Return list of all agent names."""
        return list(self._agents.keys())

    def get_distribution(self) -> dict[str, int]:
        """Return vnode count per agent.

        Useful for detecting imbalance.
        """
        return {name: len([a for a in self._ring.values() if a == name])
                for name in self._agents}

    def stats(self) -> dict:
        """Return ring stats: size, agent count, distribution skew."""
        dist = self.get_distribution()
        if not dist:
            return {"agents": 0, "vnodes": 0, "skew": 0.0}

        counts = list(dist.values())
        avg = sum(counts) / len(counts) if counts else 0
        max_count = max(counts) if counts else 0
        skew = (max_count - avg) / avg if avg > 0 else 0.0

        return {
            "agents": len(self._agents),
            "vnodes": len(self._keys),
            "distribution": dist,
            "avg_vnodes_per_agent": avg,
            "skew": skew,
        }


def assign_task_to_agent(ring: KartHashRing, task_id: str) -> Optional[str]:
    """Convenience: assign task to agent given ring.

    Returns None if ring is empty.
    """
    return ring.assign_task(task_id)
