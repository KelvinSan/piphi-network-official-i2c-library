from pydantic import BaseModel, ConfigDict


class I2cSensorsSchema(BaseModel):
    model_config = ConfigDict(
        extra='allow')
    usbpath: str
