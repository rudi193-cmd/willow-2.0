#!/usr/bin/env python3
"""
willow/hooks/registry.py — Hook registration and lookup.

Provides a queryable registry of all hooks with metadata:
  - name, category, handler_path
  - destructive, approval_required flags
  - test_path, active status
  - priority for execution order
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.pg_bridge import PgBridge


def register_hook(
    name: str,
    category: str,
    handler_path: str,
    destructive: bool = False,
    approval_required: bool = False,
    test_path: str = None,
    priority: int = 50,
) -> bool:
    """Register a hook in the registry.

    Args:
        name: Unique hook name
        category: Category (e.g., 'git_events', 'test_events', 'graph_events')
        handler_path: Path to handler script relative to project root
        destructive: If True, requires approval before execution
        approval_required: If True, requires approval before execution
        test_path: Path to test file (optional)
        priority: Execution priority (higher = earlier)

    Returns:
        True if registered or already exists, False on error
    """
    try:
        bridge = PgBridge()
        cur = bridge.conn.cursor()

        cur.execute("""
            INSERT INTO hook_registry
            (name, category, handler_path, destructive, approval_required, test_path, priority, active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (name) DO NOTHING
        """, (
            name, category, handler_path,
            destructive, approval_required, test_path, priority
        ))

        bridge.conn.commit()
        bridge.close()
        return True

    except Exception:
        return False


def get_active_hooks(category: str = None) -> list[dict]:
    """Get all active hooks, optionally filtered by category.

    Args:
        category: Optional category filter

    Returns:
        List of hook dicts with all metadata
    """
    try:
        bridge = PgBridge()
        cur = bridge.conn.cursor()

        if category:
            cur.execute("""
                SELECT name, category, handler_path, destructive, approval_required,
                       test_path, active, priority, created_at
                FROM hook_registry
                WHERE active = TRUE AND category = %s
                ORDER BY priority DESC, name
            """, (category,))
        else:
            cur.execute("""
                SELECT name, category, handler_path, destructive, approval_required,
                       test_path, active, priority, created_at
                FROM hook_registry
                WHERE active = TRUE
                ORDER BY priority DESC, name
            """)

        rows = cur.fetchall()
        bridge.close()

        return [
            {
                'name': row[0],
                'category': row[1],
                'handler_path': row[2],
                'destructive': row[3],
                'approval_required': row[4],
                'test_path': row[5],
                'active': row[6],
                'priority': row[7],
                'created_at': row[8],
            }
            for row in rows
        ]

    except Exception:
        return []


def deactivate_hook(name: str) -> bool:
    """Deactivate a hook by name (soft delete).

    Args:
        name: Hook name to deactivate

    Returns:
        True if deactivated, False on error
    """
    try:
        bridge = PgBridge()
        cur = bridge.conn.cursor()

        cur.execute("UPDATE hook_registry SET active = FALSE WHERE name = %s", (name,))
        bridge.conn.commit()
        bridge.close()
        return True

    except Exception:
        return False


def seed_builtin_hooks() -> int:
    """Register all built-in hooks. Idempotent (ON CONFLICT DO NOTHING).

    Returns:
        Count of newly registered hooks (0 if already seeded)
    """
    builtin_hooks = [
        {
            'name': 'post_commit',
            'category': 'git_events',
            'handler_path': 'willow/hooks/post_commit.py',
            'destructive': False,
            'approval_required': False,
            'test_path': None,
            'priority': 60,
        },
        {
            'name': 'post_merge',
            'category': 'git_events',
            'handler_path': 'willow/hooks/post_merge.py',
            'destructive': False,
            'approval_required': False,
            'test_path': None,
            'priority': 60,
        },
        {
            'name': 'test_completion',
            'category': 'test_events',
            'handler_path': 'willow/hooks/completion_hook.py',
            'destructive': False,
            'approval_required': False,
            'test_path': None,
            'priority': 50,
        },
        {
            'name': 'edge_linking',
            'category': 'graph_events',
            'handler_path': 'willow/hooks/edge_linking.py',
            'destructive': False,
            'approval_required': False,
            'test_path': None,
            'priority': 40,
        },
    ]

    count = 0
    for hook in builtin_hooks:
        if register_hook(**hook):
            count += 1

    return count


def get_hook_by_name(name: str) -> dict:
    """Get a single hook by name.

    Args:
        name: Hook name

    Returns:
        Hook dict or None if not found
    """
    try:
        bridge = PgBridge()
        cur = bridge.conn.cursor()

        cur.execute("""
            SELECT name, category, handler_path, destructive, approval_required,
                   test_path, active, priority, created_at
            FROM hook_registry
            WHERE name = %s
        """, (name,))

        row = cur.fetchone()
        bridge.close()

        if not row:
            return None

        return {
            'name': row[0],
            'category': row[1],
            'handler_path': row[2],
            'destructive': row[3],
            'approval_required': row[4],
            'test_path': row[5],
            'active': row[6],
            'priority': row[7],
            'created_at': row[8],
        }

    except Exception:
        return None
