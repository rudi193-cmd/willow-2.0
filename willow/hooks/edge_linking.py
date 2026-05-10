#!/usr/bin/env python3
"""
willow/hooks/edge_linking.py — Phase 4: Connect atoms into knowledge graph.

Atoms by themselves are useful, but edges make them powerful.
This module creates relationships between atoms:
  - merge atom → contains → commit atoms
  - test_fix atom → fixes → commit atom
  - feature atom → relates_to → architecture atoms
  - recent atoms → cross_references → related older atoms
"""

import sys
from pathlib import Path
from typing import Optional, Callable

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.pg_bridge import PgBridge


class EdgeLinker:
    """Creates edges between atoms to build knowledge graph."""

    def __init__(self):
        self.bridge = PgBridge()

    def link_atoms(
        self,
        from_id: int,
        to_id: int,
        relation: str,
        context: Optional[str] = None
    ) -> bool:
        """Create an edge between two atoms.

        Args:
            from_id: Source atom's ID
            to_id: Target atom's ID
            relation: Relationship type (contains, relates_to, fixes, depends_on, etc)
            context: Optional explanation of the relationship

        Returns:
            True if edge was created, False on error
        """
        try:
            # Create edge
            cur = self.bridge.conn.cursor()
            cur.execute("""
                INSERT INTO edges (from_id, to_id, relation, context)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (from_id, to_id, relation, context))

            self.bridge.conn.commit()
            return True

        except Exception:
            return False

    def link_merge_to_commits(self, merge_id: int, commit_ids: list[int]) -> int:
        """Link a merge atom to all its commit atoms."""
        count = 0
        for commit_id in commit_ids:
            if self.link_atoms(
                merge_id,
                commit_id,
                "contains",
                "Commit in this merge"
            ):
                count += 1
        return count

    def link_fix_to_commit(self, fix_id: int, commit_id: int) -> bool:
        """Link a test_fix atom to the commit that fixed it."""
        return self.link_atoms(
            fix_id,
            commit_id,
            "fixed_by",
            "This fix was introduced in this commit"
        )

    def link_feature_to_architecture(self, feature_id: int, arch_id: int) -> bool:
        """Link a feature atom to related architecture atoms."""
        return self.link_atoms(
            feature_id,
            arch_id,
            "implements",
            "Feature implements this design"
        )

    def cross_reference_by_keyword(self, from_id: int, keyword: str, max_links: int = 3) -> int:
        """Find atoms mentioning a keyword and link to them.

        Useful for connecting new work to related existing work.
        """
        try:
            cur = self.bridge.conn.cursor()

            # Find related atoms (exclude self)
            cur.execute("""
                SELECT id, title FROM knowledge
                WHERE (title ILIKE %s OR summary ILIKE %s)
                AND id != %s
                AND invalid_at IS NULL
                LIMIT %s
            """, (f'%{keyword}%', f'%{keyword}%', from_id, max_links))

            count = 0
            for to_id, to_title in cur.fetchall():
                try:
                    cur.execute("""
                        INSERT INTO edges (from_id, to_id, relation, context)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (
                        from_id,
                        to_id,
                        "relates_to",
                        f"Both mention '{keyword}'"
                    ))
                    self.bridge.conn.commit()
                    count += 1
                except Exception:
                    pass

            return count

        except Exception:
            return 0

    def close(self):
        """Close database connection."""
        try:
            self.bridge.conn.close()
        except Exception:
            pass


def link_atoms_for_session() -> dict:
    """Main entry point: create edges for all recently created atoms.

    Scans recent atoms and creates relevant edges.
    Returns summary of links created.
    """
    import os
    from datetime import datetime, timedelta, timezone

    if not os.environ.get("WILLOW_ATOM_EXTRACTION"):
        return {}

    try:
        linker = EdgeLinker()
        summary = {
            "merge_to_commits": 0,
            "cross_references": 0,
            "total_edges": 0,
        }

        # Find recent merge atoms and link to their commits
        import json
        cur = linker.bridge.conn.cursor()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        cur.execute("""
            SELECT id, content FROM knowledge
            WHERE source_type = 'merge'
            AND created_at > %s AND content IS NOT NULL
        """, (cutoff,))

        for merge_id, content_str in cur.fetchall():
            try:
                content = json.loads(content_str) if isinstance(content_str, str) else content_str
                commits = content.get("commits_in_branch", [])
                if not commits:
                    continue

                # Batch lookup: find all commit atoms matching any commit in branch
                cur2 = linker.bridge.conn.cursor()
                placeholders = ",".join(["%s"] * len(commits))
                cur2.execute(f"""
                    SELECT id, content->>'commit' FROM knowledge
                    WHERE source_type = 'commit'
                    AND content->>'commit' = ANY(ARRAY[{",".join(["%s"]*len(commits))}])
                """, commits)

                commit_ids = [row[0] for row in cur2.fetchall()]
                if commit_ids:
                    count = linker.link_merge_to_commits(merge_id, commit_ids)
                    summary["merge_to_commits"] += count
            except Exception:
                pass

        # Cross-reference new atoms with existing ones by keyword
        cur.execute("""
            SELECT id, title FROM knowledge
            WHERE source_type IN ('commit', 'test_event')
            AND created_at > %s
        """, (cutoff,))

        for atom_id, title in cur.fetchall():
            # Extract keywords from title
            keywords = [
                w for w in title.lower().split()
                if len(w) > 4 and not w.startswith("#")
            ]
            for kw in keywords[:2]:  # Limit keywords per atom
                count = linker.cross_reference_by_keyword(atom_id, kw, max_links=2)
                summary["cross_references"] += count

        linker.close()
        return summary

    except Exception as e:
        if os.environ.get("WILLOW_ATOM_VERBOSE"):
            print(f"[edge-linking] Error: {e}")
        return {}
