import logging
from typing import Any, Dict, Optional

from arango.exceptions import ArangoServerError

from agents.agent_base import ArangoAgentBase
from arango_connector import arango_connector

logger = logging.getLogger(__name__)


class BackupManagementAgent(ArangoAgentBase):
    """Agent for ArangoDB hot-backup management (Enterprise Edition).

    Hot backups create consistent, point-in-time snapshots of the entire
    ArangoDB deployment.  These operations require ArangoDB Enterprise.
    Operations: create, list, restore, delete.
    """

    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        database_name: Optional[str] = mcp_tool_inputs.get("database_name")

        logger.info(f"BackupManagementAgent: Op='{operation}', DB='{database_name}'")

        try:
            db = arango_connector.get_db(database_name)

            if operation == "create_backup":
                return self._create(db, mcp_tool_inputs)
            elif operation == "list_backups":
                return self._list(db, mcp_tool_inputs)
            elif operation == "restore_backup":
                return self._restore(db, mcp_tool_inputs)
            elif operation == "delete_backup":
                return self._delete(db, mcp_tool_inputs)
            else:
                return {"error": f"Unknown backup operation: {operation}"}

        except ArangoServerError as e:
            msg = e.error_message if hasattr(e, "error_message") else str(e)
            msg_lower = msg.lower()
            is_enterprise_only = (
                "hot backup" in msg_lower
                or "enterprise" in msg_lower
                or "unknown path" in msg_lower
                or getattr(e, "http_code", 0) in (404, 501)
            )
            if is_enterprise_only and "/_admin/backup" in msg:
                return {
                    "error": (
                        "Hot backup is an Enterprise Edition feature. "
                        "This ArangoDB instance does not support it."
                    )
                }
            logger.error(f"BackupManagementAgent: ArangoDB error - {e}")
            return {"error": f"ArangoDB Error: {msg}"}
        except Exception as e:
            error_str = str(e).lower()
            if "enterprise" in error_str or "not implemented" in error_str or "501" in error_str:
                return {
                    "error": (
                        "Hot backup is an Enterprise Edition feature. "
                        "This ArangoDB instance does not support it."
                    )
                }
            logger.error(f"BackupManagementAgent: Unexpected error - {e}", exc_info=True)
            return {"error": f"An unexpected error occurred: {str(e)}"}

    def _create(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        label: Optional[str] = inputs.get("label")
        allow_inconsistent: Optional[bool] = inputs.get("allow_inconsistent")
        force: Optional[bool] = inputs.get("force")
        timeout: Optional[int] = inputs.get("timeout")

        kwargs: Dict[str, Any] = {}
        if label is not None:
            kwargs["label"] = label
        if allow_inconsistent is not None:
            kwargs["allow_inconsistent"] = allow_inconsistent
        if force is not None:
            kwargs["force"] = force
        if timeout is not None:
            kwargs["timeout"] = timeout

        result = db.backup.create(**kwargs)
        return {"status": "Backup created.", "backup": result}

    def _list(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        backup_id: Optional[str] = inputs.get("backup_id")

        kwargs: Dict[str, Any] = {}
        if backup_id is not None:
            kwargs["backup_id"] = backup_id

        result = db.backup.get(**kwargs)
        return {"backups": result}

    def _restore(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        backup_id: Optional[str] = inputs.get("backup_id")
        if not backup_id:
            return {"error": "backup_id is required for restore."}

        result = db.backup.restore(backup_id)
        return {"status": "Backup restore initiated.", "result": result}

    def _delete(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        backup_id: Optional[str] = inputs.get("backup_id")
        if not backup_id:
            return {"error": "backup_id is required for delete."}

        db.backup.delete(backup_id)
        return {"status": f"Backup '{backup_id}' deleted."}
