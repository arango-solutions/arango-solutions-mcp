import logging
from typing import Any, Dict, Optional

from arango.database import StandardDatabase

from agents.agent_base import ArangoAgentBase, handle_arango_errors

logger = logging.getLogger(__name__)


def _backup_error_hint(exc: Exception) -> dict | None:
    """Rewrite errors that indicate a non-Enterprise ArangoDB."""
    msg = getattr(exc, "error_message", None) or str(exc)
    msg_lower = msg.lower()
    is_enterprise_only = (
        "hot backup" in msg_lower
        or "enterprise" in msg_lower
        or "unknown path" in msg_lower
        or "not implemented" in msg_lower
        or "501" in msg_lower
        or getattr(exc, "http_code", 0) in (404, 501)
    )
    if is_enterprise_only:
        return {
            "error": (
                "Hot backup is an Enterprise Edition feature. "
                "This ArangoDB instance does not support it."
            )
        }
    return None


class BackupManagementAgent(ArangoAgentBase):
    """Agent for ArangoDB hot-backup management (Enterprise Edition).

    Hot backups create consistent, point-in-time snapshots of the entire
    ArangoDB deployment.  These operations require ArangoDB Enterprise.
    Operations: create, list, restore, delete.
    """

    @handle_arango_errors(
        "BackupManagementAgent",
        "ArangoDB",
        on_arango_error=_backup_error_hint,
    )
    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        database_name: Optional[str] = mcp_tool_inputs.get("database_name")

        logger.info(f"BackupManagementAgent: Op='{operation}', DB='{database_name}'")

        db, _ = self.resolve_db(database_name)

        if operation == "create_backup":
            return await self._create(db, mcp_tool_inputs)
        elif operation == "list_backups":
            return await self._list(db, mcp_tool_inputs)
        elif operation == "restore_backup":
            return await self._restore(db, mcp_tool_inputs)
        elif operation == "delete_backup":
            return await self._delete(db, mcp_tool_inputs)
        else:
            return {"error": f"Unknown backup operation: {operation}"}

    async def _create(self, db: StandardDatabase, inputs: Dict[str, Any]) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = self.pack_optional(
            {},
            label=inputs.get("label"),
            allow_inconsistent=inputs.get("allow_inconsistent"),
            force=inputs.get("force"),
            timeout=inputs.get("timeout"),
        )

        result = await self.run_sync(db.backup.create, **kwargs)
        return {"status": "Backup created.", "backup": result}

    async def _list(self, db: StandardDatabase, inputs: Dict[str, Any]) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = self.pack_optional({}, backup_id=inputs.get("backup_id"))

        result = await self.run_sync(db.backup.get, **kwargs)
        return {"backups": result}

    async def _restore(self, db: StandardDatabase, inputs: Dict[str, Any]) -> Dict[str, Any]:
        backup_id: Optional[str] = inputs.get("backup_id")
        if not backup_id:
            return {"error": "backup_id is required for restore."}

        result = await self.run_sync(db.backup.restore, backup_id)
        return {"status": "Backup restore initiated.", "result": result}

    async def _delete(self, db: StandardDatabase, inputs: Dict[str, Any]) -> Dict[str, Any]:
        backup_id: Optional[str] = inputs.get("backup_id")
        if not backup_id:
            return {"error": "backup_id is required for delete."}

        await self.run_sync(db.backup.delete, backup_id)
        return {"status": f"Backup '{backup_id}' deleted."}
