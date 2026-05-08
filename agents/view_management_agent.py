import logging
from typing import Any, Dict, Optional

from arango.database import StandardDatabase
from arango.exceptions import (
    ArangoServerError,
    ViewCreateError,
    ViewDeleteError,
    ViewGetError,
    ViewListError,
    ViewUpdateError,
)

from agents.agent_base import ArangoAgentBase, handle_arango_errors

logger = logging.getLogger(__name__)


class ViewManagementAgent(ArangoAgentBase):
    async def _view_exists(self, db_instance: StandardDatabase, view_name: str) -> bool:
        """
        Helper function to check if a view exists.
        Returns True if the view exists, False if it does not.
        Re-raises exceptions for errors other than 'not found'.
        """
        if not view_name:
            return False
        try:
            await self.run_sync(db_instance.view, view_name)  # Attempt to get view properties
            logger.debug(f"_view_exists: View '{view_name}' found.")
            return True
        except ViewGetError as e:
            # Error code 1207: view not found
            # Error code 1203: ERROR_ARANGO_DATA_SOURCE_NOT_FOUND (can also mean view not found)
            if e.error_code in [1203, 1207]:
                logger.debug(
                    f"_view_exists: View '{view_name}' not found (ViewGetError code {e.error_code})."
                )
                return False
            # For other ViewGetErrors (e.g., permission issues), re-raise
            logger.warning(
                f"_view_exists: Unexpected ViewGetError for view '{view_name}' (code: {e.error_code}): {e.error_message}",
                exc_info=True,
            )
            raise
        except ArangoServerError as e:
            # Some ArangoDB versions might throw a more generic ArangoServerError for not found
            if e.error_code in [1203, 1207]:
                logger.debug(
                    f"_view_exists: View '{view_name}' not found (ArangoServerError code {e.error_code})."
                )
                return False
            logger.warning(
                f"_view_exists: Unexpected ArangoServerError for view '{view_name}' (code: {e.error_code}): {e.error_message}",
                exc_info=True,
            )
            raise
        except Exception as e:  # Catch any other unexpected exceptions
            logger.error(
                f"_view_exists: Unexpected exception while checking view '{view_name}': {e}",
                exc_info=True,
            )
            raise

    @handle_arango_errors(
        "ViewManagementAgent",
        "View",
        specific_exceptions=(
            ViewListError,
            ViewCreateError,
            ViewDeleteError,
            ViewUpdateError,
            ViewGetError,
        ),
    )
    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        database_name: Optional[str] = mcp_tool_inputs.get("database_name")
        view_name: Optional[str] = mcp_tool_inputs.get("view_name")
        view_type: Optional[str] = mcp_tool_inputs.get("view_type")
        properties: Dict[str, Any] = (
            mcp_tool_inputs.get("properties")
            if mcp_tool_inputs.get("properties") is not None
            else {}
        )

        logger.info(
            f"ViewManagementAgent: Op='{operation}', DB='{database_name}', View='{view_name}', Type='{view_type}', Props='{str(properties)[:100]}...'"
        )

        db, database_name = self.resolve_db(database_name)

        if operation == "list_views":
            views = await self.run_sync(db.views)
            return {"views": views}

        elif operation == "create_view":
            if not view_name or not view_type:
                logger.warning(
                    "ViewManagementAgent: View name and type are required for create_view."
                )
                return {"error": "View name and type are required for creation."}

            if await self._view_exists(db, view_name):
                return {
                    "status": f"View '{view_name}' already exists in database '{database_name}'."
                }

            current_properties = properties

            logger.info(
                f"Attempting to create view '{view_name}' of type '{view_type}' with properties: {current_properties}"
            )

            if view_type.lower() == "arangosearch":
                view_info = await self.run_sync(
                    db.create_arangosearch_view,
                    name=view_name,
                    properties=current_properties,
                )
            elif view_type.lower() == "search-alias":
                if not current_properties or "indexes" not in current_properties:
                    return {
                        "error": "For 'search-alias' view type, 'properties' argument must include 'indexes' definition."
                    }
                view_info = await self.run_sync(
                    db.create_view,
                    name=view_name,
                    view_type="search-alias",
                    properties=current_properties,
                )
            else:
                return {
                    "error": f"Unsupported view type '{view_type}'. Supported types: 'arangosearch', 'search-alias'."
                }
            logger.info(f"View '{view_name}' created successfully.")
            return {"status": "View created successfully.", "view_info": view_info}

        elif operation == "get_view_properties":
            if not view_name:
                return {"error": "View name is required to get properties."}
            if not await self._view_exists(db, view_name):
                return {"error": f"View '{view_name}' not found in database '{database_name}'."}
            view_info = await self.run_sync(db.view, view_name)
            return {"view_properties": view_info}

        elif operation == "update_view_properties":
            if not view_name:
                return {"error": "View name is required for update."}
            if not await self._view_exists(db, view_name):
                return {"error": f"View '{view_name}' not found."}

            view_obj_props = await self.run_sync(db.view, view_name)
            view_actual_type = view_obj_props.get("type")
            logger.info(
                f"Updating view '{view_name}' of type '{view_actual_type}' with properties: {properties}"
            )

            if view_actual_type == "arangosearch":
                updated_props = await self.run_sync(
                    db.update_arangosearch_view,
                    name=view_name,
                    properties=properties,
                )
            elif view_actual_type == "search-alias":
                updated_props = await self.run_sync(
                    db.update_view,
                    name=view_name,
                    properties=properties,
                )
            else:
                logger.warning(
                    f"Attempting generic update for unknown or non-specific view type: {view_actual_type}"
                )
                updated_props = await self.run_sync(
                    db.update_view,
                    name=view_name,
                    properties=properties,
                )
            return {"status": "View properties updated.", "updated_properties": updated_props}

        elif operation == "replace_view_properties":
            if not view_name:
                return {"error": "View name is required for replacement."}
            if not await self._view_exists(db, view_name):
                return {"error": f"View '{view_name}' not found."}

            view_obj_props = await self.run_sync(db.view, view_name)
            view_actual_type = view_obj_props.get("type")
            logger.info(
                f"Replacing properties for view '{view_name}' of type '{view_actual_type}' with: {properties}"
            )

            if view_actual_type == "arangosearch":
                replaced_props = await self.run_sync(
                    db.replace_arangosearch_view,
                    name=view_name,
                    properties=properties,
                )
            elif view_actual_type == "search-alias":
                if "indexes" not in properties:
                    return {
                        "error": "For replacing 'search-alias' view type, 'properties' must include 'indexes' definition."
                    }
                replaced_props = await self.run_sync(
                    db.replace_view,
                    name=view_name,
                    view_type="search-alias",
                    properties=properties,
                )
            else:
                logger.warning(
                    f"Attempting generic replace for non-specific view type: {view_actual_type}."
                )
                replaced_props = await self.run_sync(
                    db.replace_view,
                    name=view_name,
                    view_type=view_actual_type,
                    properties=properties,
                )

            return {
                "status": "View properties replaced.",
                "replaced_properties": replaced_props,
            }

        elif operation == "delete_view":
            if not view_name:
                return {"error": "View name is required for deletion."}
            if not await self._view_exists(db, view_name):
                return {"status": f"View '{view_name}' not found, no action taken."}

            success = await self.run_sync(db.delete_view, view_name, ignore_missing=False)
            return {"status": f"View '{view_name}' deleted successfully.", "success": success}

        else:
            return {"error": f"Unknown view operation: {operation}"}
