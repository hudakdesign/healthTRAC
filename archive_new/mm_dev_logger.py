#!/usr/bin/env python3
"""
HealthTRAC - Configure MetaMotion for Autonomous Logging V2

This script correctly prepares the MetaMotion to act as a standalone
data logger by enabling the sensor and starting the logger without
also starting a BLE data stream.
"""
import asyncio
import sys
from bleak import BleakClient
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('LogConfigV2')
DEFAULT_MAC = "c8:0b:fb:24:c1:65"
COMMAND_UUID = "326a9001-85cb-9195-d9dd-464cfbbae75a"

async def configure_logging_mode(mac_address):
    logger.info(f"Connecting to {mac_address} to configure for autonomous logging...")
    try:
        async with BleakClient(mac_address, timeout=20.0) as client:
            logger.info("✅ Connected! Configuring logger...")

            logger.info("1. Stopping all previous activities...")
            await client.write_gatt_char(COMMAND_UUID, bytes([0x0B, 0x01, 0x00])) # Stop Logger
            await asyncio.sleep(0.3)
            await client.write_gatt_char(COMMAND_UUID, bytes([0x03, 0x01, 0x00])) # Stop Accel Stream
            await asyncio.sleep(0.3)

            logger.info("2. Erasing all old logs from flash memory...")
            await client.write_gatt_char(COMMAND_UUID, bytes([0x0B, 0x09]))
            await asyncio.sleep(1.0) # Erasing takes time

            logger.info("3. Configuring accelerometer (25Hz, +/-4g)...")
            await client.write_gatt_char(COMMAND_UUID, bytes([0x03, 0x02, 0x01, 0x00])) # Power on
            await asyncio.sleep(0.3)
            await client.write_gatt_char(COMMAND_UUID, bytes([0x03, 0x03, 0x18, 0x0C])) # 25Hz, +/-4g
            await asyncio.sleep(0.3)
            # CORRECT WAY: Enable the data output, but DO NOT start the stream
            await client.write_gatt_char(COMMAND_UUID, bytes([0x03, 0x04, 0x01, 0x01]))
            await asyncio.sleep(0.3)

            logger.info("4. Configuring the logger to record accelerometer data...")
            await client.write_gatt_char(COMMAND_UUID, bytes([0x0B, 0x02, 0x03, 0x04]))
            await asyncio.sleep(0.5)

            logger.info("5. Starting the logger...")
            await client.write_gatt_char(COMMAND_UUID, bytes([0x0B, 0x01, 0x01]))
            await asyncio.sleep(0.5)

            logger.info("\n✅ --- CONFIGURATION COMPLETE --- ✅")
            logger.info("MetaMotion is now correctly logging data to its internal memory.")

    except Exception as e:
        logger.error(f"An error occurred during configuration: {e}")

if __name__ == "__main__":
    mac = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MAC
    asyncio.run(configure_logging_mode(mac))