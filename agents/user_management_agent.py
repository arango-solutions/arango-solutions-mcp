import logging
from typing import Any, Dict

from arango.database import StandardDatabase
from arango.exceptions import (
    UserCreateError,
    UserDeleteError,
    UserGetError,
    UserListError,
    UserUpdateError,
)
from pydantic import SecretStr

from agents.agent_base import ArangoAgentBase, handle_arango_errors
from arango_connector import arango_connector

logger = logging.getLogger(__name__)


def _unwrap_secret(value: Any) -> Any:
    # Unwrap pydantic.SecretStr at the last possible moment before passing the
    # plaintext to the python-arango driver. Plain strings (e.g. from tests
    # that bypass the FastMCP/Pydantic boundary) are passed through unchanged.
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    return value


class UserManagementAgent(ArangoAgentBase):
    """Agent for ArangoDB user and permission management.

    User operations require _system database access. Permission operations
    control database-level and collection-level access grants.
    """

    @handle_arango_errors(
        "UserManagementAgent",
        "User",
        specific_exceptions=(UserCreateError, UserDeleteError, UserGetError, UserListError, UserUpdateError),
    )
    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")

        logger.info(f"UserManagementAgent: Op='{operation}'")

        sys_db = arango_connector.get_system_db()

        if operation == "list_users":
            return await self._list_users(sys_db)
        elif operation == "get_user":
            return await self._get_user(sys_db, mcp_tool_inputs)
        elif operation == "create_user":
            return await self._create_user(sys_db, mcp_tool_inputs)
        elif operation == "update_user":
            return await self._update_user(sys_db, mcp_tool_inputs)
        elif operation == "delete_user":
            return await self._delete_user(sys_db, mcp_tool_inputs)
        elif operation == "list_permissions":
            return await self._list_permissions(sys_db, mcp_tool_inputs)
        elif operation == "get_permission":
            return await self._get_permission(sys_db, mcp_tool_inputs)
        elif operation == "grant_permission":
            return await self._grant_permission(sys_db, mcp_tool_inputs)
        elif operation == "revoke_permission":
            return await self._revoke_permission(sys_db, mcp_tool_inputs)
        else:
            return {"error": f"Unknown user operation: {operation}"}

    async def _list_users(self, db: StandardDatabase) -> Dict[str, Any]:
        users = await self.run_sync(db.users)
        return {"users": users}

    async def _get_user(self, db: StandardDatabase, inputs: Dict[str, Any]) -> Dict[str, Any]:
        username: str | None = inputs.get("username")
        if not username:
            return {"error": "username is required."}

        user = await self.run_sync(db.user, username)
        return {"user": user}

    async def _create_user(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        username: str | None = inputs.get("username")
        password = inputs.get("password")
        active: bool | None = inputs.get("active")
        extra: Dict[str, Any] | None = inputs.get("extra")

        if not username:
            return {"error": "username is required."}

        kwargs: Dict[str, Any] = {"username": username}
        if password is not None:
            kwargs["password"] = _unwrap_secret(password)
        if active is not None:
            kwargs["active"] = active
        if extra is not None:
            kwargs["extra"] = extra

        result = await self.run_sync(db.create_user, **kwargs)
        return {"status": f"User '{username}' created.", "user": result}

    async def _update_user(self, db: StandardDatabase, inputs: Dict[str, Any]) -> Dict[str, Any]:
        username: str | None = inputs.get("username")
        password = inputs.get("password")
        active: bool | None = inputs.get("active")
        extra: Dict[str, Any] | None = inputs.get("extra")

        if not username:
            return {"error": "username is required."}

        kwargs: Dict[str, Any] = {"username": username}
        if password is not None:
            kwargs["password"] = _unwrap_secret(password)
        if active is not None:
            kwargs["active"] = active
        if extra is not None:
            kwargs["extra"] = extra

        result = await self.run_sync(db.update_user, **kwargs)
        return {"status": f"User '{username}' updated.", "user": result}

    async def _delete_user(self, db: StandardDatabase, inputs: Dict[str, Any]) -> Dict[str, Any]:
        username: str | None = inputs.get("username")
        if not username:
            return {"error": "username is required."}

        await self.run_sync(db.delete_user, username)
        return {"status": f"User '{username}' deleted."}

    async def _list_permissions(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        username: str | None = inputs.get("username")
        if not username:
            return {"error": "username is required."}

        perms = await self.run_sync(db.permissions, username)
        return {"username": username, "permissions": perms}

    async def _get_permission(self, db: StandardDatabase, inputs: Dict[str, Any]) -> Dict[str, Any]:
        username: str | None = inputs.get("username")
        database_name: str | None = inputs.get("database_name")
        collection_name: str | None = inputs.get("collection_name")

        if not username:
            return {"error": "username is required."}
        if not database_name:
            return {"error": "database_name is required."}

        perm = await self.run_sync(
            db.permission, username, database_name, collection=collection_name
        )
        result: Dict[str, Any] = {
            "username": username,
            "database": database_name,
            "permission": perm,
        }
        if collection_name:
            result["collection"] = collection_name
        return result

    async def _grant_permission(self, db: StandardDatabase, inputs: Dict[str, Any]) -> Dict[str, Any]:
        username: str | None = inputs.get("username")
        permission: str | None = inputs.get("permission")
        database_name: str | None = inputs.get("database_name")
        collection_name: str | None = inputs.get("collection_name")

        if not username:
            return {"error": "username is required."}
        if not permission:
            return {"error": "permission is required (rw, ro, or none)."}
        if not database_name:
            return {"error": "database_name is required."}

        if permission not in ("rw", "ro", "none"):
            return {"error": f"Invalid permission '{permission}'. Must be 'rw', 'ro', or 'none'."}

        await self.run_sync(
            db.update_permission, username, permission, database_name, collection=collection_name
        )

        target = f"database '{database_name}'"
        if collection_name:
            target = f"collection '{collection_name}' in {target}"
        return {
            "status": f"Granted '{permission}' on {target} to user '{username}'.",
        }

    async def _revoke_permission(self, db: StandardDatabase, inputs: Dict[str, Any]) -> Dict[str, Any]:
        username: str | None = inputs.get("username")
        database_name: str | None = inputs.get("database_name")
        collection_name: str | None = inputs.get("collection_name")

        if not username:
            return {"error": "username is required."}
        if not database_name:
            return {"error": "database_name is required."}

        await self.run_sync(
            db.reset_permission, username, database_name, collection=collection_name
        )

        target = f"database '{database_name}'"
        if collection_name:
            target = f"collection '{collection_name}' in {target}"
        return {
            "status": f"Revoked permission on {target} for user '{username}'.",
        }
