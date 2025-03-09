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
from aiosseclient import aiosseclient
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

SSE_STREAM_URL = f"{API_BASE_URL}/spin-events"
SPIN_GET_URL = f"{API_BASE_URL}/api/spins"
logger.debug("SSE_STREAM_URL: `%s`", SSE_STREAM_URL)
logger.debug("SPIN_GET_URL: `%s`", SPIN_GET_URL)


async def fetch_latest_spin():
    """Fetch the latest spin from the API."""
    async with aiohttp.ClientSession() as session:
        async with session.get(SPIN_GET_URL) as response:
            if response.status == 200:
                spins_data = await response.json()

                # Directly fetch item 0 as it is the latest spin
                items = spins_data.get("items")
                latest_spin = items[0] or None
                if latest_spin:
                    logger.info("Latest spin: `%s`", latest_spin)
                    return latest_spin
                logger.warning("No latest spin found in response.")
                return None
            logger.critical("Failed to fetch spin data: `%s`", response.status)
            return None


async def listen_to_sse():
    logger.info("Listening for SSE at: %s", SSE_STREAM_URL)

    while True:
        try:
            async for event in aiosseclient(SSE_STREAM_URL):
                # Check if we got the event that indicates a new spin
                if event.data == "new spin data":
                    logger.info("Received SSE: 'new spin data'")
                    spin = await fetch_latest_spin()
                    if spin is not None:
                        await send_to_rabbitmq(spin)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error("SSE connection dropped or failed: %s", e)
            await asyncio.sleep(5)  # Wait and retry
        except Exception as e:
            logger.critical("Unexpected error in SSE loop: %s", e, exc_info=True)
            await asyncio.sleep(5)


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
