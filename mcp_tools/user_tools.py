from typing import Any, Dict, Literal, Optional

from pydantic import Field

from agents.user_management_agent import UserManagementAgent
from server import mcp_app

user_agent = UserManagementAgent()


@mcp_app.tool(
    name="list-users",
    description="""Lists all users on the ArangoDB server.

    Returns username, active status, and any extra metadata for each user.
    Requires _system database access.
    """,
)
async def list_users() -> Dict[str, Any]:
    return await user_agent.arun({"operation": "list_users"})


@mcp_app.tool(
    name="get-user",
    description="""Gets details for a specific ArangoDB user.

    Returns the user's active status, extra metadata, and other properties.
    """,
)
async def get_user(
    username: str = Field(description="The username to look up."),
) -> Dict[str, Any]:
    return await user_agent.arun({"operation": "get_user", "username": username})


@mcp_app.tool(
    name="create-user",
    description="""Creates a new ArangoDB user.

    The user is created at the server level and can then be granted
    database-level and collection-level permissions with grant-permission.
    """,
)
async def create_user(
    username: str = Field(description="Username for the new user."),
    password: Optional[str] = Field(
        default=None, description="Password. If omitted, the user has no password."
    ),
    active: Optional[bool] = Field(
        default=None, description="Whether the user is active (default true)."
    ),
    extra: Optional[Dict[str, Any]] = Field(
        default=None, description="Arbitrary extra data to store with the user."
    ),
) -> Dict[str, Any]:
    return await user_agent.arun(
        {
            "operation": "create_user",
            "username": username,
            "password": password,
            "active": active,
            "extra": extra,
        }
    )


@mcp_app.tool(
    name="update-user",
    description="""Updates an existing ArangoDB user.

    Any provided field (password, active, extra) is updated; omitted fields
    are left unchanged.
    """,
)
async def update_user(
    username: str = Field(description="Username to update."),
    password: Optional[str] = Field(default=None, description="New password."),
    active: Optional[bool] = Field(default=None, description="Set active status."),
    extra: Optional[Dict[str, Any]] = Field(default=None, description="Extra metadata to merge."),
) -> Dict[str, Any]:
    return await user_agent.arun(
        {
            "operation": "update_user",
            "username": username,
            "password": password,
            "active": active,
            "extra": extra,
        }
    )


@mcp_app.tool(
    name="delete-user",
    description="""Deletes an ArangoDB user.

    Permanently removes the user and all their permission grants.
    """,
)
async def delete_user(
    username: str = Field(description="Username to delete."),
) -> Dict[str, Any]:
    return await user_agent.arun({"operation": "delete_user", "username": username})


@mcp_app.tool(
    name="list-permissions",
    description="""Lists all permission grants for a user.

    Returns a nested structure of database → collection → permission level.
    Permission levels are 'rw' (read-write), 'ro' (read-only), or 'none'.
    """,
)
async def list_permissions(
    username: str = Field(description="Username to list permissions for."),
) -> Dict[str, Any]:
    return await user_agent.arun({"operation": "list_permissions", "username": username})


@mcp_app.tool(
    name="get-permission",
    description="""Gets the effective permission level for a user on a database or collection.

    Returns 'rw', 'ro', or 'none'. If a collection is specified, returns
    the collection-level permission (falling back to the database-level grant).
    """,
)
async def get_permission(
    username: str = Field(description="Username."),
    database: str = Field(description="Database name."),
    collection: Optional[str] = Field(
        default=None,
        description="Collection name. If omitted, returns the database-level permission.",
    ),
) -> Dict[str, Any]:
    return await user_agent.arun(
        {
            "operation": "get_permission",
            "username": username,
            "database": database,
            "collection": collection,
        }
    )


@mcp_app.tool(
    name="grant-permission",
    description="""Grants a permission level to a user on a database or collection.

    Permission levels:
    - 'rw': read and write access
    - 'ro': read-only access
    - 'none': no access (explicitly deny)

    If collection is specified, the grant applies to that collection only.
    Otherwise it applies to the entire database.
    """,
)
async def grant_permission(
    username: str = Field(description="Username to grant permission to."),
    permission: Literal["rw", "ro", "none"] = Field(
        description="Permission level: 'rw', 'ro', or 'none'."
    ),
    database: str = Field(description="Target database."),
    collection: Optional[str] = Field(
        default=None,
        description="Target collection. If omitted, permission applies to the whole database.",
    ),
) -> Dict[str, Any]:
    return await user_agent.arun(
        {
            "operation": "grant_permission",
            "username": username,
            "permission": permission,
            "database": database,
            "collection": collection,
        }
    )


@mcp_app.tool(
    name="revoke-permission",
    description="""Revokes a permission grant for a user on a database or collection.

    Removes the explicit permission, causing the user to fall back to the
    next higher level (collection → database → server default).
    """,
)
async def revoke_permission(
    username: str = Field(description="Username to revoke permission from."),
    database: str = Field(description="Target database."),
    collection: Optional[str] = Field(
        default=None,
        description="Target collection. If omitted, revokes the database-level grant.",
    ),
) -> Dict[str, Any]:
    return await user_agent.arun(
        {
            "operation": "revoke_permission",
            "username": username,
            "database": database,
            "collection": collection,
        }
    )
