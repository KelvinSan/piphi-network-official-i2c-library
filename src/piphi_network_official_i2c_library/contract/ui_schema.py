from fastapi import APIRouter


router = APIRouter(tags=["ui_schema"])


@router.get("/ui")
async def get_ui_schema():
    schema = {
        "title": "Official I2C Library Configuration",
        "description": "Configuration for Piphi Network Official I2C Library.",
        "type": "object",
        "required": ["sensor"],
        "properties": {
                "sensor": {
                    "type": "string",
                    "title": "Sensor Type",
                    "description": "Select a sensor type",
                    "enum": ["BME680", "BME688", "AHT20", "BME280"],
                    "errorMessage": "Please select a device before continuing"
            }
        },
    }

    return dict(schema=schema)
