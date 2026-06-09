"""Tests for SAFE agent permission tiers."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.safe_agents import (  # noqa: E402
    FLEET_AGENTS,
    TRUST_TIERS,
    build_manifest,
    permissions_for_agent,
    sign_manifest,
)


class TestSafeAgents(unittest.TestCase):
    def test_fleet_includes_skirnir(self):
        self.assertIn("skirnir", FLEET_AGENTS)

    def test_worker_tier_has_read_not_fleet_admin(self):
        perms = permissions_for_agent("gerald")
        self.assertIn("willow_kb_read", perms)
        self.assertNotIn("fleet_admin", perms)

    def test_hanuman_full_override(self):
        perms = permissions_for_agent("hanuman")
        self.assertIn("fleet_admin", perms)
        self.assertIn("pipeline", perms)

    def test_heimdallr_gets_fleet_admin(self):
        perms = permissions_for_agent("heimdallr")
        self.assertIn("fleet_admin", perms)

    def test_willow_gets_handoff_rebuild(self):
        perms = permissions_for_agent("willow")
        self.assertIn("handoff_rebuild", perms)

    def test_willow_gets_intake_and_jeles(self):
        perms = permissions_for_agent("willow")
        self.assertIn("intake", perms)
        self.assertIn("jeles_fetch", perms)
        self.assertNotIn("fleet_admin", perms)

    def test_skirnir_gets_handoff_rebuild(self):
        perms = permissions_for_agent("skirnir")
        self.assertIn("handoff_rebuild", perms)

    def test_build_manifest_shape(self):
        m = build_manifest("jeles")
        self.assertEqual(m["app_id"], "jeles")
        self.assertIn("jeles_fetch", m["permissions"])
        self.assertEqual(m["trust"], "WORKER")

    def test_trust_tiers_defined(self):
        self.assertIn("WORKER", TRUST_TIERS)
        self.assertIn("ENGINEER", TRUST_TIERS)
        self.assertIn("OPERATOR", TRUST_TIERS)

    def test_intake_group_covers_promote(self):
        from sap.core.gate import PERMISSION_GROUPS

        intake = PERMISSION_GROUPS["intake"]
        self.assertIn("intake_list", intake)
        self.assertIn("intake_promote", intake)

    def test_sign_manifest_blocked_inside_kart(self):
        import os
        orig = os.environ.get("WILLOW_IN_KART")
        try:
            os.environ["WILLOW_IN_KART"] = "1"
            ok, msg = sign_manifest("willow")
            self.assertFalse(ok)
            self.assertIn("Kart bwrap sandbox", msg)
        finally:
            if orig is None:
                os.environ.pop("WILLOW_IN_KART", None)
            else:
                os.environ["WILLOW_IN_KART"] = orig


if __name__ == "__main__":
    unittest.main()
