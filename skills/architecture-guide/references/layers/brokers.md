# Layer: brokers, streams and CDC

Source: Alexey's «Брокеры, потоки и CDC» (checked 30 October 2026). Everything that carries data between services: job queues, event logs, MQTT for devices, stream processing, change capture from databases. Licences change often — check the exact version before production.

Marks: licence **open / src / prop**; status **base** (proven), **pop** (widely used now), **grow** (young, growing fast, carries risk).

## Concepts

- **Queue** — one consumer takes a message; after ack it is deleted. For jobs: "send an email", "build a report".
- **Log** — messages are kept in order for days or forever; each reader keeps its own offset and can re-read history. For events: "order created".
- **Delivery guarantees** — at-most-once may lose; **at-least-once may deliver twice, so the handler must be idempotent**; exactly-once only inside one system and expensive.

## Rule 0

A broker is one more database to back up, monitor and protect. For background jobs in a small project a Postgres table (`SKIP LOCKED`, pgmq) or Valkey is often enough. Kafka is taken when **many consumers read one event stream** or **history must be re-read**.

## Classes and technologies

### QUEUE — message brokers and queues
Accept messages and hand them to consumers; routing, retries, delayed delivery, dead letter queues.

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **RabbitMQ** | open (MPL 2.0) · base | Erlang; exchange (direct, topic, fanout, headers) → routing → queues; AMQP 0-9-1 and 1.0 (native in 4.x), MQTT, STOMP; at-least-once with ack; quorum queues on Raft replaced mirrored ones; metadata on Khepri (Raft) in 4.x; Streams = a Kafka-style log inside; 3–5 node cluster, up to hundreds of thousands msg/s per stream | background jobs routed by type; integrations needing retries, TTL and DLQ; request/reply microservices; team already knows AMQP | keeping event history for months; hundreds of consumers of one stream (that is a log's job); huge queues piling up for hours |
| **NATS + JetStream** | open (Apache 2.0) · pop | one binary; subjects with wildcards; core = in-memory pub/sub at-most-once; JetStream adds durable streams, push/pull consumers, dedup, KV, object store; MQTT and WebSocket; clusters, superclusters across regions, leaf nodes at the edge. Stayed in CNCF under Apache 2.0 after the 2025 Synadia dispute | links between microservices and AI agents; edge and IoT (drones, sensors, branches); request/reply and messaging service mesh; a low-footprint broker | fewer connectors than Kafka; huge analytical event history; a team needing the AMQP library world |
| **Valkey / Redis Streams** | open (BSD-3, Valkey) · pop | Streams with consumer groups and a pending list (PEL), lists (LPUSH/BRPOP); at-least-once via XACK; in memory, durability depends on AOF; BullMQ, Sidekiq built on it | small job queues when Valkey is already there; fast notifications between services | important data that must not be lost; volume bigger than RAM |
| **Postgres queue (pgmq, `SKIP LOCKED`)** | open · pop | a jobs table, workers take rows with `FOR UPDATE SKIP LOCKED`; **the job is created in the same transaction as the data**; pgmq has an SQS-like API; River (Go), pg-boss and Graphile Worker (Node), Oban (Elixir) use the same idea; the basis of Transactional Outbox; thousands of jobs/s on ordinary Postgres | background jobs in a normal backend; outbox for reliable publishing to Kafka; no wish to add a broker | tens of thousands msg/s sustained; fan-out of one event to many services |
| **ActiveMQ Artemis** | open (Apache 2.0) · base | ActiveMQ Classic successor; queues and topics; AMQP, OpenWire, MQTT, STOMP, Core; XA transactions; journal replication. Found in banks and Java enterprise (JMS, Spring) | integration with JMS enterprise systems; distributed XA transactions | a new project with no Java legacy (RabbitMQ or NATS are simpler) |
| **LavinMQ** | open (Apache 2.0) · grow | Crystal, from the CloudAMQP authors; AMQP 0-9-1 and MQTT; writes messages to files via mmap, keeps little in memory; one machine + replicas | a cheap AMQP broker on a small server | needing all RabbitMQ plugins and ecosystem |

### LOG — event logs (the Kafka world)
The Kafka protocol is the standard; Kafka plus a dozen compatible engines. New trend: **diskless** brokers keeping data in S3 — cheaper, higher latency.

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Apache Kafka** | open (Apache 2.0) · base | topics → partitions → ordered log, consumer groups; at-least-once, exactly-once via transactions and idempotent producer; millions msg/s. 4.0 removed ZooKeeper (KRaft only); 4.1 adds share groups ("queues for Kafka", KIP-932, preview) with per-message ack, and JWT auth via OIDC. Confluent was bought by IBM in 2026; Apache Kafka stays an Apache project | an event bus between many teams and services; event sourcing and replaying history; CDC → analytics, search, cache; streaming logs and telemetry | a plain job queue for one service; a small team without operations experience; single-digit-ms latency at low traffic |
| **Redpanda** | src (BSL 1.1 Community; Apache 2.0 after 4 years; can't sell as a service) · pop | C++, no JVM, thread-per-core, Raft per partition; Kafka protocol + HTTP Proxy + Schema Registry in one binary; lower latency, fewer nodes. Tiered storage, RBAC, Iceberg topics, OIDC need an Enterprise key | a Kafka workload with less hardware and simpler ops; low p99; dev environments ("Kafka" in seconds) | an open licence; tiered storage and RBAC without paying |
| **AutoMQ** | open (Apache 2.0) · grow | Kafka fork storing the log in S3 via S3Stream (WAL + cache); 100% Kafka protocol; stateless brokers scale in seconds; AZ-aware routing avoids cross-zone traffic. Upstream discusses diskless topics (KIP-1150) | big Kafka in a cloud where disks and cross-zone traffic are expensive; long event retention | minimal latency; own hardware without S3 storage |
| **Apache Pulsar** | open (Apache 2.0) · base | stateless brokers, data in BookKeeper, metadata in ZooKeeper or Oxia; subscriptions exclusive / shared / failover / key_shared; Kafka adapter; multi-tenancy and geo-replication built in; many components | a messaging platform for many teams with quotas; geo-replication out of the box | a small team (too complex); smaller ecosystem than Kafka |
| **WarpStream** | prop (Confluent → IBM) · grow | BYOC: stateless agents, data in your S3, metadata in their service; Kafka protocol; latency ~hundreds of ms | logs and telemetry where price matters more than latency | self-hosted without an external service; latency-critical work |

### MQTT — brokers for devices
A light protocol for devices with weak links (drones, sensors, smart toys): QoS 0/1/2, retained messages (last value), Last Will (sent when a device disappears).

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **EMQX** | src (BSL 1.1 since 5.9 — a commercial cluster needs a licence) · pop | Erlang; MQTT 3.1.1/5.0, MQTT over QUIC, WebSocket; cluster with millions of connections; SQL rule engine forwarding to Kafka, Postgres, HTTP; JWT and DB auth | a drone or IoT fleet; millions of connections; MQTT → Kafka/DB bridge without code | needing an open licence (→ Mosquitto or NanoMQ); a 10-device project |
| **Eclipse Mosquitto** | open (EPL 2.0 / EDL 1.0) · base | small C binary, runs on a Raspberry Pi; MQTT 3.1–5.0, WebSocket; no cluster — several brokers with bridges for fault tolerance | small IoT systems, home automation; a broker on board or at a base station | high availability with thousands of devices |
| **NanoMQ** | open (MIT) · grow | from the EMQX authors; multi-threaded; MQTT 5.0, QUIC, ZeroMQ bridges; runs on microcomputers and gateways; bridges to cloud EMQX | an edge gateway collecting data and forwarding to the cloud | the central broker for a large fleet |

### STREAM — stream processing
Compute over an event stream on the fly: time windows, aggregates, stream joins, anomaly detection. The hard part is **state**: it must be stored and restored after failures.

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Apache Flink** | open (Apache 2.0) · base | operator graph, event time and watermarks (late events handled right); DataStream (Java), Flink SQL, PyFlink; exactly-once via checkpoints; state up to terabytes; 2.0 has disaggregated state (ForSt) — faster recovery and scaling | real-time anti-fraud and anomaly detection; complex windows and stream joins; large volumes with exactly-once | simple dashboard aggregates (ClickHouse or RisingWave are simpler); a small team (hard to operate and tune) |
| **Kafka Streams** | open (Apache 2.0) · base | a library inside a Java/Kotlin app; KStream/KTable, state in RocksDB backed up to changelog topics; exactly-once inside Kafka; scale by running more copies; 4.1 early access to a new rebalance protocol | enriching and aggregating events in JVM services | a non-Kafka source; Python or Go teams |
| **Spark Structured Streaming** | open (Apache 2.0) · base | micro-batches (a real-time mode exists); SQL, Python, Scala; exactly-once with supported sinks; seconds of latency; Delta Lake / Iceberg | data lakes: streaming and batch in one codebase | millisecond latency; no Spark infrastructure |
| **RisingWave** | open (Apache 2.0) · grow | Rust; streaming database on the Postgres protocol; incrementally maintained materialised views; snapshot consistency, ~1 s checkpoints; compute separated, state in S3; native CDC from Postgres/MySQL without Debezium; sinks to Kafka, Iceberg, Postgres | live metrics and dashboards in SQL; streaming without Java code and Flink expertise | complex event logic with timers (Flink is more flexible) |
| **Materialize** | src (BSL) · pop | Differential Dataflow; SQL on the Postgres protocol; strict serializable; mainly a managed cloud service, self-managed limited | operational data where "as exact as the database" matters | an open self-hosted engine (→ RisingWave) |
| **Arroyo** | open (MIT / Apache 2.0) · grow | Rust SQL pipelines, UDFs in Rust and Python; exactly-once; cluster or single binary. Team bought by Cloudflare in 2025, powers their Pipelines; open repo lives on but depends on Cloudflare | light SQL streaming without a JVM | long-term production without accepting single-vendor dependence |

### CDC — change capture and data integration
CDC reads the database journal (WAL in Postgres, binlog in MySQL) and turns every change into an event, so search, analytics and caches stay fresh **without dual writes from code**.

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Debezium** | open (Apache 2.0) · base | connectors to Postgres, MySQL, MongoDB, SQL Server, Oracle…; at-least-once with an initial snapshot; runs on Kafka Connect, as Debezium Server (no Kafka: to NATS, Pulsar, Redis, Pub/Sub, Kinesis) or embedded; supports Outbox. **Watch the Postgres replication slot: if the connector stops, WAL grows and fills the disk** | Postgres → Kafka → ClickHouse/OpenSearch; migrating between databases without downtime; outbox events from a service | a one-off export (pg_dump or ETL is simpler); no monitoring of replication slots |
| **Kafka Connect** | open (Apache 2.0) · base | part of Apache Kafka; source and sink connectors on workers; hundreds of ready connectors; REST + JSON config without code; Single Message Transforms; at-least-once, some exactly-once | standard Kafka ↔ databases, S3, search integrations | complex transformations (stream engines are for that) |
| **Redpanda Connect** (ex-Benthos) | src (BSL; some connectors Enterprise) · pop | one Go binary; YAML input → processors → output, Bloblang transforms; Kafka, NATS, MQTT, HTTP, S3, databases, AI processors; at-least-once. Open MIT fork of old Benthos: **Bento** | wiring MQTT → Kafka → S3 declaratively; light ETL without Java | a guaranteed open licence (→ Bento) |
| **Airbyte** | src (ELv2 — fine internally, can't sell as a service) · pop | ELT on a schedule from CRMs, ads, payments, databases, APIs; incremental syncs and CDC; no-code connector builder; self-hosted on k8s or cloud | pulling SaaS data (Stripe, HubSpot, Google Ads) into a DWH | millisecond real time; light infrastructure (Airbyte is heavy) |
| **Vector** | open (MPL 2.0, owned by Datadog) · pop | Rust binary as agent or aggregator; sources → transforms (VRL) → sinks; files, journald, k8s, syslog, Kafka, OTLP; disk buffers, at-least-once | log and metric pipelines with filtering (→ ClickHouse, Loki, S3) | CDC from databases (that is Debezium) |

## Clouds

Prefer protocol-compatible services (Kafka, AMQP, SQS, MQTT) — leaving is easier. Own APIs (EventBridge, Pub/Sub, Service Bus) are convenient but tie you to the cloud.

**Migration targets** (Alexey's projects move here):

| Cloud | Service | What | When |
|---|---|---|---|
| Yandex Cloud | Managed Service for Apache Kafka | Kafka with Schema Registry | event bus, CDC |
| | Message Queue | SQS API, serverless | background jobs, decoupling services |
| | Data Streams | Kinesis and Kafka API on YDB topics | logs, telemetry |
| | EventRouter | event bus with routing rules | event-driven between cloud services |
| | Data Transfer | transfer and CDC: Postgres, MySQL, Kafka, ClickHouse, YDB | replication into analytics, migrations |
| | (no Managed RabbitMQ) | install yourself or via Marketplace | — |
| DigitalOcean | Managed Kafka | Kafka, clear per-node price | events, CDC |
| | Valkey | streams and lists as a light queue | small job queues |
| | Droplets / DOKS | RabbitMQ, NATS, EMQX yourself | everything else |
| Railway | templates only, not managed: Kafka (KRaft), Redpanda, RabbitMQ, NATS JetStream, Mosquitto, EMQX, Pulsar; job queues Temporal, BullMQ, Hatchet | runs in your project; backups, upgrades and HA are on you | MVP, staging, development, IoT prototypes |

**Industry standard:**

| Cloud | Services |
|---|---|
| AWS | SQS (standard/FIFO, DLQ — jobs without a broker); SNS (fan-out to SQS, Lambda, HTTP, SMS); EventBridge (bus, rules, scheduler, Pipes); MSK / MSK Serverless (+ MSK Connect); Kinesis Data Streams / Firehose (→ S3, Redshift); Amazon MQ (managed RabbitMQ and ActiveMQ — moving existing AMQP/JMS); Managed Flink; IoT Core (managed MQTT); DMS (migrations and CDC) |
| Google Cloud | Pub/Sub (global serverless, no partitions, push/pull, exactly-once delivery); Managed Kafka; Dataflow (Beam → BigQuery); Datastream (CDC from Postgres, MySQL, Oracle → BigQuery); Eventarc (events → Cloud Run) |
| Azure | Service Bus (AMQP 1.0, DLQ, sessions, transactions — enterprise); Event Hubs (log with a Kafka endpoint); Event Grid (event pub/sub, MQTT broker); Stream Analytics (SQL over streams) |
| Cloudflare | Queues (batches, retries, DLQ for Workers); Basin Pipelines (GA; events over HTTP/Worker → SQL → R2 as Parquet or Iceberg); Durable Objects (stateful objects — coordination, chats, realtime) |

## Task → default → when to switch

| Task | Default | Switch when |
|---|---|---|
| Background jobs in a backend | Postgres queue (pgmq / River / pg-boss) | many job types and routing → RabbitMQ; Valkey already there → BullMQ |
| Decoupling services, retries, DLQ | RabbitMQ | in a cloud without ops → SQS / Yandex Message Queue |
| Links between agents and microservices | NATS JetStream | event history for many teams → Kafka |
| Event bus for several teams | Apache Kafka | less hardware → Redpanda; expensive cloud disks → AutoMQ |
| Reliable event publishing from a service | Transactional Outbox + Debezium | — |
| Drone and IoT fleet | EMQX | small fleet or open licence → Mosquitto; edge gateway → NanoMQ |
| Postgres → search / analytics | Debezium → Kafka → ClickHouse / OpenSearch | without Kafka → Debezium Server or Yandex Data Transfer |
| Live metrics in SQL | RisingWave | complex event logic → Flink |
| Anti-fraud, complex windows | Apache Flink | — |
| Server logs | Vector | — |
| SaaS data into a warehouse | Airbyte | few sources → simple cron scripts |
| Events into a data lake | Kafka + S3 / Iceberg connector | on Cloudflare → Basin Pipelines |
