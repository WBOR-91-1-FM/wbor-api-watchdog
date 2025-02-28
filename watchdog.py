import os
import json
import asyncio
import aiohttp
import aio_pika
from dotenv import load_dotenv

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


async def fetch_latest_spin():
    """Fetch the latest spin from the API."""
    async with aiohttp.ClientSession() as session:
        async with session.get(SPIN_GET_URL) as response:
            if response.status == 200:
                spins_data = await response.json()

                # Directly fetch spin-0 as it is the latest
                latest_spin = spins_data.get("spin-0")

                if latest_spin:
                    print(f"Latest spin: {latest_spin}")
                    return latest_spin

                print("No latest spin found in response.")
                return None

            print(f"Failed to fetch spin data: `{response.status}`")
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

        print(
            f"Published spin data to RabbitMQ on `{RABBITMQ_EXCHANGE}` with key `{RABBITMQ_ROUTING_KEY}`."
        )

        await connection.close()
    except (
        aio_pika.exceptions.AMQPConnectionError,
        aio_pika.exceptions.ChannelClosed,
    ) as e:
        print(f"Error publishing to RabbitMQ: `{e}`")


async def listen_to_sse():
    """Listen to the SSE stream and trigger updates."""
    async with aiohttp.ClientSession() as session:
        async with session.get(SSE_STREAM_URL) as response:
            async for line in response.content:
                if line:
                    decoded_line = line.decode("utf-8").strip()
                    if "Spin outdated - Update needed." in decoded_line:
                        print("Received SSE update. Fetching latest spin...")
                        spin_data = await fetch_latest_spin()
                        if spin_data:
                            await send_to_rabbitmq(spin_data)


async def main():
    """
    Entry point for the script.

    This function listens to the SSE stream and triggers updates
    when a new spin is available.
    """
    await listen_to_sse()


if __name__ == "__main__":
    asyncio.run(main())
