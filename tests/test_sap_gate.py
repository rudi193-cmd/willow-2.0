"""
Tests for sap.core.gate — cross-app authorization
b17: SAPS1
"""
from unittest.mock import patch, MagicMock
from sap.core import gate


class TestParseAppIdFromCollection:
    """Test _parse_app_id_from_collection helper."""

    def test_valid_app_id(self):
        """Extract app_id from normal collection path."""
        assert gate._parse_app_id_from_collection("story-timeline/atoms/") == "story-timeline"
        assert gate._parse_app_id_from_collection("story-timeline/user-uuid/path") == "story-timeline"

    def test_app_id_with_underscores_and_numbers(self):
        """App IDs can contain underscores and numbers."""
        assert gate._parse_app_id_from_collection("app_name_123/path") == "app_name_123"

    def test_invalid_collection_no_slash(self):
        """Collection without slash returns None."""
        assert gate._parse_app_id_from_collection("just_an_app") is None

    def test_invalid_collection_empty(self):
        """Empty collection returns None."""
        assert gate._parse_app_id_from_collection("") is None

    def test_invalid_app_id_starts_with_dash(self):
        """App ID starting with dash is invalid."""
        assert gate._parse_app_id_from_collection("-invalid/path") is None

    def test_invalid_app_id_special_chars(self):
        """App ID with invalid characters returns None."""
        assert gate._parse_app_id_from_collection("app@name/path") is None
        assert gate._parse_app_id_from_collection("app.name/path") is None


class TestAuthorizedCrossApp:
    """Test authorized_cross_app function."""

    @patch("sap.core.gate.psycopg2")
    def test_own_namespace_always_allowed(self, mock_psycopg2):
        """Requesting app accessing own namespace is always allowed (no DB query)."""
        result = gate.authorized_cross_app("story-timeline", "story-timeline/atoms/")
        assert result is True

    @patch("sap.core.gate.psycopg2")
    def test_invalid_requesting_app_id(self, mock_psycopg2):
        """Invalid requesting app ID returns False."""
        result = gate.authorized_cross_app("@invalid", "story-timeline/atoms/")
        assert result is False

    @patch("sap.core.gate.psycopg2")
    def test_unable_to_parse_target_app_id(self, mock_psycopg2):
        """If target collection doesn't parse, return False."""
        result = gate.authorized_cross_app("binder", "invalid-path-no-slash")
        assert result is False

    @patch("sap.core.gate.psycopg2")
    def test_psycopg2_not_available(self, mock_psycopg2):
        """If psycopg2 is None, return False."""
        gate.psycopg2 = None
        result = gate.authorized_cross_app("binder", "story-timeline/atoms/")
        assert result is False
        gate.psycopg2 = mock_psycopg2

    @patch("sap.core.gate.psycopg2")
    @patch.dict("os.environ", {"WILLOW_PG_USER": "test_user"})
    def test_connection_approved(self, mock_psycopg2):
        """Approved connection returns True."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)  # Row found

        result = gate.authorized_cross_app("binder", "story-timeline/atoms/", "read")
        assert result is True

        # Verify DB query was called
        mock_psycopg2.connect.assert_called_once()
        mock_cursor.execute.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("sap.core.gate.psycopg2")
    @patch.dict("os.environ", {"WILLOW_PG_USER": "test_user"})
    def test_connection_denied(self, mock_psycopg2):
        """No matching connection returns False."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # No row found

        result = gate.authorized_cross_app("unauthorized", "story-timeline/atoms/", "read")
        assert result is False

    @patch("sap.core.gate.psycopg2")
    @patch.dict("os.environ", {"WILLOW_PG_USER": "test_user"})
    def test_database_error(self, mock_psycopg2):
        """Database error is caught and returns False."""
        mock_psycopg2.connect.side_effect = Exception("connection failed")

        result = gate.authorized_cross_app("binder", "story-timeline/atoms/")
        assert result is False

    @patch("sap.core.gate.psycopg2")
    @patch.dict("os.environ", {"WILLOW_PG_USER": "test_user"})
    def test_query_includes_scope_path_match(self, mock_psycopg2):
        """Verify the query includes scope_path_matches call."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)

        gate.authorized_cross_app("binder", "story-timeline/user-{uuid}/atoms/", "read")

        # Check that the query mentions scope_path_matches
        call_args = mock_cursor.execute.call_args
        query = call_args[0][0]
        assert "scope_path_matches" in query
        # Check that parameters include collection and access
        params = call_args[0][1]
        assert "story-timeline" in params
        assert "read" in params

    @patch("sap.core.gate.psycopg2")
    @patch.dict("os.environ", {"WILLOW_PG_USER": "test_user"})
    def test_access_type_parameter(self, mock_psycopg2):
        """Verify access type is included in query."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)

        # Test with different access type (default is "read", but method accepts access param)
        gate.authorized_cross_app("binder", "story-timeline/atoms/", access="read")

        call_args = mock_cursor.execute.call_args
        params = call_args[0][1]
        # Should have: requesting_app, target_app, access, collection
        assert len(params) == 4
        assert params[2] == "read"  # access parameter


class TestScopePathIntegration:
    """Integration tests for cross-app scope path matching."""

    @patch("sap.core.gate.psycopg2")
    @patch.dict("os.environ", {"WILLOW_PG_USER": "test_user"})
    def test_uuid_wildcard_in_scope(self, mock_psycopg2):
        """Scope path with {uuid} placeholder is handled."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)

        # Connection scope is user-specific, passed collection includes user
        gate.authorized_cross_app(
            "binder",
            "story-timeline/user-abc123/atoms/",
            access="read"
        )

        # The scope_path_matches function in Postgres handles {uuid} wildcard
        # This test just verifies the path is passed to the query
        call_args = mock_cursor.execute.call_args
        params = call_args[0][1]
        assert "story-timeline/user-abc123/atoms/" in params


class TestDevBypassHostnameCheck:
    """Tests for WILLOW_DEV_HOSTNAMES hostname gate check."""

    def test_gate_mode_pgp_enforced_when_no_dev_root(self):
        original = gate._DEV_SAFE_ROOT
        try:
            gate._DEV_SAFE_ROOT = None
            assert gate.gate_mode() == "pgp_enforced"
        finally:
            gate._DEV_SAFE_ROOT = original

    def test_gate_mode_dev_bypass_when_dev_root_set(self):
        from pathlib import Path
        original = gate._DEV_SAFE_ROOT
        try:
            gate._DEV_SAFE_ROOT = Path("/tmp/fake-dev")
            assert gate.gate_mode() == "dev_bypass"
        finally:
            gate._DEV_SAFE_ROOT = original

    def test_hostname_detail_not_active_by_default(self):
        original = gate._DEV_HOSTNAME_CHECK
        try:
            gate._DEV_HOSTNAME_CHECK = "not_active"
            assert gate.gate_hostname_detail() == "not_active"
        finally:
            gate._DEV_HOSTNAME_CHECK = original

    def test_hostname_detail_passed_when_host_in_allowlist(self):
        original = gate._DEV_HOSTNAME_CHECK
        try:
            gate._DEV_HOSTNAME_CHECK = "passed:my-dev-host"
            assert gate.gate_hostname_detail() == "passed:my-dev-host"
        finally:
            gate._DEV_HOSTNAME_CHECK = original

    def test_hostname_detail_blocked_implies_fail_closed(self):
        """When hostname blocked, _DEV_SAFE_ROOT must be None (pgp_enforced)."""
        original_root = gate._DEV_SAFE_ROOT
        original_check = gate._DEV_HOSTNAME_CHECK
        try:
            gate._DEV_SAFE_ROOT = None
            gate._DEV_HOSTNAME_CHECK = "blocked:prod-server"
            assert gate.gate_hostname_detail() == "blocked:prod-server"
            assert gate.gate_mode() == "pgp_enforced"
        finally:
            gate._DEV_SAFE_ROOT = original_root
            gate._DEV_HOSTNAME_CHECK = original_check

    def test_hostname_detail_unchecked_when_no_allowlist(self):
        original = gate._DEV_HOSTNAME_CHECK
        try:
            gate._DEV_HOSTNAME_CHECK = "unchecked"
            assert gate.gate_hostname_detail() == "unchecked"
        finally:
            gate._DEV_HOSTNAME_CHECK = original

    def test_dev_hostnames_parsed_from_env(self):
        """WILLOW_DEV_HOSTNAMES parses comma-separated list correctly."""
        import importlib, os
        saved = {k: os.environ.get(k) for k in (
            "WILLOW_DEV_SAFE_ROOT", "WILLOW_ALLOW_DEV_GATE", "WILLOW_DEV_HOSTNAMES"
        )}
        try:
            # Clear dev bypass so reload doesn't activate it
            for k in ("WILLOW_DEV_SAFE_ROOT", "WILLOW_ALLOW_DEV_GATE", "WILLOW_DEV_HOSTNAMES"):
                os.environ.pop(k, None)
            os.environ["WILLOW_DEV_HOSTNAMES"] = "host-a, host-b , host-c"
            importlib.reload(gate)
            assert gate._DEV_HOSTNAMES == frozenset({"host-a", "host-b", "host-c"})
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            importlib.reload(gate)

    def test_dev_hostnames_empty_when_env_not_set(self):
        """WILLOW_DEV_HOSTNAMES not set → empty frozenset."""
        import importlib, os
        saved = {k: os.environ.get(k) for k in (
            "WILLOW_DEV_SAFE_ROOT", "WILLOW_ALLOW_DEV_GATE", "WILLOW_DEV_HOSTNAMES"
        )}
        try:
            for k in ("WILLOW_DEV_SAFE_ROOT", "WILLOW_ALLOW_DEV_GATE", "WILLOW_DEV_HOSTNAMES"):
                os.environ.pop(k, None)
            importlib.reload(gate)
            assert gate._DEV_HOSTNAMES == frozenset()
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            importlib.reload(gate)


class TestAuthorizedCrossAppEdgeCases:
    """Edge cases and boundary conditions."""

    @patch("sap.core.gate.psycopg2")
    def test_case_sensitive_app_ids(self, mock_psycopg2):
        """App IDs in query should preserve case."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)

        gate.authorized_cross_app("MyApp", "Target-App/path/", access="read")

        # Verify both app IDs were passed with correct case
        call_args = mock_cursor.execute.call_args
        params = call_args[0][1]
        assert "MyApp" in params
        assert "Target-App" in params

    @patch("sap.core.gate.psycopg2")
    def test_different_access_types(self, mock_psycopg2):
        """Access type parameter affects authorization."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        # Test with read access
        result = gate.authorized_cross_app("app1", "app2/data/", access="read")
        assert result is False

        # Verify "read" was passed
        first_call = mock_cursor.execute.call_args_list[0]
        params = first_call[0][1]
        assert params[2] == "read"
