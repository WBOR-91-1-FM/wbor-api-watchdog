# wbor-api-watchdog

Subscribes to the SSE stream that our [Spinitron](https://spinitron.com) [API proxy](https://github.com/WBOR-91-1-FM/spinitron-proxy/) generates (to indicate that a new Spin was logged). When the message is received, query the latest spin and package it into a message that is sent to a RabbitMQ exchange for downstream consumption (e.g. an [RDS encoder](https://github.com/WBOR-91-1-FM/wbor-rds-encoder)).

If the SSE stream from the proxy is interrupted, the watchdog will attempt to reconnect. If reconnections fail, it switches to polling mode. In both SSE-triggered fetches and polling mode, if the API proxy endpoint for fetching spins is unreachable, the watchdog will fall back to querying the primary Spinitron API directly using an API key. It polls for new spins every 3 seconds (by default) while periodically checking for the proxy's SSE stream to come back online. Once the proxy's SSE stream is back online, it switches back to listening to the SSE stream.

## Usage

Ensure Make is installed on your system.

1. Clone the repository
2. Copy `.env.sample` to `.env` and fill in the values. This includes:
   - `API_BASE_URL` for the Spinitron proxy.
   - `SPINITRON_API_URL` for the primary Spinitron API (e.g., `https://spinitron.com/api/`).
   - `SPINITRON_API_KEY` for the primary Spinitron API.
   - RabbitMQ connection details.
3. Change values in the Makefile as needed (enter a HOST_DIR)
4. Run `make`
   - Alternatively, run `DOCKER_TOOL=podman make` if you are using Podman
