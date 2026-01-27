"""
ArangoDB MCP Server

A Model Context Protocol server for ArangoDB that provides comprehensive database operations
including document management, graph operations, AQL query execution, and more.

This package exposes ArangoDB functionality to AI assistants and development tools through
the standardized MCP protocol.
"""

__version__ = "1.0.0"
__author__ = "ArangoDB MCP Team"

from .config import settings
from .server import app, mcp_app

__all__ = ["app", "mcp_app", "settings"]
