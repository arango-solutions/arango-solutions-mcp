"""Generate PyInstaller spec file for ArangoDB MCP Server."""

from pathlib import Path


def generate_spec():
    """Generate PyInstaller spec file from pyproject.toml."""

    # Generate spec content
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("manuals", "manuals"),
    ],
    hiddenimports=[
        "arango",
        "arango.client",
        "arango.database",
        "arango.exceptions",
        "mcp",
        "mcp.server",
        "mcp.server.fastmcp",
        "fastmcp",
        "pydantic",
        "pydantic_settings",
        "pydantic.fields",
        "pydantic.main",
        "pydantic_core",
        "anyio",
        "anyio._backends",
        "anyio._backends._asyncio",
        "importlib_metadata",
        "agents",
        "agents.agent_base",
        "agents.analyzer_management_agent",
        "agents.aql_execution_agent",
        "agents.collection_management_agent",
        "agents.database_management_agent",
        "agents.document_crud_agent",
        "agents.graph_management_agent",
        "agents.index_management_agent",
        "agents.manual_management_agent",
        "agents.view_management_agent",
        "mcp_tools",
        "mcp_tools.analyzer_tools",
        "mcp_tools.aql_tools",
        "mcp_tools.collection_tools",
        "mcp_tools.database_tools",
        "mcp_tools.document_tools",
        "mcp_tools.graph_tools",
        "mcp_tools.index_tools",
        "mcp_tools.manual_tools",
        "mcp_tools.view_tools",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="arangodb_mcp_server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"""

    # Write spec file
    spec_file = Path("arangodb_mcp_server.spec")
    spec_file.write_text(spec_content)

    print(f"Generated {spec_file}")
    return spec_file


if __name__ == "__main__":
    generate_spec()

