import logging
from typing import Any, Dict, Optional

from arango.exceptions import (
    ArangoServerError,
    UserCreateError,
    UserDeleteError,
    UserGetError,
    UserListError,
    UserUpdateError,
)

from agents.agent_base import ArangoAgentBase
from arango_connector import arango_connector

logger = logging.getLogger(__name__)


class UserManagementAgent(ArangoAgentBase):
    """Agent for ArangoDB user and permission management.

    User operations require _system database access. Permission operations
    control database-level and collection-level access grants.
    """

    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")

        logger.info(f"UserManagementAgent: Op='{operation}'")

        try:
            sys_db = arango_connector.get_system_db()

            if operation == "list_users":
                return self._list_users(sys_db)
            elif operation == "get_user":
                return self._get_user(sys_db, mcp_tool_inputs)
            elif operation == "create_user":
                return self._create_user(sys_db, mcp_tool_inputs)
            elif operation == "update_user":
                return self._update_user(sys_db, mcp_tool_inputs)
            elif operation == "delete_user":
                return self._delete_user(sys_db, mcp_tool_inputs)
            elif operation == "list_permissions":
                return self._list_permissions(sys_db, mcp_tool_inputs)
            elif operation == "get_permission":
                return self._get_permission(sys_db, mcp_tool_inputs)
            elif operation == "grant_permission":
                return self._grant_permission(sys_db, mcp_tool_inputs)
            elif operation == "revoke_permission":
                return self._revoke_permission(sys_db, mcp_tool_inputs)
            else:
                return {"error": f"Unknown user operation: {operation}"}

        except (
            UserCreateError,
            UserDeleteError,
            UserGetError,
            UserListError,
            UserUpdateError,
        ) as e:
            logger.error(f"UserManagementAgent: User error - {e}")
            return {
                "error": f"User Error: {e.error_message if hasattr(e, 'error_message') else str(e)}"
            }
        except ArangoServerError as e:
            logger.error(f"UserManagementAgent: ArangoDB error - {e}")
            return {
                "error": f"ArangoDB Error: {e.error_message if hasattr(e, 'error_message') else str(e)}"
            }
        except Exception as e:
            logger.error(f"UserManagementAgent: Unexpected error - {e}", exc_info=True)
            return {"error": f"An unexpected error occurred: {str(e)}"}

    def _list_users(self, db) -> Dict[str, Any]:
        users = db.users()
        return {"users": users}

    def _get_user(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        username: Optional[str] = inputs.get("username")
        if not username:
            return {"error": "username is required."}

        user = db.user(username)
        return {"user": user}

    def _create_user(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        username: Optional[str] = inputs.get("username")
        password: Optional[str] = inputs.get("password")
        active: Optional[bool] = inputs.get("active")
        extra: Optional[Dict[str, Any]] = inputs.get("extra")

        if not username:
            return {"error": "username is required."}

        kwargs: Dict[str, Any] = {"username": username}
        if password is not None:
            kwargs["password"] = password
        if active is not None:
            kwargs["active"] = active
        if extra is not None:
            kwargs["extra"] = extra

        result = db.create_user(**kwargs)
        return {"status": f"User '{username}' created.", "user": result}

    def _update_user(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        username: Optional[str] = inputs.get("username")
        password: Optional[str] = inputs.get("password")
        active: Optional[bool] = inputs.get("active")
        extra: Optional[Dict[str, Any]] = inputs.get("extra")

        if not username:
            return {"error": "username is required."}

        kwargs: Dict[str, Any] = {"username": username}
        if password is not None:
            kwargs["password"] = password
        if active is not None:
            kwargs["active"] = active
        if extra is not None:
            kwargs["extra"] = extra

        result = db.update_user(**kwargs)
        return {"status": f"User '{username}' updated.", "user": result}

    def _delete_user(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        username: Optional[str] = inputs.get("username")
        if not username:
            return {"error": "username is required."}

        db.delete_user(username)
        return {"status": f"User '{username}' deleted."}

    def _list_permissions(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        username: Optional[str] = inputs.get("username")
        if not username:
            return {"error": "username is required."}

        perms = db.permissions(username)
        return {"username": username, "permissions": perms}

    def _get_permission(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        username: Optional[str] = inputs.get("username")
        database: Optional[str] = inputs.get("database")
        collection: Optional[str] = inputs.get("collection")

        if not username:
            return {"error": "username is required."}
        if not database:
            return {"error": "database is required."}

        perm = db.permission(username, database, collection=collection)
        result: Dict[str, Any] = {
            "username": username,
            "database": database,
            "permission": perm,
        }
        if collection:
            result["collection"] = collection
        return result

    def _grant_permission(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        username: Optional[str] = inputs.get("username")
        permission: Optional[str] = inputs.get("permission")
        database: Optional[str] = inputs.get("database")
        collection: Optional[str] = inputs.get("collection")

        if not username:
            return {"error": "username is required."}
        if not permission:
            return {"error": "permission is required (rw, ro, or none)."}
        if not database:
            return {"error": "database is required."}

        if permission not in ("rw", "ro", "none"):
            return {"error": f"Invalid permission '{permission}'. Must be 'rw', 'ro', or 'none'."}

        db.update_permission(username, permission, database, collection=collection)

        target = f"database '{database}'"
        if collection:
            target = f"collection '{collection}' in {target}"
        return {
            "status": f"Granted '{permission}' on {target} to user '{username}'.",
        }

    def _revoke_permission(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        username: Optional[str] = inputs.get("username")
        database: Optional[str] = inputs.get("database")
        collection: Optional[str] = inputs.get("collection")

        if not username:
            return {"error": "username is required."}
        if not database:
            return {"error": "database is required."}

        db.reset_permission(username, database, collection=collection)

        target = f"database '{database}'"
        if collection:
            target = f"collection '{collection}' in {target}"
        return {
            "status": f"Revoked permission on {target} for user '{username}'.",
        }
