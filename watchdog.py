"""
Module to watch for updates in the WBOR Spinitron API relay and publish them to 
RabbitMQ.

This script listens to a Server-Sent Events (SSE) stream and fetches the latest 
spin data. When a new spin is available, it publishes the data to a RabbitMQ 
exchange.

The RabbitMQ exchange, queue, and routing key are all configurable via environment
variables.

This script is intended to be run as a standalone service that is always running
to keep the RabbitMQ queue up-to-date with the latest spins.
"""

import os
import json
import logging
import asyncio
import aiohttp
import aio_pika
from dotenv import load_dotenv

from utils.logging import configure_logging

logging.root.handlers = []
logger = configure_logging()

load_dotenv()

# Load environment variables (RabbitMQ credentials, API endpoint)
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE")
RABBITMQ_EXCHANGE = os.getenv("RABBITMQ_EXCHANGE")
RABBITMQ_ROUTING_KEY = os.getenv("RABBITMQ_ROUTING_KEY")

API_BASE_URL = "https://api-1.wbor.org"

SSE_STREAM_URL = f"{API_BASE_URL}/spins/stream"
SPIN_GET_URL = f"{API_BASE_URL}/spins/get"
logger.debug("SSE_STREAM_URL: `%s`", SSE_STREAM_URL)
logger.debug("SPIN_GET_URL: `%s`", SPIN_GET_URL)


async def fetch_latest_spin():
    """Fetch the latest spin from the API."""
    async with aiohttp.ClientSession() as session:
        async with session.get(SPIN_GET_URL) as response:
            if response.status == 200:
                spins_data = await response.json()

                # Directly fetch spin-0 as it is the latest
                latest_spin = spins_data.get("spin-0")

                if latest_spin:
                    logger.info("Latest spin: `%s`", latest_spin)
                    return latest_spin

                logger.warning("No latest spin found in response.")
                return None

            logger.critical("Failed to fetch spin data: `%s`", response.status)
            return None


async def send_to_rabbitmq(spin_data):
    """Publish spin data to RabbitMQ."""
    try:
        connection = await aio_pika.connect_robust(
            host=RABBITMQ_HOST, login=RABBITMQ_USER, password=RABBITMQ_PASS
        )
        channel = await connection.channel()

        # Declare the durable topic exchange
        exchange = await channel.declare_exchange(
            RABBITMQ_EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
        )

        # Publish the message
        message = aio_pika.Message(body=json.dumps(spin_data).encode("utf-8"))
        await exchange.publish(message, routing_key=RABBITMQ_ROUTING_KEY)

        logger.info(
            "Published spin data to RabbitMQ on `%s` with key `%s`.",
            RABBITMQ_EXCHANGE,
            RABBITMQ_ROUTING_KEY,
        )

        await connection.close()
    except (
        aio_pika.exceptions.AMQPConnectionError,
        aio_pika.exceptions.ChannelClosed,
    ) as e:
        logger.critical("Error publishing to RabbitMQ: `%s`", e)


async def listen_to_sse():
    """Listen to the SSE stream and trigger updates, with automatic reconnection."""
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(SSE_STREAM_URL) as response:
                    logger.info("Attempting to connect to SSE stream...")

                    if response.status != 200:
                        logger.error(
                            "Failed to connect to SSE stream, status: `%s`",
                            response.status,
                        )
                        await asyncio.sleep(5)  # Wait before retrying
                        continue

                    logger.info("Connected to SSE stream successfully.")
                    logger.debug("Starting SSE message loop...")

                    # Ensure response.content is not empty before processing
                    async for line in response.content:
                        logger.debug("Received raw line: `%s`", line)

                        try:
                            if line:
                                decoded_line = line.decode("utf-8").strip()
                                logger.debug("SSE received: `%s`", decoded_line)

                                if "Spin outdated - Update needed." in decoded_line:
                                    logger.info(
                                        "Received spin update signal. Fetching latest spin..."
                                    )
                                    spin_data = await fetch_latest_spin()
                                    if spin_data:
                                        await send_to_rabbitmq(spin_data)
                                    else:
                                        logger.warning(
                                            "No valid spin data received after SSE update."
                                        )
                        except (aiohttp.ClientError, json.JSONDecodeError) as e:
                            logger.exception("Error processing SSE message: `%s`", e)
                            continue  # Continue processing SSE messages

        except aiohttp.ClientError as e:
            logger.error("SSE connection error: `%s`", e)
        except (aio_pika.exceptions.AMQPError, asyncio.TimeoutError) as e:
            logger.critical("Unexpected error in SSE listener: `%s`", e)

        logger.info("Reconnecting to SSE stream in 5 seconds...")
        await asyncio.sleep(5)  # Delay before attempting reconnection


async def main():
    """
    Entry point for the script.

    This function listens to the SSE stream and triggers updates
    when a new spin is available.
    """
    logger.info("Starting WBOR Spinitron watchdog...")
    try:
        await listen_to_sse()
    except Exception as e:
        logger.critical("Unhandled exception in main: %s", e, exc_info=True)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested.")
    finally:
        loop.close()
