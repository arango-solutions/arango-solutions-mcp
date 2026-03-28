from typing import Any, Dict, Optional

from pydantic import Field

from agents.backup_management_agent import BackupManagementAgent
from server import mcp_app

backup_agent = BackupManagementAgent()


@mcp_app.tool(
    name="create-backup",
    description="""Creates a hot backup of the entire ArangoDB deployment.

    **Enterprise Edition only.**

    Hot backups are consistent, point-in-time snapshots that include all
    databases, collections, indexes, views, and graphs. They are created
    while the server is running and serving requests.

    The backup is stored on the server's local filesystem (or configured
    backup directory). Returns the backup ID for later restore or delete.
    """,
)
async def create_backup(
    label: Optional[str] = Field(
        default=None,
        description="Human-readable label for the backup (appended to the auto-generated ID).",
    ),
    allow_inconsistent: Optional[bool] = Field(
        default=None,
        description="If true, allows potentially inconsistent backup (e.g. during heavy writes).",
    ),
    force: Optional[bool] = Field(
        default=None,
        description="If true, aborts ongoing transactions to force a consistent snapshot.",
    ),
    timeout: Optional[int] = Field(
        default=None,
        description="Timeout in seconds to wait for the backup to complete.",
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database for authentication. Backup covers the entire deployment.",
    ),
) -> Dict[str, Any]:
    return await backup_agent.arun(
        {
            "operation": "create_backup",
            "label": label,
            "allow_inconsistent": allow_inconsistent,
            "force": force,
            "timeout": timeout,
            "database_name": database_name,
        }
    )


@mcp_app.tool(
    name="list-backups",
    description="""Lists available hot backups on the ArangoDB deployment.

    **Enterprise Edition only.**

    Returns metadata for all backups, or a specific backup if backup_id
    is provided. Metadata includes backup ID, timestamp, size, and version.
    """,
)
async def list_backups(
    backup_id: Optional[str] = Field(
        default=None,
        description="Specific backup ID to retrieve. Lists all if omitted.",
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database for authentication.",
    ),
) -> Dict[str, Any]:
    return await backup_agent.arun(
        {
            "operation": "list_backups",
            "backup_id": backup_id,
            "database_name": database_name,
        }
    )


@mcp_app.tool(
    name="restore-backup",
    description="""Restores the ArangoDB deployment from a hot backup.

    **Enterprise Edition only.**

    WARNING: This replaces ALL data on the server with the backup contents.
    The server will restart during the restore process. Use with extreme caution.
    """,
)
async def restore_backup(
    backup_id: str = Field(
        description="The backup ID to restore from (as returned by create-backup or list-backups).",
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database for authentication.",
    ),
) -> Dict[str, Any]:
    return await backup_agent.arun(
        {
            "operation": "restore_backup",
            "backup_id": backup_id,
            "database_name": database_name,
        }
    )


@mcp_app.tool(
    name="delete-backup",
    description="""Deletes a hot backup from the ArangoDB deployment.

    **Enterprise Edition only.**

    Permanently removes the backup files from the server's filesystem.
    This action cannot be undone.
    """,
)
async def delete_backup(
    backup_id: str = Field(
        description="The backup ID to delete.",
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database for authentication.",
    ),
) -> Dict[str, Any]:
    return await backup_agent.arun(
        {
            "operation": "delete_backup",
            "backup_id": backup_id,
            "database_name": database_name,
        }
    )
