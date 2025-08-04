# fastapi_client_backend/main.py

# Standard imports for the FastAPI application
import json
import logging

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import client_settings
from .llm_orchestrator import orchestrator
from .mcp_client_setup import app_lifespan

# Configure the main application logger
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    main_handler = logging.StreamHandler()
    main_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    main_handler.setFormatter(main_formatter)
    logger.addHandler(main_handler)
    logger.setLevel(logging.INFO)


app = FastAPI(title="ArangoDB Chatbot API (MCP Client)", lifespan=app_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5000",
        "http://127.0.0.1:5000",
    ],  # Adjust as needed for client
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    user_id: str


class ChatResponse(BaseModel):
    response: str
    agent_type: str = "orchestrator"


class HistoryResponse(BaseModel):
    history: list


class StatusResponse(BaseModel):
    status: str


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, http_request: Request):
    logger.info(
        f"Received chat request for user_id '{req.user_id}': {req.message[:100]}..."
    )  # Log only a portion
    try:
        client_ip = http_request.client.host if http_request.client else "unknown"
        logger.debug(
            f"Request from IP: {client_ip}"
        )  # Changed to debug, less verbose for production

        assistant_response = await orchestrator.process_user_query(
            req.user_id, req.message
        )
        return ChatResponse(response=assistant_response)
    except ConnectionRefusedError:
        logger.error(
            f"Connection to MCP Server ({client_settings.mcp_server_url}) refused."
        )
        raise HTTPException(
            status_code=503,
            detail="MCP service unavailable. Please ensure the MCP server is running.",
        )
    except Exception as e:
        logger.exception(f"Error during chat processing for user_id '{req.user_id}':")
        raise HTTPException(
            status_code=500, detail=f"An internal error occurred: {str(e)}"
        )


@app.get("/api/history/{user_id}", response_model=HistoryResponse)
async def get_history(user_id: str):
    history = orchestrator.get_history(user_id)
    return HistoryResponse(history=history)


@app.post("/api/history/clear/{user_id}", response_model=StatusResponse)
async def clear_history(user_id: str):
    orchestrator.clear_history(user_id)
    return StatusResponse(status="cleared")


@app.get("/api/health", response_model=StatusResponse)
async def health():
    return StatusResponse(status="healthy")


def run_fastapi_client_backend_uvicorn():
    fastapi_port = getattr(client_settings, "fastapi_port", 8001)
    print(f"Starting FastAPI client backend on http://localhost:{fastapi_port}")

    uvicorn.run(
        "fastapi_client_backend.main:app",
        host="0.0.0.0",
        port=fastapi_port,
        reload=False,
    )


if __name__ == "__main__":
    run_fastapi_client_backend_uvicorn()
