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
        from_b17: str,
        to_b17: str,
        relation: str,
        context: Optional[str] = None
    ) -> bool:
        """Create an edge between two atoms.

        Args:
            from_b17: Source atom's b17 identifier
            to_b17: Target atom's b17 identifier
            relation: Relationship type (contains, relates_to, fixes, depends_on, etc)
            context: Optional explanation of the relationship

        Returns:
            True if edge was created, False if not found
        """
        try:
            # Find source and target atoms by b17
            cur = self.bridge.conn.cursor()
            cur.execute("SELECT id FROM knowledge WHERE b17 = %s", (from_b17,))
            from_id = cur.fetchone()
            if not from_id:
                return False

            cur.execute("SELECT id FROM knowledge WHERE b17 = %s", (to_b17,))
            to_id = cur.fetchone()
            if not to_id:
                return False

            from_id = from_id[0]
            to_id = to_id[0]

            # Create edge
            cur.execute("""
                INSERT INTO edges (from_id, to_id, relation, context)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (from_id, to_id, relation, context))

            self.bridge.conn.commit()
            return True

        except Exception:
            return False

    def link_merge_to_commits(self, merge_b17: str, commit_b17_list: list[str]) -> int:
        """Link a merge atom to all its commit atoms."""
        count = 0
        for commit_b17 in commit_b17_list:
            if self.link_atoms(
                merge_b17,
                commit_b17,
                "contains",
                "Commit in this merge"
            ):
                count += 1
        return count

    def link_fix_to_commit(self, fix_b17: str, commit_b17: str) -> bool:
        """Link a test_fix atom to the commit that fixed it."""
        return self.link_atoms(
            fix_b17,
            commit_b17,
            "fixed_by",
            "This fix was introduced in this commit"
        )

    def link_feature_to_architecture(self, feature_b17: str, arch_b17: str) -> bool:
        """Link a feature atom to related architecture atoms."""
        return self.link_atoms(
            feature_b17,
            arch_b17,
            "implements",
            "Feature implements this design"
        )

    def cross_reference_by_keyword(self, from_b17: str, keyword: str, max_links: int = 3) -> int:
        """Find atoms mentioning a keyword and link to them.

        Useful for connecting new work to related existing work.
        """
        try:
            cur = self.bridge.conn.cursor()

            # Find source atom
            cur.execute(
                "SELECT id, title FROM knowledge WHERE b17 = %s",
                (from_b17,)
            )
            from_row = cur.fetchone()
            if not from_row:
                return 0

            from_id, from_title = from_row

            # Find related atoms (exclude self)
            cur.execute("""
                SELECT id, b17, title FROM knowledge
                WHERE (title ILIKE %s OR summary ILIKE %s)
                AND id != %s
                AND invalid_at IS NULL
                LIMIT %s
            """, (f'%{keyword}%', f'%{keyword}%', from_id, max_links))

            count = 0
            for to_id, to_b17, to_title in cur.fetchall():
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
        cur = linker.bridge.conn.cursor()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        cur.execute("""
            SELECT b17, content FROM knowledge
            WHERE source_type = 'merge'
            AND created_at > %s
        """, (cutoff,))

        for b17, content_str in cur.fetchall():
            if not content_str:
                continue

            try:
                import json
                content = json.loads(content_str) if isinstance(content_str, str) else content_str
                commits = content.get("commits_in_branch", [])
                if commits:
                    count = linker.link_merge_to_commits(
                        b17,
                        [c[:7] for c in commits]  # Use short hashes
                    )
                    summary["merge_to_commits"] += count
            except Exception:
                pass

        # Cross-reference new atoms with existing ones by keyword
        cur.execute("""
            SELECT b17, title FROM knowledge
            WHERE source_type IN ('commit', 'test_event')
            AND created_at > %s
        """, (cutoff,))

        for b17, title in cur.fetchall():
            # Extract keywords from title
            keywords = [
                w for w in title.lower().split()
                if len(w) > 4 and not w.startswith("#")
            ]
            for kw in keywords[:2]:  # Limit keywords per atom
                count = linker.cross_reference_by_keyword(b17, kw, max_links=2)
                summary["cross_references"] += count

        linker.close()
        return summary

    except Exception as e:
        if os.environ.get("WILLOW_ATOM_VERBOSE"):
            print(f"[edge-linking] Error: {e}")
        return {}
