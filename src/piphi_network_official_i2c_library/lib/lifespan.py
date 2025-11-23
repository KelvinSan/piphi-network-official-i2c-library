from contextlib import asynccontextmanager
from fastapi import FastAPI

from piphi_network_official_i2c_library.lib.common import PiPhiMCP2221


mcp_service = PiPhiMCP2221()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await mcp_service.identify_all_mcp2221()
    devices = await mcp_service.build_discovery_results()
    print("discovered mcp2221 devices",devices)
    yield