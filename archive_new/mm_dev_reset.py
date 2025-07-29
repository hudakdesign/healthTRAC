#!/usr/bin/env python3
"""
Reset and Basic Configuration for MetaMotion
- Performs a factory reset
- Enables standard advertising
- Configures for easy connections
"""

import asyncio
import sys
from bleak import BleakClient, BleakScanner
import logging

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ResetConfig")

# Default MAC address
DEFAULT_MAC = "C8:0B:FB:24:C1:65"

# UUIDs
COMMAND_UUID = "326a9001-85cb-9195-d9dd-464cfbbae75a"
NOTIFY_UUID = "326a9006-85cb-9195-d9dd-464cfbbae75a"


async def reset_and_configure(mac_address):
    """Reset and configure the MetaMotion"""
    logger.info(f"Connecting to {mac_address}...")

    # Try to find device first
    device = await BleakScanner.find_device_by_address(mac_address, timeout=5.0)
    if not device:
        logger.error(f"Device {mac_address} not found! Please check if it's powered on.")
        return False

    logger.info(f"Found device with signal strength {device.rssi} dBm")

    # Connect to device
    async with BleakClient(mac_address) as client:
        if not client.is_connected:
            logger.error("Failed to connect!")
            return False

        logger.info("Connected successfully!")

        # Get services
        await client.get_services()
        logger.info("Service discovery completed")

        # Factory reset first
        logger.info("Performing factory reset...")
        try:
            # Module 0x11 (Settings), Command 0x09 (Reset)
            await client.write_gatt_char(COMMAND_UUID, bytes([0x11, 0x09]))
            logger.info("Reset command sent")

            # Give device time to reset
            logger.info("Waiting for device to reset (10 seconds)...")
            await asyncio.sleep(10.0)
        except Exception as e:
            logger.warning(f"Reset may have failed (this is normal if device restarted): {e}")
            return True  # Still consider successful since reset causes disconnect

    # After reset, reconnect and configure
    logger.info("Reconnecting after reset...")
    await asyncio.sleep(2.0)

    try:
        async with BleakClient(mac_address) as client:
            if not client.is_connected:
                logger.error("Failed to reconnect after reset!")
                return False

            logger.info("Reconnected successfully")
            await client.get_services()

            # Configure advertising and connection parameters
            logger.info("Configuring device for easier connections...")

            # Enable advertising
            # Module 0x11 (Settings), Command 0x01 (Set BLE Advertising), Param 0x01 (On)
            await client.write_gatt_char(COMMAND_UUID, bytes([0x11, 0x01, 0x01]))
            await asyncio.sleep(0.5)

            # Set advertising name to make it easier to identify
            name = "HTRAC-MM"
            name_bytes = name.encode('utf-8')
            command = bytes([0x11, 0x0C]) + name_bytes
            await client.write_gatt_char(COMMAND_UUID, command)
            await asyncio.sleep(0.5)

            # Set advertising interval to faster rate
            # Module 0x11 (Settings), Command 0x06 (Set Advertising Interval)
            # Params: 417 (0xA1, 0x01) = 417.5ms interval, moderate battery usage
            await client.write_gatt_char(COMMAND_UUID, bytes([0x11, 0x06, 0xA1, 0x01]))
            await asyncio.sleep(0.5)

            # Set connection parameters for better connection stability
            # Module 0x11 (Settings), Command 0x03 (Set Connection Parameters)
            # Params: min interval, max interval, latency, timeout
            await client.write_gatt_char(COMMAND_UUID,
                                         bytes([0x11, 0x03,
                                                0x06, 0x00,  # Min interval: 7.5ms
                                                0x06, 0x00,  # Max interval: 7.5ms
                                                0x00, 0x00,  # Latency: 0
                                                0x90, 0x01]))  # Timeout: 400
            await asyncio.sleep(0.5)

            # Set TX power higher for better connection range
            # Module 0x11 (Settings), Command 0x04 (Set TX Power)
            # Param: 0x04 = 0dBm (max power)
            await client.write_gatt_char(COMMAND_UUID, bytes([0x11, 0x04, 0x04]))

            logger.info("Configuration complete!")
            logger.info("Device should now be easier to connect to.")

            return True

    except Exception as e:
        logger.error(f"Configuration failed: {e}")
        return False


if __name__ == "__main__":
    # Use provided MAC or default
    mac_address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MAC

    print(f"\n=== MetaMotion Reset & Configuration ===")
    print(f"Target MAC: {mac_address}")

    result = asyncio.run(reset_and_configure(mac_address))

    if result:
        print("\n✅ Device has been reset and configured for easier connections")
        print("Now try connecting with your Arduino")
    else:
        print("\n❌ Reset and configuration failed")
        print("Check that the device is powered on and try again")