# wbor-api-watchdog

Subscribes to the SSE stream that our [API relay](https://github.com/aidansmth/API-Relay) generates (to indicate a new Spin logged in [Spinitron](https://spinitron.com)). When the message is received, query the latest spin and bundle it into a message that is sent to our RabbitMQ exchange for downstream consumption (e.g. an [RDS encoder](https://github.com/WBOR-91-1-FM/wbor-rds-encoder)).
