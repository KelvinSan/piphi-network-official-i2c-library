import asyncio
import datetime
import hashlib
import hmac
import json
import math
import os
import sys
from typing import Dict, List
import aiomqtt
import bme680
from fastapi import APIRouter, HTTPException
from bme680 import BME680
from piphi_network_official_i2c_library.contract.schema import I2cSensorsSchema
from piphi_network_official_i2c_library.lib.common import PiPhiMCP2221

if sys.platform.lower() == "win32" or os.name.lower() == "nt":
    from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy

    set_event_loop_policy(WindowsSelectorEventLoopPolicy())

router = APIRouter(tags=["config"])

device_store = {}

polling: Dict[str, asyncio.Task] = {}


def sign_payload(payload: dict, secret: str):
    data = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hmac.new(
        secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha256
    ).hexdigest()


async def calculate_dew_pt(sensor: BME680):
    """
    Calculate dew point using the BME680's temperature and humidity readings.
    This function uses a more efficient algorithm to reduce the number of operations.
    """
    a = 17.625
    b = 243.04
    t = sensor.data.temperature
    h = sensor.data.humidity / 100
    x = math.log(h) + (a * t) / (b + t)
    dew_pt = (b * x) / (a - x)
    return dew_pt


async def set_sensor(usbpath: str):
    print(PiPhiMCP2221.mcp_mapping[usbpath])
    if (
        PiPhiMCP2221.mcp_mapping[usbpath]["active"] == False
        and PiPhiMCP2221.mcp_mapping[usbpath]["sensor"] == "BME68x"
    ):
        bme = await PiPhiMCP2221.get_bme680_sensor(
            PiPhiMCP2221.mcp_mapping[usbpath]["bus"], usbpath
        )
        return {"bme68x": bme}
    if (
        PiPhiMCP2221.mcp_mapping[usbpath]["active"] == False
        and PiPhiMCP2221.mcp_mapping[usbpath]["sensor"] == "BME280"
    ):
        bme = await PiPhiMCP2221.get_bme280_sensor(
            PiPhiMCP2221.mcp_mapping[usbpath]["bus"], usbpath
        )
        if bme is not None:
            PiPhiMCP2221.mcp_mapping[usbpath]["active"] = True
        return {"bme280": bme}
    if (
        PiPhiMCP2221.mcp_mapping[usbpath]["active"] == False
        and PiPhiMCP2221.mcp_mapping[usbpath]["sensor"] == "AHT20"
    ):
        return {"aht20": PiPhiMCP2221.mcp_mapping[usbpath]["mcp"]}
    if (
        PiPhiMCP2221.mcp_mapping[usbpath]["active"] == False
        and PiPhiMCP2221.mcp_mapping[usbpath]["sensor"] == "PMSA003I"
    ):
        return {"pmsa003i": PiPhiMCP2221.mcp_mapping[usbpath]["bus"]}


async def poll_sensor(sensor_dict: dict, container_id: str, signature: str):
    data = {}
    data["x-container-id"] = container_id
    data["x-piphi-signature"] = signature
    if "bme68x" in sensor_dict:
        sensor_dict["bme68x"].set_humidity_oversample(bme680.constants.OS_2X)
        sensor_dict["bme68x"].set_pressure_oversample(bme680.constants.OS_4X)
        sensor_dict["bme68x"].set_temperature_oversample(bme680.constants.OS_8X)
        sensor_dict["bme68x"].set_filter(bme680.constants.FILTER_SIZE_3)
        sensor_dict["bme68x"].set_gas_status(bme680.constants.ENABLE_GAS_MEAS)
        sensor_dict["bme68x"].set_gas_heater_temperature(320)
        sensor_dict["bme68x"].set_gas_heater_duration(150)
        sensor_dict["bme68x"].select_gas_heater_profile(0)
        while True:
            data["metrics"]["temperature"] = round(sensor_dict["bme68x"].data.temperature)
            data["metrics"]["pressure"] = round(sensor_dict["bme68x"].data.pressure)
            data["metrics"]["humidity"] = round(sensor_dict["bme68x"].data.humidity)
            data["metrics"]["gas"] = round(sensor_dict["bme68x"].data.gas_resistance)
            data["metrics"]["dew_pt"] = round(await calculate_dew_pt(sensor_dict["bme68x"]))
            data["device_id"] = device_store.get("id")
            data["timestamp"] = datetime.datetime.now().isoformat()
            data["units"] = {
                "temperature": "C",
                "pressure": "hPa",
                "humidity": "%",
                "gas": "ohm",
                "dew_pt": "C",
            }
            async with aiomqtt.Client("localhost") as client:
                await client.publish(
                    "piphi/telemetry", json.dumps(data), qos=1, retain=True
                )
            await asyncio.sleep(10)
    if "bme280" in sensor_dict:
        while True:
            data["metrics"]["temperature"] = sensor_dict["bme280"].get_temperature()
            data["metrics"]["pressure"] = sensor_dict["bme280"].get_pressure()
            data["metrics"]["humidity"] = sensor_dict["bme280"].get_humidity()
            data["device_id"] = device_store.get("id")
            data["timestamp"] = datetime.datetime.now().isoformat()
            data["units"] = {"temperature": "C", "pressure": "hPa", "humidity": "%"}
            async with aiomqtt.Client("localhost") as client:
                await client.publish(
                    "piphi/telemetry", json.dumps(data), qos=1, retain=True
                )
            await asyncio.sleep(10)
    if "aht20" in sensor_dict:
        while True:
            sensor_dict["aht20"].I2C_write(0x38, [0xAC, 0x33, 0x00])
            await asyncio.sleep(10)
            mcp_data = sensor_dict["aht20"].I2C_read(0x38, 7)
            if mcp_data[0] & 0x80 == 0:
                humidity_raw = (
                    (mcp_data[1] << 12) | (mcp_data[2] << 4) | (mcp_data[3] >> 4)
                )
                humidity = (humidity_raw / 1048576.0) * 100
                temp_raw = (
                    ((mcp_data[3] & 0x0F) << 16) | (mcp_data[4] << 8) | mcp_data[5]
                )
                temperature = (temp_raw / 1048576.0) * 200 - 50
                data["metrics"]["temperature"] = round(temperature)
                data["metrics"]["humidity"] = round(humidity)
                data["device_id"] = device_store.get("id")
                data["timestamp"] = datetime.datetime.now().isoformat()
                data["units"] = {"temperature": "C", "humidity": "%"}
                async with aiomqtt.Client("localhost") as client:
                    await client.publish(
                        "piphi/telemetry", json.dumps(data), qos=1, retain=True
                    )
            await asyncio.sleep(10)
    if "pmsa003i" in sensor_dict:
        while True:
            pdata = sensor_dict["pmsa003i"].read_i2c_block_data(0x12, 0x00, 32)
            if len(pdata) != 32 or pdata[0] != 0x42 or pdata[1] != 0x4D:
                print("Invalid header or length")
            checksum = sum(pdata[:30]) & 0xFFFF
            received_checksum = (pdata[30] << 8) | pdata[31]
            if checksum != received_checksum:
                print(
                    f"Checksum mismatch: calculated {checksum:04X}, received {received_checksum:04X}"
                )
            pm1_0_standard = (pdata[4] << 8) | pdata[5]
            pm2_5_standard = (pdata[6] << 8) | pdata[7]
            pm10_standard = (pdata[8] << 8) | pdata[9]
            pm1_0_env = (pdata[10] << 8) | pdata[11]
            pm2_5_env = (pdata[12] << 8) | pdata[13]
            pm10_env = (pdata[14] << 8) | pdata[15]
            particles_03um = (pdata[16] << 8) | pdata[17]
            particles_05um = (pdata[18] << 8) | pdata[19]
            particles_10um = (pdata[20] << 8) | pdata[21]
            particles_25um = (pdata[22] << 8) | pdata[23]
            particles_50um = (pdata[24] << 8) | pdata[25]
            particles_100um = (pdata[26] << 8) | pdata[27]

            aqdata ={
                "pm10_standard": pm1_0_standard,
                "pm25_standard": pm2_5_standard,
                "pm100_standard": pm10_standard,
                "pm10_env": pm1_0_env,
                "pm25_env": pm2_5_env,
                "pm100_env": pm10_env,
                "particles_03um": particles_03um,
                "particles_05um": particles_05um,
                "particles_10um": particles_10um,
                "particles_25um": particles_25um,
                "particles_50um": particles_50um,
                "particles_100um": particles_100um,
            }
            if aqdata:
                print("\nConcentration Units (standard)")
                print("---------------------------------------")
                print(
                    f"PM 1.0: {aqdata['pm10_standard']}\tPM2.5: {aqdata['pm25_standard']}\tPM10: {aqdata['pm100_standard']}"
                )
                print("Concentration Units (environmental)")
                print("---------------------------------------")
                print(
                    f"PM 1.0: {aqdata['pm10_env']}\tPM2.5: {aqdata['pm25_env']}\tPM10: {aqdata['pm100_env']}"
                )
                print("---------------------------------------")
                print(f"Particles > 0.3um / 0.1L air: {aqdata['particles_03um']}")
                print(f"Particles > 0.5um / 0.1L air: {aqdata['particles_05um']}")
                print(f"Particles > 1.0um / 0.1L air: {aqdata['particles_10um']}")
                print(f"Particles > 2.5um / 0.1L air: {aqdata['particles_25um']}")
                print(f"Particles > 5.0um / 0.1L air: {aqdata['particles_50um']}")
                print(f"Particles > 10 um / 0.1L air: {aqdata['particles_100um']}")
                print("---------------------------------------")
                data["metrics"] = aqdata
                data["device_id"] = device_store.get("id")
                data["timestamp"] = datetime.datetime.now().isoformat()
                data["units"] = {
                    "pm10_standard": "ug/m3",
                    "pm25_standard": "ug/m3",
                    "pm100_standard": "ug/m3",
                    "pm10_env": "ug/m3",
                    "pm25_env": "ug/m3",
                    "pm100_env": "ug/m3",
                    "particles_03um": "#/0.1L air",
                    "particles_05um": "#/0.1L air",
                    "particles_10um": "#/0.1L air",
                    "particles_25um": "#/0.1L air",
                    "particles_50um": "#/0.1L air",
                    "particles_100um": "#/0.1L air",
                }
                async with aiomqtt.Client("localhost") as client:
                    await client.publish(
                        "piphi/telemetry", json.dumps(data), qos=1, retain=True
                    )
            else:
                print("Unable to read from sensor, retrying...")
            await asyncio.sleep(60)


@router.post("/config")
async def set_config(payload: I2cSensorsSchema):
    device_store.update(payload)
    existing_poll = polling.get(payload.id)
    if existing_poll and not existing_poll.done():
        polling[payload.id].cancel()
        try:
            await existing_poll
        except asyncio.CancelledError:
            pass
    signature = sign_payload(payload.model_dump(), device_store.get("secret"))
    sensor = await set_sensor(payload.usbpath)
    if sensor is not None:
        task = asyncio.create_task(
            poll_sensor(
                sensor,
                signature=signature,
                container_id=device_store.get("container_id"),
            )
        )
        polling[payload.id] = task
    else:
        raise HTTPException(status_code=404, detail="Sensor not supported")
    return
