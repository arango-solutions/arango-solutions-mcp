import logging
from typing import Any, Dict, List, Optional, Union

from arango.exceptions import (
    ArangoServerError,
    TransactionAbortError,
    TransactionCommitError,
    TransactionInitError,
    TransactionListError,
    TransactionStatusError,
)

from agents.agent_base import ArangoAgentBase
from arango_connector import arango_connector
from config import settings

logger = logging.getLogger(__name__)


class TransactionManagementAgent(ArangoAgentBase):
    """Agent for ArangoDB stream transaction management.

    Stream transactions provide multi-document ACID guarantees.
    Operations: begin, status, commit, abort, list, execute_within.
    """

    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        database_name: Optional[str] = mcp_tool_inputs.get("database_name")

        logger.info(f"TransactionManagementAgent: Op='{operation}', DB='{database_name}'")

        try:
            db = arango_connector.get_db(database_name)
            database_name = database_name or db.name

            if operation == "begin_transaction":
                return self._begin(db, mcp_tool_inputs)
            elif operation == "transaction_status":
                return self._status(db, mcp_tool_inputs)
            elif operation == "commit_transaction":
                return self._commit(db, mcp_tool_inputs)
            elif operation == "abort_transaction":
                return self._abort(db, mcp_tool_inputs)
            elif operation == "list_transactions":
                return self._list(db)
            elif operation == "execute_transaction":
                return self._execute_js(db, mcp_tool_inputs)
            else:
                return {"error": f"Unknown transaction operation: {operation}"}

        except (
            TransactionInitError,
            TransactionCommitError,
            TransactionAbortError,
            TransactionStatusError,
            TransactionListError,
        ) as e:
            logger.error(f"TransactionManagementAgent: Transaction error - {e}")
            return {
                "error": f"Transaction Error: {e.error_message if hasattr(e, 'error_message') else str(e)}"
            }
        except ArangoServerError as e:
            logger.error(f"TransactionManagementAgent: ArangoDB error - {e}")
            return {
                "error": f"ArangoDB Error: {e.error_message if hasattr(e, 'error_message') else str(e)}"
            }
        except Exception as e:
            logger.error(f"TransactionManagementAgent: Unexpected error - {e}", exc_info=True)
            return {"error": f"An unexpected error occurred: {str(e)}"}

    def _begin(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        read_collections: Optional[Union[str, List[str]]] = inputs.get("read")
        write_collections: Optional[Union[str, List[str]]] = inputs.get("write")
        exclusive_collections: Optional[Union[str, List[str]]] = inputs.get("exclusive")
        sync: Optional[bool] = inputs.get("sync")
        allow_implicit: Optional[bool] = inputs.get("allow_implicit")
        lock_timeout: Optional[int] = inputs.get("lock_timeout")
        max_size: Optional[int] = inputs.get("max_size")

        kwargs: Dict[str, Any] = {}
        if read_collections is not None:
            kwargs["read"] = read_collections
        if write_collections is not None:
            kwargs["write"] = write_collections
        if exclusive_collections is not None:
            kwargs["exclusive"] = exclusive_collections
        if sync is not None:
            kwargs["sync"] = sync
        if allow_implicit is not None:
            kwargs["allow_implicit"] = allow_implicit
        if lock_timeout is not None:
            kwargs["lock_timeout"] = lock_timeout
        if max_size is not None:
            kwargs["max_size"] = max_size

        txn_db = db.begin_transaction(**kwargs)
        txn_id = txn_db.transaction_id

        return {
            "status": "Transaction started.",
            "transaction_id": txn_id,
            "instructions": (
                "Use this transaction_id with commit-transaction or "
                "abort-transaction. Run AQL queries within this transaction "
                "by passing the transaction_id to execute-aql-query (if supported) "
                "or use execute-transaction for server-side JS transactions."
            ),
        }

    def _status(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        txn_id: Optional[str] = inputs.get("transaction_id")
        if not txn_id:
            return {"error": "transaction_id is required."}

        txn_db = db.fetch_transaction(txn_id)
        status = txn_db.transaction_status()

        return {"transaction_id": txn_id, "status": status}

    def _commit(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        txn_id: Optional[str] = inputs.get("transaction_id")
        if not txn_id:
            return {"error": "transaction_id is required."}

        txn_db = db.fetch_transaction(txn_id)
        txn_db.commit_transaction()

        return {
            "status": "Transaction committed successfully.",
            "transaction_id": txn_id,
        }

    def _abort(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        txn_id: Optional[str] = inputs.get("transaction_id")
        if not txn_id:
            return {"error": "transaction_id is required."}

        txn_db = db.fetch_transaction(txn_id)
        txn_db.abort_transaction()

        return {
            "status": "Transaction aborted successfully.",
            "transaction_id": txn_id,
        }

    def _list(self, db) -> Dict[str, Any]:
        transactions = db.list_transactions()
        return {"transactions": transactions}

    def _execute_js(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a server-side JavaScript transaction."""
        if not settings.server.enable_js_transactions:
            return {
                "error": "Server-side JavaScript transactions are disabled. "
                "Set ENABLE_JS_TRANSACTIONS=true to enable this feature."
            }

        command: Optional[str] = inputs.get("command")
        params: Optional[Dict[str, Any]] = inputs.get("params")
        read_collections: Optional[List[str]] = inputs.get("read")
        write_collections: Optional[List[str]] = inputs.get("write")
        sync: Optional[bool] = inputs.get("sync")
        max_size: Optional[int] = inputs.get("max_size")
        allow_implicit: Optional[bool] = inputs.get("allow_implicit")

        if not command:
            return {"error": "command (JavaScript function body) is required."}

        kwargs: Dict[str, Any] = {"command": command}
        if params is not None:
            kwargs["params"] = params
        if read_collections is not None:
            kwargs["read"] = read_collections
        if write_collections is not None:
            kwargs["write"] = write_collections
        if sync is not None:
            kwargs["sync"] = sync
        if max_size is not None:
            kwargs["max_size"] = max_size
        if allow_implicit is not None:
            kwargs["allow_implicit"] = allow_implicit

        result = db.execute_transaction(**kwargs)

        return {"status": "Transaction executed.", "result": result}
