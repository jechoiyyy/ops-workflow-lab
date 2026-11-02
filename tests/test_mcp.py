import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ops_workflow_lab.store import Store


def test_stdio_protocol_and_approval_boundary(tmp_path):
    path = str(tmp_path / "mcp.db")

    async def exercise():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "ops_workflow_lab.mcp_server"],
            env={**os.environ, "OPS_LAB_DB": path},
        )
        async with stdio_client(parameters) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {tool.name for tool in tools.tools} == {
                "list_demo_targets",
                "propose_workflow",
                "get_workflow",
                "get_workflow_events",
            }
            result = await session.call_tool(
                "propose_workflow",
                {
                    "goal": "Back up atlas-api",
                    "request_key": "mcp-request-001",
                },
            )
            assert not result.isError
            data = json.loads(result.content[0].text)
            assert data["status"] == "awaiting_approval"
            bad = await session.call_tool(
                "propose_workflow",
                {
                    "goal": "Delete everything",
                    "request_key": "mcp-request-002",
                },
            )
            assert bad.isError
            return data["id"]

    run_id = asyncio.run(exercise())
    run = Store(path).get(run_id)
    assert all(s["attempts"] == 0 for s in run["steps"])
