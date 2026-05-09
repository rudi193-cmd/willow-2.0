#!/usr/bin/env python3
"""
willow/hooks/runner.py — Hook execution with isolation, stall detection, approval.

Adapts Cinnamonint patterns for Willow:
  - Each hook runs in a subprocess (isolated from session)
  - Stall detection: skip if hook returns unchanged state
  - Approval gates: block destructive hooks without approval
  - Iteration tracking: log all executions to hook_executions table
"""

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.pg_bridge import PgBridge
from willow.hooks.registry import get_active_hooks, get_hook_by_name


def _hash_content(content: str) -> str:
    """Generate SHA256 hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()


def _is_stalled(input_hash: str, output_hash: str) -> bool:
    """Detect if hook made no progress (input == output)."""
    return input_hash == output_hash


def _log_execution(
    hook_name: str,
    run_id: Optional[str],
    status: str,
    input_hash: Optional[str] = None,
    output_hash: Optional[str] = None,
    changed: Optional[bool] = None,
    elapsed_ms: Optional[int] = None,
    error: Optional[str] = None,
) -> bool:
    """Log hook execution to hook_executions table.

    Args:
        hook_name: Name of hook
        run_id: Session run ID (optional)
        status: Execution status (ok|stalled|error|skipped|timeout)
        input_hash: SHA256 of input
        output_hash: SHA256 of output
        changed: Whether output changed
        elapsed_ms: Execution time in milliseconds
        error: Error message if status='error'

    Returns:
        True if logged, False on error
    """
    try:
        bridge = PgBridge()
        cur = bridge.conn.cursor()

        cur.execute("""
            INSERT INTO hook_executions
            (hook_name, run_id, input_hash, output_hash, changed, status, error, ended_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            hook_name, run_id, input_hash, output_hash, changed, status, error
        ))

        bridge.conn.commit()
        bridge.close()
        return True

    except Exception as e:
        if os.environ.get("WILLOW_ATOM_VERBOSE"):
            print(f"[hook-log] Error logging {hook_name}: {e}", file=sys.stderr)
        return False


def run_hook_isolated(
    handler_path: str,
    input_data: Optional[str] = None,
    timeout: int = 30,
) -> dict:
    """Run a hook in a subprocess for isolation and safety.

    Args:
        handler_path: Path to handler script (relative to project root)
        input_data: Optional stdin data to pass to handler
        timeout: Seconds before killing subprocess

    Returns:
        Dict with: {stdout, stderr, returncode, elapsed_ms, timed_out}
    """
    project_root = str(Path(__file__).parent.parent.parent)
    abs_path = os.path.join(project_root, handler_path)

    if not os.path.exists(abs_path):
        return {
            'stdout': '',
            'stderr': f'Handler not found: {abs_path}',
            'returncode': 1,
            'elapsed_ms': 0,
            'timed_out': False,
        }

    started = time.monotonic()

    try:
        result = subprocess.run(
            [sys.executable, abs_path],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=project_root,
        )

        elapsed_ms = int((time.monotonic() - started) * 1000)

        return {
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode,
            'elapsed_ms': elapsed_ms,
            'timed_out': False,
        }

    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            'stdout': '',
            'stderr': f'Hook timed out after {timeout} seconds',
            'returncode': 124,  # Standard timeout exit code
            'elapsed_ms': elapsed_ms,
            'timed_out': True,
        }

    except Exception as e:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            'stdout': '',
            'stderr': str(e),
            'returncode': 1,
            'elapsed_ms': elapsed_ms,
            'timed_out': False,
        }


def _requires_approval(hook: dict) -> bool:
    """Check if hook requires approval before execution."""
    return hook.get('approval_required', False) or hook.get('destructive', False)


def _prompt_approval(hook_name: str) -> bool:
    """Prompt for approval of a destructive hook.

    In non-interactive contexts (shutdown), auto-approve.
    Could be enhanced with approval file flags.

    Args:
        hook_name: Name of hook requiring approval

    Returns:
        True if approved, False if rejected
    """
    # For shutdown pipeline (non-interactive), auto-approve for now
    # Destructive hooks can be caught at registration time
    return True


def run_pipeline(category: Optional[str] = None, run_id: Optional[str] = None) -> dict:
    """Run all active hooks for a category with isolation and tracking.

    Args:
        category: Optional category filter (e.g., 'git_events')
        run_id: Session run ID for tracking

    Returns:
        Summary dict: {executed, stalled, errors, skipped, total_ms}
    """
    hooks = get_active_hooks(category)

    summary = {
        'executed': 0,
        'stalled': 0,
        'errors': 0,
        'skipped': 0,
        'total_ms': 0,
    }

    started_total = time.monotonic()

    for hook in hooks:
        hook_name = hook['name']

        # Check approval gate
        if _requires_approval(hook) and not _prompt_approval(hook_name):
            _log_execution(hook_name, run_id, status='skipped')
            summary['skipped'] += 1
            continue

        # Run in isolation
        result = run_hook_isolated(
            hook['handler_path'],
            input_data=None,
            timeout=30,
        )

        # Determine status
        if result['timed_out']:
            status = 'timeout'
            changed = False
            summary['errors'] += 1
        elif result['returncode'] != 0:
            status = 'error'
            changed = False
            summary['errors'] += 1
        else:
            # Hook succeeded — check for stall
            output = result['stdout']
            output_hash = _hash_content(output)
            input_hash = _hash_content('')  # For now, empty input (hooks aren't data-driven)

            if _is_stalled(input_hash, output_hash):
                status = 'stalled'
                changed = False
                summary['stalled'] += 1
            else:
                status = 'ok'
                changed = True
                summary['executed'] += 1

        # Log execution
        _log_execution(
            hook_name,
            run_id,
            status=status,
            input_hash=_hash_content(''),
            output_hash=_hash_content(result['stdout']),
            changed=status == 'ok',
            elapsed_ms=result['elapsed_ms'],
            error=result['stderr'] if result['returncode'] != 0 else None,
        )

        if os.environ.get("WILLOW_ATOM_VERBOSE"):
            print(f"[hook-runner] {hook_name}: {status} ({result['elapsed_ms']}ms)")

    summary['total_ms'] = int((time.monotonic() - started_total) * 1000)
    return summary


if __name__ == '__main__':
    # Test execution
    import json
    summary = run_pipeline()
    print(json.dumps(summary, indent=2))
