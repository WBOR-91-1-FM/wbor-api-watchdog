# wbor-api-watchdog

Subscribes to the SSE stream that our [API proxy](https://github.com/WBOR-91-1-FM/spinitron-proxy/) generates (to indicate that a new Spin was logged in [Spinitron](https://spinitron.com)). When the message is received, query the latest spin and package it into a message that is sent to a RabbitMQ exchange for downstream consumption (e.g. an [RDS encoder](https://github.com/WBOR-91-1-FM/wbor-rds-encoder)).

```sh
make DOCKER_TOOL=docker
```

## TODO

- [ ] Polling as a fallback in case SSE fails
