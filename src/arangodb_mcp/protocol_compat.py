"""Temporary protocol-version bridge for the official MCP Python SDK.

The upstream 1.29 SDK implements the required stateless HTTP primitives but
still advertises 2025-11-25. The 2026-07-28 wire revision is additive for the
request/response shapes this server uses, so this bridge enables negotiation
while the ASGI boundary enforces the new transport requirements. Remove this
module once the SDK natively advertises 2026-07-28 or later.
"""

from __future__ import annotations

import mcp.shared.version
import mcp.types

MCP_2026_VERSION = "2026-07-28"
SDK_NATIVE_LATEST_VERSION = mcp.types.LATEST_PROTOCOL_VERSION
COMPATIBILITY_SUNSET = "2027-02-01"


def enable_mcp_2026_negotiation() -> bool:
    """Enable 2026 negotiation, returning whether the bridge was necessary."""
    supported = mcp.shared.version.SUPPORTED_PROTOCOL_VERSIONS
    bridge_required = MCP_2026_VERSION not in supported
    if bridge_required:
        supported.append(MCP_2026_VERSION)
    mcp.shared.version.LATEST_PROTOCOL_VERSION = MCP_2026_VERSION
    mcp.types.LATEST_PROTOCOL_VERSION = MCP_2026_VERSION
    return bridge_required
