import json
import multiprocessing
from pathlib import Path
from fastapi import FastAPI
import uvicorn
import aiofiles
from piphi_network_official_i2c_library.contract.discovery import discovery_router
from piphi_network_official_i2c_library.lib.lifespan import lifespan
from piphi_network_official_i2c_library.contract.config import router as config_router
app = FastAPI(lifespan=lifespan)


app.include_router(discovery_router)
app.include_router(router=config_router)


@app.get("/manifest.json")
async def display_manifest():
    """This endpoint returns the manifest.json file which contains the information about the official piphi i2c library."""
    path = Path(__file__).parent.parent / "manifest.json"
    async with aiofiles.open(path) as f:
        return json.loads(await f.read())


if __name__ == "__main__":
    multiprocessing.freeze_support()
    uvicorn.run("piphi:app", host="0.0.0.0", port=3669, reload=True)