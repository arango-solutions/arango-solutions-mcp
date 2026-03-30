from typing import Any, Dict, List, Optional

from pydantic import Field

from agents.transaction_management_agent import TransactionManagementAgent
from server import mcp_app

txn_agent = TransactionManagementAgent()


@mcp_app.tool(
    name="begin-transaction",
    description="""Begins a stream transaction for multi-document ACID operations.

    Stream transactions let you perform reads and writes across multiple
    documents and collections atomically. After beginning a transaction
    you receive a transaction_id — pass it to subsequent tools to operate
    within the transaction, then commit or abort.

    You MUST declare the collections you intend to read from, write to,
    or access exclusively. ArangoDB will lock accordingly.

    **Workflow:**
    1. begin-transaction (declare collections) → get transaction_id
    2. Perform operations (AQL, document CRUD) using the transaction_id
    3. commit-transaction OR abort-transaction

    Transactions time out after a server-configured idle period (default 60s).
    """,
)
async def begin_transaction(
    write: Optional[List[str]] = Field(
        default=None,
        description="Collections that will be written to inside this transaction.",
    ),
    read: Optional[List[str]] = Field(
        default=None,
        description="Collections that will be read from inside this transaction.",
    ),
    exclusive: Optional[List[str]] = Field(
        default=None,
        description="Collections requiring exclusive (serialized) access.",
    ),
    sync: Optional[bool] = Field(
        default=None,
        description="If true, forces WAL sync on every operation (safer, slower).",
    ),
    allow_implicit: Optional[bool] = Field(
        default=None,
        description="If true, allows reading from collections not declared upfront.",
    ),
    lock_timeout: Optional[int] = Field(
        default=None,
        description="Timeout in seconds for acquiring collection locks.",
    ),
    max_size: Optional[int] = Field(
        default=None,
        description="Maximum transaction size in bytes before intermediate commits.",
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database. Uses default if not specified.",
    ),
) -> Dict[str, Any]:
    return await txn_agent.arun(
        {
            "operation": "begin_transaction",
            "write": write,
            "read": read,
            "exclusive": exclusive,
            "sync": sync,
            "allow_implicit": allow_implicit,
            "lock_timeout": lock_timeout,
            "max_size": max_size,
            "database_name": database_name,
        }
    )


@mcp_app.tool(
    name="transaction-status",
    description="""Returns the current status of a stream transaction.

    Possible statuses: 'running', 'committed', 'aborted'.
    Use this to check whether a transaction is still active before performing
    further operations within it.
    """,
)
async def transaction_status(
    transaction_id: str = Field(
        description="The transaction ID returned by begin-transaction.",
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database. Uses default if not specified.",
    ),
) -> Dict[str, Any]:
    return await txn_agent.arun(
        {
            "operation": "transaction_status",
            "transaction_id": transaction_id,
            "database_name": database_name,
        }
    )


@mcp_app.tool(
    name="commit-transaction",
    description="""Commits a stream transaction, making all its changes permanent.

    Once committed, the transaction cannot be rolled back.
    All document writes, updates, and deletions performed within the
    transaction become visible to other readers.
    """,
)
async def commit_transaction(
    transaction_id: str = Field(
        description="The transaction ID to commit.",
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database. Uses default if not specified.",
    ),
) -> Dict[str, Any]:
    return await txn_agent.arun(
        {
            "operation": "commit_transaction",
            "transaction_id": transaction_id,
            "database_name": database_name,
        }
    )


@mcp_app.tool(
    name="abort-transaction",
    description="""Aborts (rolls back) a stream transaction, discarding all changes.

    All document writes, updates, and deletions performed within the
    transaction are rolled back as if they never happened.
    """,
)
async def abort_transaction(
    transaction_id: str = Field(
        description="The transaction ID to abort.",
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database. Uses default if not specified.",
    ),
) -> Dict[str, Any]:
    return await txn_agent.arun(
        {
            "operation": "abort_transaction",
            "transaction_id": transaction_id,
            "database_name": database_name,
        }
    )


@mcp_app.tool(
    name="list-transactions",
    description="""Lists all currently running stream transactions on the server.

    Returns transaction IDs and their states.  Useful for auditing
    or cleaning up abandoned transactions.
    """,
)
async def list_transactions(
    database_name: Optional[str] = Field(
        default=None,
        description="Target database. Uses default if not specified.",
    ),
) -> Dict[str, Any]:
    return await txn_agent.arun(
        {
            "operation": "list_transactions",
            "database_name": database_name,
        }
    )


@mcp_app.tool(
    name="execute-transaction",
    description="""Executes a server-side JavaScript transaction atomically.

    **IMPORTANT:** This tool is disabled by default for security.
    Set the ENABLE_JS_TRANSACTIONS=true environment variable to enable it.

    Unlike stream transactions (begin/commit/abort), this runs a
    self-contained JavaScript function on the server in a single request.
    The function receives 'params' and must return a result.

    Use this for short, atomic multi-collection operations where you
    don't need to interleave client-side logic between steps.

    **Example command:**
    ```
    function(params) {
        const db = require('@arangodb').db;
        const col = db._collection(params.collection);
        col.insert({name: params.name});
        return col.count();
    }
    ```
    """,
)
async def execute_transaction(
    command: str = Field(
        description="JavaScript function body to execute server-side.",
    ),
    params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parameters passed to the JavaScript function.",
    ),
    write: Optional[List[str]] = Field(
        default=None,
        description="Collections the function will write to.",
    ),
    read: Optional[List[str]] = Field(
        default=None,
        description="Collections the function will read from.",
    ),
    sync: Optional[bool] = Field(
        default=None,
        description="If true, forces WAL sync (safer, slower).",
    ),
    max_size: Optional[int] = Field(
        default=None,
        description="Maximum transaction size in bytes.",
    ),
    allow_implicit: Optional[bool] = Field(
        default=None,
        description="Allow reading collections not declared upfront.",
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database. Uses default if not specified.",
    ),
) -> Dict[str, Any]:
    return await txn_agent.arun(
        {
            "operation": "execute_transaction",
            "command": command,
            "params": params,
            "write": write,
            "read": read,
            "sync": sync,
            "max_size": max_size,
            "allow_implicit": allow_implicit,
            "database_name": database_name,
        }
    )
