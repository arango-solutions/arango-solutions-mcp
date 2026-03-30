"""Tests for user and permission management."""

import contextlib
import uuid

import pytest
from arango.database import StandardDatabase

from agents.user_management_agent import UserManagementAgent


def _unique_user():
    return f"mcp_test_user_{uuid.uuid4().hex[:8]}"


class TestUserManagement:
    """User CRUD tests using the UserManagementAgent against _system."""

    @pytest.fixture(autouse=True)
    def _setup(self, system_db: StandardDatabase, arango_client, monkeypatch):
        self.agent = UserManagementAgent()
        self.created_users: list[str] = []

        from arango_connector import arango_connector
        from tests.conftest import _PASSWORD, _USERNAME

        monkeypatch.setattr(arango_connector, "client", arango_client)

        def _get_system_db():
            return arango_client.db("_system", username=_USERNAME, password=_PASSWORD)

        monkeypatch.setattr(arango_connector, "get_system_db", _get_system_db)

        yield

        for u in self.created_users:
            with contextlib.suppress(Exception):
                system_db.delete_user(u, ignore_missing=True)

    def _track(self, username: str):
        self.created_users.append(username)

    @pytest.mark.asyncio
    async def test_list_users(self):
        result = await self.agent.arun({"operation": "list_users"})
        assert "error" not in result
        assert "users" in result
        usernames = [u["username"] for u in result["users"]]
        assert "root" in usernames

    @pytest.mark.asyncio
    async def test_create_user(self):
        username = _unique_user()
        self._track(username)

        result = await self.agent.arun(
            {
                "operation": "create_user",
                "username": username,
                "password": "test123",
                "active": True,
            }
        )
        assert "error" not in result
        assert result["user"]["username"] == username
        assert result["user"]["active"] is True

    @pytest.mark.asyncio
    async def test_create_user_with_extra(self):
        username = _unique_user()
        self._track(username)

        result = await self.agent.arun(
            {
                "operation": "create_user",
                "username": username,
                "password": "test123",
                "extra": {"department": "engineering", "role": "analyst"},
            }
        )
        assert "error" not in result
        assert result["user"]["extra"]["department"] == "engineering"

    @pytest.mark.asyncio
    async def test_get_user(self):
        username = _unique_user()
        self._track(username)

        await self.agent.arun(
            {"operation": "create_user", "username": username, "password": "test123"}
        )

        result = await self.agent.arun({"operation": "get_user", "username": username})
        assert "error" not in result
        assert result["user"]["username"] == username

    @pytest.mark.asyncio
    async def test_get_user_not_found(self):
        result = await self.agent.arun(
            {"operation": "get_user", "username": "nonexistent_user_xyz"}
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_update_user(self):
        username = _unique_user()
        self._track(username)

        await self.agent.arun(
            {
                "operation": "create_user",
                "username": username,
                "password": "test123",
                "active": True,
            }
        )

        result = await self.agent.arun(
            {"operation": "update_user", "username": username, "active": False}
        )
        assert "error" not in result
        assert result["user"]["active"] is False

    @pytest.mark.asyncio
    async def test_update_user_extra(self):
        username = _unique_user()
        self._track(username)

        await self.agent.arun(
            {"operation": "create_user", "username": username, "password": "test123"}
        )

        result = await self.agent.arun(
            {
                "operation": "update_user",
                "username": username,
                "extra": {"team": "platform"},
            }
        )
        assert "error" not in result
        assert result["user"]["extra"]["team"] == "platform"

    @pytest.mark.asyncio
    async def test_delete_user(self):
        username = _unique_user()

        await self.agent.arun(
            {"operation": "create_user", "username": username, "password": "test123"}
        )

        result = await self.agent.arun({"operation": "delete_user", "username": username})
        assert "error" not in result
        assert "deleted" in result["status"].lower()

        get_result = await self.agent.arun({"operation": "get_user", "username": username})
        assert "error" in get_result

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self):
        result = await self.agent.arun(
            {"operation": "delete_user", "username": "nonexistent_user_xyz"}
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_user_missing_username(self):
        result = await self.agent.arun({"operation": "create_user"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_user_missing_username(self):
        result = await self.agent.arun({"operation": "get_user"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_unknown_operation(self):
        result = await self.agent.arun({"operation": "nonexistent"})
        assert "error" in result


class TestPermissionManagement:
    """Permission grant/revoke tests."""

    @pytest.fixture(autouse=True)
    def _setup(
        self,
        system_db: StandardDatabase,
        arango_client,
        test_db: StandardDatabase,
        test_db_name: str,
        test_collection: str,
        monkeypatch,
    ):
        self.agent = UserManagementAgent()
        self.db_name = test_db_name
        self.col_name = test_collection
        self.username = _unique_user()

        from arango_connector import arango_connector
        from tests.conftest import _PASSWORD, _USERNAME

        monkeypatch.setattr(arango_connector, "client", arango_client)

        def _get_system_db():
            return arango_client.db("_system", username=_USERNAME, password=_PASSWORD)

        monkeypatch.setattr(arango_connector, "get_system_db", _get_system_db)

        system_db.create_user(self.username, password="test123", active=True)

        yield

        with contextlib.suppress(Exception):
            system_db.delete_user(self.username, ignore_missing=True)

    @pytest.mark.asyncio
    async def test_grant_database_permission(self):
        result = await self.agent.arun(
            {
                "operation": "grant_permission",
                "username": self.username,
                "permission": "rw",
                "database": self.db_name,
            }
        )
        assert "error" not in result
        assert "granted" in result["status"].lower()

    @pytest.mark.asyncio
    async def test_grant_collection_permission(self):
        await self.agent.arun(
            {
                "operation": "grant_permission",
                "username": self.username,
                "permission": "rw",
                "database": self.db_name,
            }
        )

        result = await self.agent.arun(
            {
                "operation": "grant_permission",
                "username": self.username,
                "permission": "ro",
                "database": self.db_name,
                "collection": self.col_name,
            }
        )
        assert "error" not in result
        assert "granted" in result["status"].lower()

    @pytest.mark.asyncio
    async def test_get_permission(self):
        await self.agent.arun(
            {
                "operation": "grant_permission",
                "username": self.username,
                "permission": "ro",
                "database": self.db_name,
            }
        )

        result = await self.agent.arun(
            {
                "operation": "get_permission",
                "username": self.username,
                "database": self.db_name,
            }
        )
        assert "error" not in result
        assert result["permission"] == "ro"

    @pytest.mark.asyncio
    async def test_get_collection_permission(self):
        await self.agent.arun(
            {
                "operation": "grant_permission",
                "username": self.username,
                "permission": "rw",
                "database": self.db_name,
            }
        )
        await self.agent.arun(
            {
                "operation": "grant_permission",
                "username": self.username,
                "permission": "ro",
                "database": self.db_name,
                "collection": self.col_name,
            }
        )

        result = await self.agent.arun(
            {
                "operation": "get_permission",
                "username": self.username,
                "database": self.db_name,
                "collection": self.col_name,
            }
        )
        assert "error" not in result
        assert result["permission"] == "ro"
        assert result["collection"] == self.col_name

    @pytest.mark.asyncio
    async def test_list_permissions(self):
        await self.agent.arun(
            {
                "operation": "grant_permission",
                "username": self.username,
                "permission": "rw",
                "database": self.db_name,
            }
        )

        result = await self.agent.arun({"operation": "list_permissions", "username": self.username})
        assert "error" not in result
        assert "permissions" in result
        assert self.db_name in result["permissions"]

    @pytest.mark.asyncio
    async def test_revoke_permission(self):
        await self.agent.arun(
            {
                "operation": "grant_permission",
                "username": self.username,
                "permission": "rw",
                "database": self.db_name,
            }
        )

        result = await self.agent.arun(
            {
                "operation": "revoke_permission",
                "username": self.username,
                "database": self.db_name,
            }
        )
        assert "error" not in result
        assert "revoked" in result["status"].lower()

    @pytest.mark.asyncio
    async def test_grant_invalid_permission(self):
        result = await self.agent.arun(
            {
                "operation": "grant_permission",
                "username": self.username,
                "permission": "admin",
                "database": self.db_name,
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_grant_missing_username(self):
        result = await self.agent.arun(
            {
                "operation": "grant_permission",
                "permission": "rw",
                "database": self.db_name,
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_grant_missing_database(self):
        result = await self.agent.arun(
            {
                "operation": "grant_permission",
                "username": self.username,
                "permission": "rw",
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_grant_missing_permission(self):
        result = await self.agent.arun(
            {
                "operation": "grant_permission",
                "username": self.username,
                "database": self.db_name,
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_revoke_missing_database(self):
        result = await self.agent.arun(
            {
                "operation": "revoke_permission",
                "username": self.username,
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_permission_missing_database(self):
        result = await self.agent.arun(
            {
                "operation": "get_permission",
                "username": self.username,
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_list_permissions_missing_username(self):
        result = await self.agent.arun({"operation": "list_permissions"})
        assert "error" in result
