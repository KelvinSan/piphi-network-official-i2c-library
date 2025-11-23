from typing import Optional
import EasyMCP2221
import serial.tools.list_ports
import bme680
import bme280

class PiPhiMCP2221:
    
    all_mcp2221s_dict = []
    
    mcp_mapping = {
        
        
    }
    
    def __init__(self):
        pass
    
    @staticmethod
    async def get_aht200_sensor(device: EasyMCP2221.Device):
        return device
    @staticmethod
    async def get_bme680_sensor(bus: EasyMCP2221.SMBus, port:str) -> Optional[bme680.BME680]:
        """
        Returns the BME680 sensor object connected to the given bus.

        Args:
            bus (EasyMCP2221.SMBus): The bus object to use for communication.

        Returns:
            Optional[bme680.BME680]: The BME680 sensor object, or None if the operation fails.
        """
        try:
            primary_address = bme680.constants.I2C_ADDR_PRIMARY
            PiPhiMCP2221.mcp_mapping[port]["active"] = True
            return bme680.BME680(i2c_addr=primary_address, i2c_device=bus)
        except (RuntimeError, IOError, EasyMCP2221.exceptions.NotAckError):
            try:
                secondary_address = bme680.constants.I2C_ADDR_SECONDARY
                PiPhiMCP2221.mcp_mapping[port]["active"] = True
                return bme680.BME680(i2c_addr=secondary_address, i2c_device=bus)
            except (RuntimeError, IOError, EasyMCP2221.exceptions.NotAckError) as error:
                raise error from None
            
    @staticmethod
    async def get_bme280_sensor(bus: EasyMCP2221.SMBus, port: str) -> Optional[bme280.BME280]:
        """
        Returns the BME280 sensor object connected to the given bus.

        Args:
            bus (EasyMCP2221.SMBus): The bus object to use for communication.

        Returns:
            Optional[bme280.BME280]: The BME280 sensor object, or None if the operation fails.
        """
        try:
            address = bme280.I2C_ADDRESS_VCC
            return bme280.BME280(i2c_addr=address, i2c_dev=bus)
        except (RuntimeError, IOError, EasyMCP2221.exceptions.NotAckError):
            try:
                address = bme280.I2C_ADDRESS_GND
                return bme280.BME280(i2c_addr=address, i2c_dev=bus)
            except (RuntimeError, IOError, EasyMCP2221.exceptions.NotAckError) as error:
                raise error from None
    
    async def identify_all_mcp2221(self):
        PiPhiMCP2221.all_mcp2221s_dict = [{"name": item.description, "usbpath": item.device,"serial": item.serial_number} for item in serial.tools.list_ports.comports() if "04D8:00DD" in item.hwid]
        return PiPhiMCP2221.all_mcp2221s_dict
    async def fetch_bme(self, bus: EasyMCP2221.SMBus) -> Optional[int]:
        """
        Fetches the chip ID of the BME sensor connected to the given bus.

        Args:
            bus (EasyMCP2221.SMBus): The bus object to use for communication.

        Returns:
            Optional[int]: The chip ID of the BME sensor, or None if the operation fails.
        """
        try:
            chip_id: int = bus.read_byte_data(0x77, 0xD0)
            return chip_id
        except EasyMCP2221.exceptions.NotAckError:
            return None
        except TimeoutError:
            return None
    async def fetch_aht(self, bus: EasyMCP2221.SMBus) -> Optional[int]:
        """
        Fetches the status of the AHT20 sensor connected to the given bus.

        Args:
            bus (EasyMCP2221.SMBus): The bus object to use for communication.

        Returns:
            Optional[int]: The status of the AHT20 sensor, or None if the operation fails.
        """
        try:
            status = bus.read_byte_data(0x38, 0x71)
            return status
        except EasyMCP2221.exceptions.NotAckError as error:
            return None
        except TimeoutError:
            return None
        
    async def read_pm_sensor_data(self, bus: EasyMCP2221.SMBus) -> Optional[bytes]:
        """
        Reads the data from the PM sensor connected to the given bus.

        Args:
            bus (EasyMCP2221.SMBus): The bus object to use for communication.

        Returns:
            Optional[bytes]: The data read from the PM sensor, or None if the operation fails.
        """
        try:
            register_address = 0x12
            data_length = 32
            pm_sensor_data = bus.read_i2c_block_data(register_address, 0x00, data_length)
            return pm_sensor_data
        except (EasyMCP2221.exceptions.NotAckError, TimeoutError):
            return None
    async def build_discovery_results(self):
        final_results = []
        for index,value in enumerate(PiPhiMCP2221.all_mcp2221s_dict):
            try:
                mcp = EasyMCP2221.Device(devnum=index)
                bus = EasyMCP2221.SMBus(mcp=mcp)
                """Checking for BMEx"""
                bme_chip_id = await self.fetch_bme(bus)
                if bme_chip_id == 97:
                    value['sensor'] = "BME68x"
                    value['mcp_usbserial'] = mcp.usbserial
                    PiPhiMCP2221.mcp_mapping[value["usbpath"]] = {
                        "mcp":mcp,
                        "bus":bus,
                        "chip_id":bme_chip_id,
                        "sensor":"BME68x",
                        "mcp_usbserial":mcp.usbserial,
                        "mcp_index":index,
                        "usbpath":value['usbpath'],
                        "active":False
                    }
                if bme_chip_id == 96:
                    value['sensor'] = "BME280"
                    value['mcp_usbserial'] = mcp.usbserial
                    PiPhiMCP2221.mcp_mapping[value["usbpath"]] = {
                        "mcp":mcp,
                        "bus":bus,
                        "chip_id":bme_chip_id,
                        "sensor":"BME68x",
                        "mcp_usbserial":mcp.usbserial,
                        "mcp_index":index,
                        "usbpath":value['usbpath'],
                        "active":False
                    }
                aht20_status = await self.fetch_aht(bus)
                if aht20_status is not None:
                    value['sensor'] = "AHT20"
                    value['mcp_usbserial'] = mcp.usbserial
                    PiPhiMCP2221.mcp_mapping[value["usbpath"]] = {
                        "mcp":mcp,
                        "bus":bus,
                        "status":aht20_status,
                        "sensor":"AHT20",
                        "mcp_usbserial":mcp.usbserial,
                        "mcp_index":index,
                        "usbpath":value['usbpath'],
                        "active":False
                    }
                pmsa003i_data = await self.read_pm_sensor_data(bus)
                if pmsa003i_data is not None:
                    if len(pmsa003i_data) == 32 and pmsa003i_data[0] == 0x42 and pmsa003i_data[1] == 0x4D:
                        
                        value['sensor'] = "PMSA003I"
                        value['mcp_usbserial'] = mcp.usbserial
                        PiPhiMCP2221.mcp_mapping[value["usbpath"]] = {
                            "mcp":mcp,
                            "bus":bus,
                            "data":pmsa003i_data,
                            "sensor":"PMSA003I",
                            "mcp_usbserial":mcp.usbserial,
                            "mcp_index":index,
                            "usbpath":value['usbpath'],
                            "active":False
                        }
                        final_results.append(value)
            except EasyMCP2221.exceptions.NotAckError as error:
                pass
        return final_results