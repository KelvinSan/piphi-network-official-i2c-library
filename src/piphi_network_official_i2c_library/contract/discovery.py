

from fastapi import APIRouter

from piphi_network_official_i2c_library.lib.common import PiPhiMCP2221

discovery_router = APIRouter(tags=["discovery"])

mcp_service = PiPhiMCP2221()

@discovery_router.get("/discovery")
async def discovery():
    await mcp_service.identify_all_mcp2221()
    devices = await mcp_service.build_discovery_results()
    return {
        "devices": devices
    }