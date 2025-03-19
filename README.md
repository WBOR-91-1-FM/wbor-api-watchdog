# wbor-api-watchdog

Subscribes to the SSE stream that our [Spinitron](https://spinitron.com) [API proxy](https://github.com/WBOR-91-1-FM/spinitron-proxy/) generates (to indicate that a new Spin was logged). When the message is received, query the latest spin and package it into a message that is sent to a RabbitMQ exchange for downstream consumption (e.g. an [RDS encoder](https://github.com/WBOR-91-1-FM/wbor-rds-encoder)).

## Usage

Ensure Make is installed on your system.

1. Clone the repository
2. Copy `.env.sample` to `.env` and fill in the values
3. Change values in the Makefile as needed (enter a HOST_DIR)
4. Run `make`
   1. Alternatively, run `DOCKER_TOOL=podman make` if you are using Podman

## TODO

- [ ] Polling as a fallback in case SSE fails
