# fastapi_client_backend/llm_orchestrator.py
import json
import logging
from typing import Any, Dict, List

from langchain_core.messages import (AIMessage, BaseMessage, HumanMessage,
                                     ToolMessage)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from mcp import types as mcp_types

from .config import client_settings
from .mcp_client_setup import mcp_client_manager

logger = logging.getLogger(__name__)


class LLMOrchestrator:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=client_settings.llm_model_name,
            google_api_key=client_settings.gemini_api_key,
            convert_system_message_to_human=True,
        )
        self.conversation_history: Dict[str, List[BaseMessage]] = {}

    def _mcp_schema_to_gemini_parameters(
        self, mcp_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Converts an MCP inputSchema (JSON Schema) to Gemini's expected parameter schema.
        This is a simplified converter; a full JSON Schema to Gemini Function Declaration
        converter would be more complex.
        """
        if not mcp_schema or "properties" not in mcp_schema:
            return {
                "type": "OBJECT",
                "properties": {},
            }  # Gemini uses OBJECT for dictionary types

        gemini_props = {}
        for prop_name, prop_schema in mcp_schema.get("properties", {}).items():
            gemini_type = "STRING"  # Default
            mcp_type = prop_schema.get("type")
            description = prop_schema.get("description", f"Parameter {prop_name}")
            is_nullable = prop_schema.get("nullable", False)  # Check for nullable

            if mcp_type == "string":
                gemini_type = "STRING"
            elif mcp_type == "integer" or mcp_type == "number":
                gemini_type = "NUMBER"
            elif mcp_type == "boolean":
                gemini_type = "BOOLEAN"
            elif mcp_type == "array":
                gemini_type = "ARRAY"
                if (
                    "items" in prop_schema
                    and prop_schema["items"].get("type") == "object"
                ):
                    pass
                elif "items" in prop_schema:
                    pass
            elif mcp_type == "object":
                gemini_type = "OBJECT"

            gemini_props[prop_name.replace("-", "_")] = {
                "type": gemini_type,
                "description": description,
            }
            if is_nullable:
                gemini_props[prop_name.replace("-", "_")]["nullable"] = True

        return {
            "type": "OBJECT",
            "properties": gemini_props,
            "required": [
                req.replace("-", "_") for req in mcp_schema.get("required", [])
            ],
        }

    def _format_mcp_tools_for_llm(
        self, mcp_tools: List[mcp_types.Tool]
    ) -> List[Dict[str, Any]]:
        """Converts MCP Tool definitions to a format Gemini function calling can use."""
        formatted_tools = []
        for tool in mcp_tools:
            gemini_parameters = self._mcp_schema_to_gemini_parameters(tool.inputSchema)

            formatted_tools.append(
                {
                    "name": tool.name.replace("-", "_"),
                    "description": tool.description or "No description available.",
                    "parameters": gemini_parameters,
                }
            )
        # logger.debug(f"Formatted tools for LLM: {json.dumps(formatted_tools, indent=2)}") # Can be noisy
        return formatted_tools

    async def process_user_query(self, user_id: str, query: str) -> str:
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []

        current_human_message = HumanMessage(content=query)

        turn_messages: List[BaseMessage] = list(self.conversation_history[user_id])
        turn_messages.append(current_human_message)

        async with mcp_client_manager.get_session() as mcp_session:
            mcp_tools_list = (await mcp_session.list_tools()).tools
            llm_formatted_tools = self._format_mcp_tools_for_llm(mcp_tools_list)

            llm_with_tools = self.llm
            if llm_formatted_tools:
                llm_with_tools = self.llm.bind_tools(llm_formatted_tools)
            else:
                logger.warning(
                    "No MCP tools found or formatted for LLM. Proceeding without tool binding."
                )

            system_prompt_content = (
                "You are a helpful assistant that can interact with an ArangoDB database using the provided tools. "
                "Your primary directive is to **ALWAYS prioritize using a tool to answer any question about the current state of the database**, even if the question seems simple. "
                "Do not rely on your own knowledge for information like listing databases, collections, or documents. Always use a tool to get live, real-time data. "
                "Carefully choose the correct tool and formulate its arguments based on the user's query. "
                "When a tool requires a JSON object for an argument (like 'document_data' or 'filters' or 'properties'), "
                "ensure you provide a well-formed JSON object directly as the argument value, not a string containing JSON. "
                "After a tool is executed, use its output to answer the user's question clearly and in a well-structured format. "
                "Default database is usually _system unless specified otherwise in a tool's arguments or by the user. "
                "The 'list-collections' tool will show user-defined collections; for system collections, an AQL query might be needed. "
                "If a tool call results in an error, explain the error to the user clearly and ask if they want to try something else. "
                "Do not attempt to re-call a tool that previously errored unless the user provides new information or clarifies the request.\n\n"
                "Output Formatting Guidelines for Better User Experience:\n"
                "- Use proper Markdown formatting for better readability:\n"
                "  - Use **bold** for important terms, names, and emphasis.\n"
                "  - Use `inline code` (backticks) for database names, collection names, document keys, field names, and analyzer names (e.g., `_system::my_analyzer`).\n"
                "  - Use ```json code blocks``` for JSON data, query results, and structured output.\n"
                "  - Use ```aql code blocks``` for AQL queries.\n"
                "  - Use > blockquotes for important notes or warnings.\n"
                "  - Use --- for horizontal dividers when separating sections.\n"
                "- When listing items (databases, collections, documents, analyzers, etc.):\n"
                "  - Use bullet points (`*`) or numbered lists (`1.`) with proper formatting.\n"
                "  - Present names like database names, collection names, or analyzer names (e.g., `_system::text_en`) **exactly as provided by the tool's output data**, typically enclosed in backticks for `inline code` formatting (e.g., `_system::custom_analyzer_name`). Do **not** add any prefixes like `/` or other characters to these names unless they are part of the actual name data from the tool.\n"
                "  - Example for collections: `* **my_collection** (document collection) - 150 documents`\n"
                "  - Example for analyzers: `* \`_system::text_en\` (Type: text)` or `1. \`identity\` (Type: identity)`\n"
                "  - Group related items under subheadings with **bold headers** if appropriate.\n"
                "- When displaying query results or data:\n"
                "  - Always use proper JSON code blocks with syntax highlighting.\n"
                "  - Add context before the code block: 'Here are the results:'\n"
                "  - Summarize key findings after showing the data.\n"
                "  - For large datasets, show first few items and mention total count.\n"
                "- When operations succeed:\n"
                "  - Start with a clear success message: ' **Successfully created** database `my_db`'.\n"
                "  - Provide relevant details in a structured format.\n"
                "  - Offer next steps or related actions when appropriate.\n"
                "- When errors occur:\n"
                "  - Start with clear error indication: ' **Error occurred**'.\n"
                "  - Explain the issue in simple terms.\n"
                "  - Suggest solutions or alternatives.\n"
                "  - Use blockquotes for important error details.\n"
                "- For complex operations:\n"
                "  - Break down the response into clear sections.\n"
                "  - Use numbered steps for procedures.\n"
                "  - Provide examples when helpful.\n"
                "  - End with a summary of what was accomplished.\n"
                "Always prioritize clarity, proper formatting, and user-friendly presentation. "
                "Make your responses visually appealing and easy to scan, similar to modern chat interfaces."
            )

            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", system_prompt_content),
                    MessagesPlaceholder(variable_name="chat_history"),
                ]
            )

            chain = prompt | llm_with_tools

            max_tool_iterations = 5
            current_iteration = 0
            final_bot_response_content = (
                "I'm sorry, I encountered an issue and couldn't complete your request."
            )

            while current_iteration < max_tool_iterations:
                current_iteration += 1
                # logger.debug(f"LLM Interaction Loop: Iteration {current_iteration} for user '{user_id}'. Current turn_messages count: {len(turn_messages)}")
                # turn_messages_summary = [f"{m.type}: {(str(m.content)[:70] if m.content else '[None]')}" + (f" (TCs: {len(m.tool_calls)})" if isinstance(m, AIMessage) and m.tool_calls else "") for m in turn_messages]
                # logger.debug(f"Invoking LLM (Iter {current_iteration}) with turn_messages: {turn_messages_summary}")

                ai_response: AIMessage = await chain.ainvoke(
                    {"chat_history": turn_messages}
                )
                # logger.debug(f"LLM response (Iter {current_iteration}) for user '{user_id}': AIMessage(id='{ai_response.id}', content='{(ai_response.content or '')[:100]}...', tool_calls={ai_response.tool_calls})")
                turn_messages.append(ai_response)

                if ai_response.tool_calls:
                    tool_results_messages: List[ToolMessage] = []
                    any_tool_arg_errors_this_step = False

                    for tool_call in ai_response.tool_calls:
                        tool_name_llm = tool_call["name"]
                        tool_name_mcp = tool_name_llm.replace("_", "-")
                        tool_args = tool_call["args"]
                        tool_call_id = tool_call.get("id")

                        current_tool_arg_error = False

                        for arg_name in [
                            "document_data",
                            "documents_data",
                            "filters",
                            "properties",
                            "index_definition",
                            "edge_definitions",
                            "edge_data",
                            "bind_vars",
                        ]:
                            if arg_name in tool_args and isinstance(
                                tool_args[arg_name], str
                            ):
                                try:
                                    parsed_value = json.loads(tool_args[arg_name])
                                    if arg_name == "documents_data" and not isinstance(
                                        parsed_value, list
                                    ):
                                        logger.warning(
                                            f"LLM provided {arg_name} as a string for {tool_name_mcp}, but it didn't parse to a list: {tool_args[arg_name]}"
                                        )
                                        error_content = f"Tool Argument Error: For tool '{tool_name_mcp}', the argument '{arg_name}' was expected to be a list of objects, but I received a string that did not parse into a list. Please ensure it's a list of JSON objects."
                                        tool_results_messages.append(
                                            ToolMessage(
                                                content=error_content,
                                                tool_call_id=(
                                                    tool_call_id
                                                    if tool_call_id
                                                    else f"error_no_id_{tool_name_llm}_{arg_name}"
                                                ),
                                            )
                                        )
                                        any_tool_arg_errors_this_step = True
                                        current_tool_arg_error = True
                                        break  # Stop processing args for this tool call
                                    tool_args[arg_name] = parsed_value
                                    logger.info(
                                        f"Successfully parsed stringified '{arg_name}' for {tool_name_mcp}"
                                    )
                                except json.JSONDecodeError:
                                    logger.warning(
                                        f"Argument '{arg_name}' for {tool_name_mcp} is a string but not valid JSON: {tool_args[arg_name]}"
                                    )
                                    error_content = f"Tool Argument Error: For tool '{tool_name_mcp}', the argument '{arg_name}' was provided as a string '{tool_args[arg_name][:100]}...' which is not valid JSON. Please provide a valid JSON object or list as required by the tool."
                                    tool_results_messages.append(
                                        ToolMessage(
                                            content=error_content,
                                            tool_call_id=(
                                                tool_call_id
                                                if tool_call_id
                                                else f"error_no_id_{tool_name_llm}_{arg_name}"
                                            ),
                                        )
                                    )
                                    any_tool_arg_errors_this_step = True
                                    current_tool_arg_error = True
                                    break  # Stop processing args for this tool call

                        if current_tool_arg_error:
                            continue  # Move to the next tool_call in ai_response.tool_calls

                        if not tool_call_id:
                            logger.error(
                                f"Tool call for '{tool_name_llm}' from LLM is missing an 'id'. Tool call: {tool_call}"
                            )
                            error_content = f"Internal Error: Tool call for '{tool_name_llm}' was missing its required ID from the LLM response. Cannot proceed with this tool."
                            tool_results_messages.append(
                                ToolMessage(
                                    content=error_content,
                                    tool_call_id=f"error_missing_id_{tool_name_llm}_{len(tool_results_messages)}",
                                )
                            )
                            any_tool_arg_errors_this_step = True  # Treat missing ID as a critical argument issue for this step
                            continue

                        logger.info(
                            f"Executing MCP Tool: {tool_name_mcp} with processed args: {json.dumps(tool_args, indent=2, default=str)[:500]}..., AI-generated call_id: {tool_call_id}"
                        )

                        try:
                            mcp_tool_result_raw = await mcp_session.call_tool(
                                tool_name_mcp, tool_args
                            )
                            result_str_parts = (
                                [
                                    item.text
                                    for item in mcp_tool_result_raw.content
                                    if item.type == "text"
                                ]
                                if mcp_tool_result_raw.content
                                else []
                            )
                            raw_tool_output = (
                                "\n".join(result_str_parts)
                                if result_str_parts
                                else "Tool executed successfully and returned no textual output."
                            )

                            mcp_tool_result_for_llm = raw_tool_output
                            try:
                                parsed_agent_output = json.loads(raw_tool_output)
                                mcp_tool_result_for_llm = json.dumps(
                                    parsed_agent_output
                                )  # Keep it compact for LLM

                            except json.JSONDecodeError:
                                pass

                            if mcp_tool_result_raw.isError:
                                mcp_tool_result_for_llm = f"Tool Error ({tool_name_mcp}): {mcp_tool_result_for_llm}"
                                logger.warning(
                                    f"MCP Tool '{tool_name_mcp}' execution resulted in error: {mcp_tool_result_for_llm[:500]}"
                                )
                            else:
                                logger.info(
                                    f"MCP Tool '{tool_name_mcp}' execution successful. Result for LLM: {mcp_tool_result_for_llm[:200]}..."
                                )

                            tool_results_messages.append(
                                ToolMessage(
                                    content=mcp_tool_result_for_llm,
                                    tool_call_id=tool_call_id,
                                )
                            )
                        except Exception as e:
                            error_content_dict = {
                                "critical_error_summary": f"Unhandled exception calling MCP tool '{tool_name_mcp}'",
                                "details": str(e),
                            }
                            error_msg_for_llm = json.dumps(error_content_dict)
                            logger.exception(
                                f"Exception during MCP tool call for {tool_name_mcp}:"
                            )
                            tool_results_messages.append(
                                ToolMessage(
                                    content=error_msg_for_llm, tool_call_id=tool_call_id
                                )
                            )

                    # If there were tool calls but all resulted in argument errors before execution,
                    # we still need to add these error messages to turn_messages to inform the LLM.
                    if (
                        tool_results_messages
                    ):  # Add any generated tool messages (success or error)
                        turn_messages.extend(tool_results_messages)
                    elif ai_response.tool_calls and not tool_results_messages:
                        # This case means tool_calls were present, but no ToolMessage (even errors) got generated.
                        # This might happen if all tool_calls had missing IDs and loop continued without adding.
                        logger.error(
                            "ai_response had tool_calls but no tool_results_messages were generated (e.g. all missing IDs). Breaking loop."
                        )
                        final_bot_response_content = "I encountered an issue with the tool requests and couldn't process them."
                        break

                    # If there were any argument errors in this step, we don't break the main loop immediately.
                    # Instead, we let the LLM see the error messages and decide if it can recover or needs to stop.
                    # The main loop continues to the next iteration.

                else:  # No tool_calls in ai_response, LLM provides final answer
                    final_bot_response_content = (
                        ai_response.content
                        if ai_response.content is not None
                        else "The operation was processed, but I don't have a further textual response."
                    )
                    break  # Exit main processing loop

            else:  # Loop finished due to max_tool_iterations
                logger.warning(
                    f"Reached max_tool_iterations ({max_tool_iterations}) for user '{user_id}' query '{query}'."
                )
                last_ai_msg_in_loop = (
                    turn_messages[-1]
                    if turn_messages and isinstance(turn_messages[-1], AIMessage)
                    else None
                )
                if (
                    last_ai_msg_in_loop
                    and last_ai_msg_in_loop.content
                    and not last_ai_msg_in_loop.tool_calls
                ):  # if last msg has content and no more tool calls
                    final_bot_response_content = last_ai_msg_in_loop.content
                elif last_ai_msg_in_loop and last_ai_msg_in_loop.tool_calls:
                    final_bot_response_content = "I tried multiple steps but seem to be stuck in a tool loop. Could you please rephrase your request?"
                else:
                    final_bot_response_content = "I tried multiple steps but couldn't finalize your request. Please try rephrasing or simplifying your query."

            self.conversation_history[user_id] = turn_messages
            self.conversation_history[user_id] = self.conversation_history[user_id][
                -20:
            ]

            logger.info(
                f"Final answer for user_id '{user_id}': {final_bot_response_content[:200]}..."
            )
            return final_bot_response_content

    def get_history(self, user_id: str) -> List[Dict[str, str]]:
        history_dicts = []
        for msg_obj in self.conversation_history.get(user_id, []):
            entry = {"role": msg_obj.type, "content": ""}

            current_content_for_display = ""
            if isinstance(msg_obj.content, str):
                current_content_for_display = msg_obj.content
            elif msg_obj.content is None:
                if isinstance(msg_obj, AIMessage) and msg_obj.tool_calls:
                    try:
                        tool_call_data = []
                        for idx, tc in enumerate(msg_obj.tool_calls):
                            if isinstance(tc, dict):
                                tool_call_data.append(
                                    {
                                        "name": tc.get("name"),
                                        "args": tc.get("args"),
                                        "id": tc.get("id", f"tc_{idx}"),
                                    }
                                )
                            else:
                                tool_call_data.append(str(tc))
                        current_content_for_display = json.dumps(tool_call_data)
                        entry["is_tool_call_data"] = True
                    except Exception as e:
                        logger.warning(
                            f"Could not serialize tool_calls for history display: {e}"
                        )
                        current_content_for_display = (
                            "[Tool call information - serialization error]"
                        )
                else:
                    current_content_for_display = "[No content provided]"
            elif isinstance(msg_obj.content, list) and not msg_obj.content:
                current_content_for_display = "[Received empty list as content]"
            else:
                try:
                    current_content_for_display = str(msg_obj.content)
                except:
                    current_content_for_display = "[Unserializable content]"

            entry["content"] = current_content_for_display

            if isinstance(msg_obj, ToolMessage):
                entry["tool_call_id"] = msg_obj.tool_call_id

            history_dicts.append(entry)
        return history_dicts

    def clear_history(self, user_id: str):
        if user_id in self.conversation_history:
            self.conversation_history[user_id] = []
        logger.info(f"History cleared for user_id '{user_id}'.")
        return True


orchestrator = LLMOrchestrator()
