# grove/mcp_auth.py — Grove OAuth 2.0 PKCE provider (single-user)
# b17: GRMOAUTH  ΔΣ=42
"""
Single-user OAuth 2.0 PKCE provider for grove.mcp_local --serve mode.

Flow:
  1. claude.ai hits /authorize → provider redirects to /grove-approve?pending=<key>
  2. USER opens that URL in a browser, clicks Allow
  3. Provider issues an auth code → client exchanges for access + refresh tokens
  4. Tokens stored in token_path JSON file; access tokens expire in 30 days

State is in-memory for pending codes (lost on restart, which just means
claude.ai re-auths). Tokens are persisted to token_path so reconnects work.
"""
import json
import secrets
import time
from pathlib import Path
from typing import Any

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

_ACCESS_TTL  = 30 * 86400  # 30 days (single-user local; claude.ai doesn't auto-refresh)
_CODE_TTL    = 300         # 5 minutes
_REFRESH_TTL = 30 * 86400  # 30 days


def _tok() -> str:
    return secrets.token_urlsafe(32)


class GroveOAuthProvider:
    """
    Minimal single-user OAuth provider. Clients register dynamically.
    Authorization requires USER to click Allow at /grove-approve.
    """

    def __init__(self, token_path: Path, base_url: str) -> None:
        self._token_path = Path(token_path)
        self._base_url   = base_url.rstrip("/")

        # In-memory: pending approvals {key: (client, params)}
        self._pending: dict[str, tuple[OAuthClientInformationFull, AuthorizationParams]] = {}
        # In-memory: issued auth codes {code: AuthorizationCode}
        self._codes:   dict[str, AuthorizationCode] = {}

        # Persisted state
        self._state: dict[str, Any] = self._load_state()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_state(self) -> dict:
        if self._token_path.exists():
            try:
                return json.loads(self._token_path.read_text())
            except Exception:
                pass
        return {"clients": {}, "access_tokens": {}, "refresh_tokens": {}}

    def _save_state(self) -> None:
        self._token_path.parent.mkdir(parents=True, exist_ok=True)
        self._token_path.write_text(json.dumps(self._state, indent=2))

    # ── Pending approval helpers (called by grove_approve route) ──────────────

    def pop_pending(self, key: str):
        return self._pending.pop(key, None)

    def issue_code(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        code_str = _tok()
        self._codes[code_str] = AuthorizationCode(
            code=code_str,
            scopes=params.scopes or ["grove"],
            expires_at=time.time() + _CODE_TTL,
            client_id=client.client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
        )
        return code_str

    # ── OAuthAuthorizationServerProvider protocol ─────────────────────────────

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        data = self._state["clients"].get(client_id)
        if data is None:
            return None
        return OAuthClientInformationFull(**data)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self._state["clients"][client_info.client_id] = client_info.model_dump(mode="json")
        self._save_state()

    async def authorize(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        key = secrets.token_urlsafe(16)
        self._pending[key] = (client, params)
        return f"{self._base_url}/grove-approve?pending={key}"

    async def load_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: str,
    ) -> AuthorizationCode | None:
        code = self._codes.get(authorization_code)
        if code is None:
            return None
        if code.client_id != client.client_id:
            return None
        if code.expires_at < time.time():
            del self._codes[authorization_code]
            return None
        return code

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AuthorizationCode,
    ) -> OAuthToken:
        # Consume the code
        self._codes.pop(authorization_code.code, None)

        access_tok  = _tok()
        refresh_tok = _tok()
        now         = int(time.time())

        self._state["access_tokens"][access_tok] = {
            "token":     access_tok,
            "client_id": client.client_id,
            "scopes":    authorization_code.scopes,
            "expires_at": now + _ACCESS_TTL,
        }
        self._state["refresh_tokens"][refresh_tok] = {
            "token":     refresh_tok,
            "client_id": client.client_id,
            "scopes":    authorization_code.scopes,
            "expires_at": now + _REFRESH_TTL,
        }
        self._save_state()

        return OAuthToken(
            access_token=access_tok,
            token_type="bearer",
            expires_in=_ACCESS_TTL,
            refresh_token=refresh_tok,
            scope=" ".join(authorization_code.scopes),
        )

    async def load_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: str,
    ) -> RefreshToken | None:
        data = self._state["refresh_tokens"].get(refresh_token)
        if data is None:
            return None
        if data["client_id"] != client.client_id:
            return None
        exp = data.get("expires_at")
        if exp and exp < time.time():
            del self._state["refresh_tokens"][refresh_token]
            self._save_state()
            return None
        return RefreshToken(**data)

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        # Rotate both tokens
        self._state["refresh_tokens"].pop(refresh_token.token, None)

        effective_scopes = scopes or refresh_token.scopes
        access_tok  = _tok()
        new_refresh = _tok()
        now         = int(time.time())

        self._state["access_tokens"][access_tok] = {
            "token":     access_tok,
            "client_id": client.client_id,
            "scopes":    effective_scopes,
            "expires_at": now + _ACCESS_TTL,
        }
        self._state["refresh_tokens"][new_refresh] = {
            "token":     new_refresh,
            "client_id": client.client_id,
            "scopes":    effective_scopes,
            "expires_at": now + _REFRESH_TTL,
        }
        self._save_state()

        return OAuthToken(
            access_token=access_tok,
            token_type="bearer",
            expires_in=_ACCESS_TTL,
            refresh_token=new_refresh,
            scope=" ".join(effective_scopes),
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        data = self._state["access_tokens"].get(token)
        if data is None:
            return None
        exp = data.get("expires_at")
        if exp and exp < time.time():
            del self._state["access_tokens"][token]
            self._save_state()
            return None
        return AccessToken(**data)

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        if isinstance(token, AccessToken):
            self._state["access_tokens"].pop(token.token, None)
        else:
            self._state["refresh_tokens"].pop(token.token, None)
        self._save_state()
