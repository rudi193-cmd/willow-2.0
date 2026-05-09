#!/usr/bin/env python3
"""
tests/hooks/test_runner.py — Tests for hook runner (isolation, stall detection, approval).

Tests adapt Cinnamonint patterns: subprocess isolation, stall detection, approval gates.
"""

import unittest
import os
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from willow.hooks.runner import (
    run_hook_isolated,
    run_pipeline,
    _is_stalled,
    _requires_approval,
    _log_execution,
    _hash_content,
)


class TestStallDetection(unittest.TestCase):
    """Test stall detection (input == output means no progress)."""

    def test_stall_detected(self):
        """Identical hashes indicate stall."""
        hash1 = _hash_content("same content")
        hash2 = _hash_content("same content")
        self.assertTrue(_is_stalled(hash1, hash2))

    def test_stall_not_detected(self):
        """Different hashes indicate progress."""
        hash1 = _hash_content("input")
        hash2 = _hash_content("output")
        self.assertFalse(_is_stalled(hash1, hash2))


class TestApprovalGate(unittest.TestCase):
    """Test approval gate flags."""

    def test_destructive_requires_approval(self):
        """Destructive hook requires approval."""
        hook = {'destructive': True, 'approval_required': False}
        self.assertTrue(_requires_approval(hook))

    def test_approval_required_requires_approval(self):
        """Hook marked as approval_required requires approval."""
        hook = {'destructive': False, 'approval_required': True}
        self.assertTrue(_requires_approval(hook))

    def test_safe_hook_no_approval(self):
        """Safe hook doesn't require approval."""
        hook = {'destructive': False, 'approval_required': False}
        self.assertFalse(_requires_approval(hook))


class TestSubprocessIsolation(unittest.TestCase):
    """Test subprocess isolation (hooks run in separate process)."""

    def test_hook_runs_in_subprocess(self):
        """Hook script is executed as subprocess, not imported."""
        # Create a minimal test hook
        test_hook_path = Path(__file__).parent.parent.parent / "willow" / "hooks" / "post_commit.py"
        if test_hook_path.exists():
            result = run_hook_isolated(str(test_hook_path.relative_to(Path(__file__).parent.parent.parent)))
            # Should return dict with subprocess result
            self.assertIn('returncode', result)
            self.assertIn('stdout', result)
            self.assertIn('stderr', result)
            self.assertIn('elapsed_ms', result)

    def test_handler_not_found(self):
        """Nonexistent handler returns error result."""
        result = run_hook_isolated("nonexistent/handler.py")
        self.assertEqual(result['returncode'], 1)
        self.assertIn('not found', result['stderr'].lower())

    @patch('subprocess.run')
    def test_timeout_handling(self, mock_run):
        """Hook timeout is caught and reported."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 30)

        result = run_hook_isolated("dummy/hook.py", timeout=30)
        self.assertEqual(result['returncode'], 124)  # Standard timeout code
        self.assertTrue(result['timed_out'])
        self.assertIn('timeout', result['stderr'].lower())


class TestIterationLogging(unittest.TestCase):
    """Test iteration tracking logs to hook_executions."""

    @patch('willow.hooks.runner.PgBridge')
    def test_log_execution_writes_to_db(self, mock_bridge_class):
        """Log execution inserts record into hook_executions."""
        mock_bridge = MagicMock()
        mock_bridge_class.return_value = mock_bridge
        mock_cursor = MagicMock()
        mock_bridge.conn.cursor.return_value = mock_cursor

        result = _log_execution(
            'test_hook',
            'run_123',
            'ok',
            input_hash='abc123',
            output_hash='def456',
            changed=True,
            elapsed_ms=100,
        )

        # Verify insert was called
        self.assertTrue(result)
        mock_cursor.execute.assert_called()
        mock_bridge.conn.commit.assert_called()

    @patch('willow.hooks.runner.PgBridge')
    def test_log_execution_error_handling(self, mock_bridge_class):
        """Log execution handles DB errors gracefully."""
        mock_bridge_class.side_effect = Exception("DB error")

        # Should not raise, return False
        result = _log_execution('test_hook', 'run_123', 'error')
        self.assertFalse(result)


class TestPipelineExecution(unittest.TestCase):
    """Test hook pipeline execution and summary."""

    @patch('willow.hooks.runner.get_active_hooks')
    @patch('willow.hooks.runner.run_hook_isolated')
    @patch('willow.hooks.runner._log_execution')
    def test_pipeline_summary(self, mock_log, mock_run, mock_get_hooks):
        """Pipeline returns summary of execution."""
        # Setup
        mock_get_hooks.return_value = [
            {
                'name': 'hook1',
                'category': 'test',
                'handler_path': 'path/to/hook1.py',
                'destructive': False,
                'approval_required': False,
            }
        ]
        mock_run.return_value = {
            'stdout': 'output',
            'stderr': '',
            'returncode': 0,
            'elapsed_ms': 50,
            'timed_out': False,
        }
        mock_log.return_value = True

        # Run pipeline
        summary = run_pipeline(category='test')

        # Verify summary structure
        self.assertIn('executed', summary)
        self.assertIn('stalled', summary)
        self.assertIn('errors', summary)
        self.assertIn('skipped', summary)
        self.assertIn('total_ms', summary)
        self.assertEqual(summary['executed'], 1)


if __name__ == '__main__':
    unittest.main()
