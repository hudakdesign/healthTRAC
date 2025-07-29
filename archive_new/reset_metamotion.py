#!/usr/bin/env python3
"""
MetaMotion Complete Reset
Resets all modules and configurations
"""
import asyncio
import sys
from bleak import BleakClient
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Reset')

# Default MAC address
MAC_ADDRESS = "C8:0B:FB:24:C1:65"

COMMAND_UUID = "326a9001-85cb-9195-d9dd-464cfbbae75a"
NOTIFY_UUID = "326a9006-85cb-9195-d9dd-464cfbbae75a"


async def reset_device(address):
    """Perform complete reset of device"""
    logger.info(f"Performing complete reset of {address}...")

    try:
        client = BleakClient(address)
        await client.connect(timeout=15.0)
        logger.info("Connected successfully")

        # Wait for service discovery
        logger.info("Waiting for service discovery...")
        await asyncio.sleep(3.0)

        # Subscribe to notifications
        await client.start_notify(NOTIFY_UUID, lambda s, d: None)
        await asyncio.sleep(1.0)

        # Clear everything in sequence
        modules = [
            (0x0F, "macros"),
            (0x09, "data processors"),
            (0x0C, "timers"),
            (0x0B, "logging"),
            (0xFE, "debug")
        ]

        for module_id, name in modules:
            logger.info(f"Clearing {name}...")
            if module_id == 0x0B:  # Logging uses command 0x09 to clear
                await client.write_gatt_char(COMMAND_UUID,
                                             bytes([module_id, 0x09]))
            else:
                await client.write_gatt_char(COMMAND_UUID,
                                             bytes([module_id, 0x05]))
            await asyncio.sleep(1.5)

        # Turn on BLE advertising (so we can connect again)
        logger.info("Enabling BLE advertising...")
        await client.write_gatt_char(COMMAND_UUID, bytes([0x11, 0x01, 0x01]))
        await asyncio.sleep(1.0)

        logger.info("Reset complete")

    except Exception as e:
        logger.error(f"Reset error: {e}")
    finally:
        try:
            await client.disconnect()
            logger.info("Disconnected")
        except:
            pass


if __name__ == "__main__":
    # Default MAC address is already set

    # Override with command line argument if provided
    if len(sys.argv) > 1:
        MAC_ADDRESS = sys.argv[1]

    asyncio.run(reset_device(MAC_ADDRESS))