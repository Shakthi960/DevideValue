"""
Route-level tests for the auth endpoints.

CI does not install supabase, so we stub ``app.core.supabase``
in ``sys.modules`` before importing the router, then swap the
router's ``supabase`` reference with a fake auth client per test.
"""

import os
import sys
import types

os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:///:memory:",
)

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class _FakeSupabase:
    def __init__(self, auth=None):
        self.auth = auth


_fake_supabase_module = types.ModuleType("app.core.supabase")

if "app.core.supabase" not in sys.modules:
    _fake_supabase_module.supabase = _FakeSupabase()
    sys.modules["app.core.supabase"] = _fake_supabase_module

from app.routes import auth as auth_route  # noqa: E402


class _FakeUser:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "user-1")
        self.email = kwargs.get("email", "a@example.com")
        self.user_metadata = kwargs.get("user_metadata", {})
        self.created_at = kwargs.get("created_at", None)


class _FakeSession:
    def __init__(self, access_token="fake-token"):
        self.access_token = access_token


class _FakeResult:
    def __init__(self, user=None, session=None, error=None):
        self.user = user
        self.session = session
        self.error = error


class _FakeAuth:
    def __init__(self, should_raise=False, user=None, session=None):
        self.should_raise = should_raise
        self.user = user
        self.session = session

    def sign_up(self, credentials=None, **kwargs):
        if self.should_raise:
            raise RuntimeError("boom")
        return _FakeResult(
            user=self.user,
            session=self.session,
        )

    def sign_in_with_password(self, credentials=None, **kwargs):
        if self.should_raise:
            raise RuntimeError("boom")
        return _FakeResult(
            user=self.user,
            session=self.session,
        )

    def get_user(self, token):
        if self.should_raise:
            raise RuntimeError("boom")
        return _FakeResult(user=self.user)


def _user_with_full_name():
    return _FakeUser(
        id="user-1",
        email="a@example.com",
        user_metadata={"full_name": "Jane Doe"},
        created_at=None,
    )


class TestAuthRegister:
    def _post(self, monkeypatch, auth_fake, password="secret123"):
        monkeypatch.setattr(
            auth_route,
            "supabase",
            _FakeSupabase(auth=auth_fake),
        )

        app = FastAPI()
        app.include_router(auth_route.router)

        return TestClient(app).post(
            "/api/auth/register",
            json={
                "email": "a@example.com",
                "password": password,
                "full_name": "Jane Doe",
            },
        )

    def test_register_returns_token_and_user(self, monkeypatch):
        auth = _FakeAuth(
            user=_user_with_full_name(),
            session=_FakeSession("reg-token"),
        )

        response = self._post(monkeypatch, auth)

        assert response.status_code == 200

        data = response.json()

        assert data["access_token"] == "reg-token"
        assert data["user"]["email"] == "a@example.com"
        assert data["user"]["full_name"] == "Jane Doe"

    def test_register_short_password_rejected(self, monkeypatch):
        auth = _FakeAuth(
            user=_user_with_full_name(),
            session=_FakeSession("reg-token"),
        )

        response = self._post(monkeypatch, auth, password="123")

        assert response.status_code == 422
        assert "6 characters" in response.json()["detail"]

    def test_register_supabase_error_returns_400(self, monkeypatch):
        auth = _FakeAuth(should_raise=True)

        response = self._post(monkeypatch, auth)

        assert response.status_code == 400

    def test_register_no_user_returns_400(self, monkeypatch):
        auth = _FakeAuth(user=None, session=None)

        response = self._post(monkeypatch, auth)

        assert response.status_code == 400
        assert response.json()["detail"] == "Unable to create user"

    def test_register_no_session_returns_verification_message(
        self,
        monkeypatch,
    ):
        auth = _FakeAuth(
            user=_user_with_full_name(),
            session=None,
        )

        response = self._post(monkeypatch, auth)

        assert response.status_code == 200
        assert "verify your email" in response.json()["detail"].lower()


class TestAuthLogin:
    def _login(self, monkeypatch, auth_fake):
        monkeypatch.setattr(
            auth_route,
            "supabase",
            _FakeSupabase(auth=auth_fake),
        )

        app = FastAPI()
        app.include_router(auth_route.router)

        return TestClient(app).post(
            "/api/auth/login",
            json={
                "email": "a@example.com",
                "password": "secret123",
            },
        )

    def test_login_happy_path(self, monkeypatch):
        auth = _FakeAuth(
            user=_user_with_full_name(),
            session=_FakeSession("login-token"),
        )

        response = self._login(monkeypatch, auth)

        assert response.status_code == 200

        data = response.json()

        assert data["access_token"] == "login-token"
        assert data["user"]["email"] == "a@example.com"

    def test_login_bad_credentials_401(self, monkeypatch):
        auth = _FakeAuth(should_raise=True)

        response = self._login(monkeypatch, auth)

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    def test_login_missing_user_or_session_401(self, monkeypatch):
        auth = _FakeAuth(user=None, session=None)

        response = self._login(monkeypatch, auth)

        assert response.status_code == 401


class TestAuthMe:
    def _me(self, monkeypatch, auth_fake, header=None):
        monkeypatch.setattr(
            auth_route,
            "supabase",
            _FakeSupabase(auth=auth_fake),
        )

        app = FastAPI()
        app.include_router(auth_route.router)

        kwargs = {}

        if header is not None:
            kwargs["headers"] = {"Authorization": header}

        return TestClient(app).get("/api/auth/me", **kwargs)

    def test_me_no_header_401(self, monkeypatch):
        auth = _FakeAuth(user=_user_with_full_name())

        response = self._me(monkeypatch, auth)

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_me_happy_path(self, monkeypatch):
        auth = _FakeAuth(user=_user_with_full_name())

        response = self._me(
            monkeypatch,
            auth,
            header="Bearer good-token",
        )

        assert response.status_code == 200

        data = response.json()

        assert data["id"] == "user-1"
        assert data["email"] == "a@example.com"
        assert data["full_name"] == "Jane Doe"

    def test_me_invalid_token_401(self, monkeypatch):
        auth = _FakeAuth(should_raise=True)

        response = self._me(
            monkeypatch,
            auth,
            header="Bearer bad-token",
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired token"