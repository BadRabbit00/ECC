# Layer: databases

Source: Alexey's «Карта баз данных» (October 2026). Databases that run as a separate service: you start a server and connect to it over the network. Licences and cloud service names change often — before a production decision, check the licence of the exact version and the data region.

Licence marks: **open** = a real open licence; **src** = source-available with restrictions; **prop** = proprietary or paid.

## Rule 0

Start with PostgreSQL. Add a second database only when Postgres has hit a specific, **measured** problem. Every new database brings its own backups, monitoring, upgrades, access control and one more point of failure.

## Classes and engines

### REL — relational (OLTP)
Tables with a strict schema, foreign keys, SQL, ACID transactions. OLTP = many small fast operations: an order, a payment, a profile.

| Engine | Licence | Inside | Good for | Bad for |
|---|---|---|---|---|
| **PostgreSQL** — the default for a new project | open (PostgreSQL) | MVCC (reads never block writes; VACUUM cleans old versions). Tables + JSONB, arrays, ranges, PostGIS, pgvector. Window functions, CTE, recursion; isolation up to Serializable. Scale: vertical + read replicas; sharding via Citus or sharding proxies. Extensions: PostGIS, pgvector, TimescaleDB, pg_cron, RLS for multi-tenancy; logical replication and CDC | almost any backend (CRM, shop, portals); complex relations and SQL reports; multi-tenancy via RLS; one engine instead of five (JSON, search, vectors, geo) | huge write streams (100k+ events/s) without preparation; analytics over billions of rows (columnar is 10× faster); global writes in several regions; untuned VACUUM and no pooling (PgBouncer) hurt |
| **MySQL / MariaDB** | open (GPLv2) | InnoDB with a clustered PK index, so the PK choice affects speed. JSON weaker than Postgres. Replicas, Group Replication; sharding via Vitess | CMS, PHP stack, products that require MySQL; simple CRUD with very frequent reads; team and hosting already on MySQL | complex SQL analytics (weaker optimizer); rich types, extensions, geo. MySQL and MariaDB have diverged — not interchangeable |

### DSQL — distributed SQL (NewSQL)
SQL and ACID like Postgres, but data is split automatically and lives on many nodes; Raft keeps replicas consistent. Cost: latency — every write waits for a majority.

| Engine | Licence | Inside | Good for | Bad for |
|---|---|---|---|---|
| **CockroachDB** | prop (no open Core since late 2024; Enterprise free under $10M revenue, with telemetry and yearly re-registration) | Postgres wire protocol (not all features); Serializable by default; ranges with own Raft groups; rows can be pinned to a region | fintech/SaaS needing multi-region ACID; per-row data residency | small projects (Postgres is faster and simpler); Postgres extensions don't work; check the licence before building a product on it |
| **YugabyteDB** | open (Apache 2.0) | real Postgres query layer on DocDB (RocksDB + Raft); YSQL + YCQL; much of the PG extensions and drivers work | "Postgres, but across three DCs without downtime"; migrating from Postgres with minimal rewrite | one machine is enough — then it is extra complexity; joins across nodes are slower than in one Postgres |
| **TiDB** | open (Apache 2.0) | MySQL protocol; TiDB (SQL) + TiKV (rows, Raft) + TiFlash (columns) + PD; HTAP without ETL | MySQL that no longer fits one machine; reports on live data without a separate store | little data — too many components; Postgres stacks |
| **YDB** | open (Apache 2.0) | Yandex; row and column tables plus topics (Kafka-like); YQL with a Postgres compatibility layer; Serializable; auto-sharding; serverless in Yandex Cloud | Yandex Cloud projects needing scale without manual sharding; serverless backends with unpredictable load | smaller community than Postgres; YQL differs from usual SQL |

### DOC — document
A record is a JSON document with nested fields; flexible schema. Good when an object is read whole; bad when many entities are related.

| Engine | Licence | Inside | Good for | Bad for |
|---|---|---|---|---|
| **MongoDB** | src (SSPL — you cannot build your own cloud service on it) | BSON, WiredTiger, 16 MB per document; MQL + aggregation pipeline, `$lookup`; multi-document ACID since 4.0 but costlier than SQL; replica set + sharding by key; Change Streams, TTL indexes, time-series, geo; vectors and full text in Atlas | catalogs with varying attributes; content, profiles, events read whole; quick prototypes without schema migrations | finance and accounting with many relations; reports with many joins; "no schema" turns into "schema smeared across the code" |
| **FerretDB** | open (Apache 2.0) | MongoDB protocol on PostgreSQL (DocumentDB extension); Mongo drivers work; inherits Postgres transactions and scale | Mongo code where the licence or database sprawl is a problem; Mongo API with backups and monitoring already built for Postgres | all the newest MongoDB features 1:1; very high load on the pure Mongo path |
| **CouchDB** | open (Apache 2.0) | JSON over HTTP; Mango queries, map/reduce views; per-document MVCC with revisions; multi-master replication, conflicts kept for the app to resolve; with PouchDB gives offline-first | mobile and field apps without a stable network; sync between branches | complex queries and analytics; high-load backends |

### KV — key-value and in-memory
Key → value, hence speed. In-memory engines keep everything in RAM and answer in fractions of a millisecond. Cache, counters, queues and locks — **not the primary store**.

| Engine | Licence | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Valkey** | open (BSD-3, Linux Foundation) | Redis fork since 2024; full Redis client compatibility; strings, hashes, lists, sets, sorted sets, streams, bitmaps; Lua; MULTI/EXEC; replicas, Sentinel, Cluster; RDB + AOF, still memory-first. Clouds are moving to Valkey | cache in front of the DB, sessions, rate limiting; leaderboards (sorted sets); pub/sub and light queues (streams); distributed locks (carefully) | the only store for important data; data bigger than RAM; complex queries and search by value |
| **Redis 8** | src (AGPLv3 / RSAL / SSPL) | Stack modules (JSON, search, vectors, time-series) are in the core; AGPL is fine internally but requires releasing code if you offer a modified Redis as a service | search and vectors right in the cache; Redis Enterprise solutions | want a clean permissive licence → Valkey; same as Valkey: not the primary store |
| **Dragonfly** | src (BSL 1.1) | multi-threaded shared-nothing, each core owns its data; Redis + Memcached API; on one big machine beats a Redis cluster and uses less memory | a huge cache on one big server; hit Redis single-threading | need an open licence; need every detail of the Redis Cluster protocol |
| **etcd** | open (Apache 2.0) | versioned KV; gRPC, watch, leases with TTL; compare-and-swap; 3–5 nodes on Raft; megabytes to gigabytes, not terabytes. The brain of Kubernetes | configuration, service discovery, leader election; coordinating distributed workers | user data; large values and heavy writes |
| **FoundationDB** | open (Apache 2.0) | ordered KV with strict Serializable across the cluster; deterministic simulation testing; "layers" on top (document, SQL, queues). Apple iCloud, Snowflake metadata | building your own database or metadata service; real distributed ACID on KV | a ready app database out of the box; transactions longer than 5 s (hard limit) |

### WIDE — wide-column
Rows grouped by partition key and sorted inside it. Queries are designed upfront: "one table per query". In return, writes grow linearly with nodes.

| Engine | Licence | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Apache Cassandra** | open (Apache 2.0) | masterless ring, multi-DC; LSM tree (journal + memory → SSTables) so writes are cheap; per-query consistency ONE / QUORUM / ALL; CQL without joins; LWT via Paxos, Accord ACID in progress; 5.0 adds vector search and SAI indexes | telemetry, event logs, IoT, chat messages; 24/7 writes in several DCs without downtime | ad-hoc queries and reports; frequent updates/deletes (tombstones hurt); a small team without operations experience |
| **ScyllaDB** | src (open version closed since late 2024; free edition size-limited) | Cassandra rewritten in C++ (Seastar), shard-per-core, no GC pauses; CQL + DynamoDB API; usually several times fewer nodes | Cassandra workloads cheaper in hardware; predictable low p99 | need an open licence; the same model limits as Cassandra |

### GRAPH — graph
Nodes and edges with properties; following an edge costs the same however much data there is (index-free adjacency). Strong for "friends of friends who…".

| Engine | Licence | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Neo4j** | open (GPLv3 Community) | property graph; Cypher / GQL; ACID; clusters and sharding only in Enterprise; large algorithm library (PageRank, communities, shortest paths); vector index → GraphRAG | knowledge graphs, GraphRAG, ontologies; anti-fraud chains between accounts; recommendations by relations, IAM permission graphs | plain tables and aggregates; huge writes; scaling in Community |
| **Memgraph** | src (BSL 1.1) | in-memory, C++, Cypher, ACID, replicas; reads Kafka streams and recomputes algorithms on the fly | graph analytics over an event stream; Cypher plus speed | a graph larger than RAM; need a clean open licence |

### MULTI — multi-model
Try to be document, graph, KV and sometimes vector at once. Plus: one engine. Minus: usually weaker than a specialised engine in each model.

| Engine | Licence | Inside | Good for | Bad for |
|---|---|---|---|---|
| **SurrealDB** | src (BSL 1.1) | Rust; documents, graph edges (RELATE), vectors, geo; SurrealQL; ACID; record-level permissions, auth, live queries, frontend access; storage: memory, RocksDB, TiKV; embeddable | prototypes and pet projects wanting everything in one; related data + realtime for small apps; embedded in Rust apps | critical high-load production (young engine); need a mature tool and people ecosystem; need an open licence |
| **ArangoDB** | src (BSL 1.1 since 3.12, was Apache 2.0) | documents, graphs (edges are document collections), full text (ArangoSearch); AQL; ACID on one server, limited in a cluster | documents with rich relations without two databases | pure graph work (Neo4j is stronger); distributed transactions |

### OLAP — analytical (columnar)
Data stored by column: "sales by month" reads only the needed columns and compresses them heavily. Great for reports over billions of rows, bad for point updates.

| Engine | Licence | Inside | Good for | Bad for |
|---|---|---|---|---|
| **ClickHouse** | open (Apache 2.0) | MergeTree engines; SQL with extensions; no classic transactions (block inserts are atomic); shards + replicas, Keeper; vectorised execution, heavy compression, materialised views computed on insert; Kafka and S3 engines; likes batch inserts | product analytics, events, clickstream; logs and traces (cheaper than Elasticsearch); dashboards over hundreds of millions of rows in seconds | OLTP with frequent single-row UPDATE/DELETE; one-row inserts; complex multi-table joins without preparation |
| **StarRocks** | open (Apache 2.0) | MPP; MySQL protocol; cost-based optimizer; distributed joins between large tables better than ClickHouse; upsert by PK; reads Iceberg, Hudi, Delta directly | BI with star schemas and many joins; queries over a data lake | small volumes (overkill); OLTP |
| **Apache Druid** | open (Apache 2.0) | time-partitioned segments; Druid SQL; many node roles (hard to operate) | live dashboards on a Kafka event stream for many users | a small team (ClickHouse is simpler); joins and updates |
| **DuckDB** | open (MIT) | embedded columnar library, ACID in one process; reads Parquet, CSV, JSON from disk or S3; MotherDuck as a service | analytics over files, notebooks, ETL scripts; agents that need to compute over a CSV quickly | many concurrent writing clients; a shared team server |

### TS — time series
Point = time + labels + value; data is appended and read in time windows. Specialised engines compress 10–20× and drop old data by retention policy.

| Engine | Licence | Inside | Good for | Bad for |
|---|---|---|---|---|
| **TimescaleDB** | open (Apache 2.0 + Timescale License: use freely, don't sell as DBaaS) | Postgres extension; hypertables split by time, columnar compression of old chunks, continuous aggregates; full SQL and ACID | business and IoT metrics next to normal data; joining a series with the customer table | Prometheus-style infrastructure monitoring; millions of high-cardinality series |
| **VictoriaMetrics** | open (Apache 2.0) | Prometheus-compatible; MetricsQL (superset of PromQL); single-node or cluster; very frugal with memory and disk; VictoriaLogs nearby | monitoring servers, k8s, network (UniFi exporters too); replacing Prometheus as it grows | transactional business data; arbitrary SQL |
| **InfluxDB 3** | open (MIT / Apache 2.0, Core) | Rust on Arrow + Parquet in object storage; SQL and InfluxQL (Flux gone, breaks v2); Core = one node, Enterprise = cluster | IoT and sensors, drone telemetry | long history in free Core (limits on old-data queries); already living in the Prometheus world |
| **QuestDB** | open (Apache 2.0) | columnar with a designated timestamp; SQL + SAMPLE BY, ASOF JOIN; one machine, replicas in Enterprise | market data, high-frequency series | a multi-node cluster in the free version |

### SEARCH — search
Inverted index: word → documents. Full text with morphology, typos, ranking and facets. A **secondary index, not the source of truth** — data is copied here from the main database.

| Engine | Licence | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Elasticsearch** | src (AGPLv3 / SSPL / ELv2) | Lucene; Query DSL, ES\|QL, SQL; near-real-time (~1 s); shards + replicas; strong aggregations, vector and hybrid search (BM25 + vectors); memory-hungry | complex catalog and document search; SIEM, security logs, ELK | the primary store (mapping failures lose data); a small site (heavy and expensive) |
| **OpenSearch** | open (Apache 2.0, Linux Foundation) | Elasticsearch fork (2021); Query DSL, PPL, SQL; free security (RBAC, audit), alerting, k-NN plugins; the engine behind AWS, Yandex Cloud and DigitalOcean managed search | the same as Elastic with an open licence; SIEM on an open stack (Wazuh uses it) | the same minuses: memory, complexity, not a source of truth |
| **Meilisearch** | open (MIT, Community) | Rust; REST, filters, facets, hybrid search; async indexing; one machine (sharding in Enterprise); typo tolerance, ranking, highlighting, good Russian, almost no tuning | storefront product search; admin or internal wiki search | logs and analytics; billions of documents |
| **Typesense** | open (GPLv3) | schema'd documents; in-memory index; built-in vectors and semantic search; Raft cluster in the free version | catalog search with fault tolerance | an index larger than RAM |

### VEC — vector
Store embeddings and find nearest neighbours by meaning; approximate indexes (HNSW, IVF) trade a little accuracy for big speed. The base of RAG and semantic search.

| Engine | Licence | Inside | Good for | Bad for |
|---|---|---|---|---|
| **pgvector** — not a separate database, the first candidate | open (PostgreSQL) | `vector` column in a normal table; HNSW and IVFFlat, quantisation; ACID; vectors next to data, so access-rights filters and joins in one query | company-document RAG up to ~tens of millions of vectors; when access rights to chunks matter | hundreds of millions of vectors with strict latency; complex filtering + vectors at huge volume |
| **Qdrant** | open (Apache 2.0) | Rust; points = vector + payload; REST/gRPC; payload filtering inside the HNSW walk; sparse vectors for hybrid, multivectors, quantisation; sharding and replicas | RAG with filters (tenant, date, type); embedding recommendations | few vectors (pgvector is enough); source of truth |
| **Weaviate** | open (BSD-3) | objects with vectors; GraphQL, REST, gRPC; calls embedding models on insert; hybrid BM25 + vectors; multi-tenancy | quick start of semantic search with ready modules | you want full control of embeddings (modules are extra) |
| **Milvus** | open (Apache 2.0) | distributed, separate query/data/index services, S3 storage, GPU indexes; Milvus Lite | billions of vectors, GPU search | small projects (many components) |

### STREAM — next to databases: streams
Often called databases, but they are event logs: they move data between services and keep history for re-reading. They do not query by content. The full broker picture is in `brokers.md`.

| Engine | Licence | Good for | Bad for |
|---|---|---|---|
| **Apache Kafka** | open (Apache 2.0) — topics → partitions → ordered log; exactly-once between topics; KRaft (no ZooKeeper) since 4.0; base for CDC (Debezium) and streaming into ClickHouse | an event bus between services; CDC from a database to analytics and search | a plain job queue (RabbitMQ / NATS / Valkey are simpler); searching messages |
| **NATS JetStream** | open (Apache 2.0) — one binary, small footprint; subjects, streams, built-in KV and object store; Raft cluster | messages between microservices and agents; edge and IoT | huge history for analytics (Kafka) |

## Clouds and managed services

Managed = the provider installs, upgrades, backs up and watches the database. You pay more for hardware but keep no on-call DBA. Key questions: where the data physically lives, how backups and PITR work, the cost of egress, how easy it is to move back.

**AWS** — the widest choice. Minuses: complex billing, expensive egress, strong lock-in on its own engines (DynamoDB, Aurora DSQL).

| Service | What | When |
|---|---|---|
| RDS | Postgres, MySQL, MariaDB, Oracle, SQL Server, Db2 | normal projects, "Postgres without an admin" |
| Aurora | Postgres/MySQL-compatible, storage separated from compute | high load, fast replicas, serverless mode |
| Aurora DSQL | distributed Postgres-compatible serverless SQL | multi-region ACID without your own cluster |
| DynamoDB | own KV/document, serverless | huge load with known queries; bad for ad-hoc |
| DocumentDB | MongoDB API (incomplete) | Mongo code in AWS |
| ElastiCache / MemoryDB | Valkey, Redis, Memcached; MemoryDB with a durable log | cache / in-memory as the primary store |
| Keyspaces | Cassandra-compatible serverless | Cassandra without operations |
| Neptune | Gremlin, openCypher, SPARQL | knowledge graph in AWS |
| Timestream | time series, InfluxDB option | metrics and IoT |
| Redshift | DWH | BI and analytics |
| OpenSearch Service | search and logs, serverless option | search, SIEM |
| S3 Vectors | vectors in object storage | cheap storage of large vector sets |

**Yandex Cloud** — good for the CIS: roubles/tenge, closeness to users, Russian-speaking support, Terraform. Renamed services: MongoDB → **StoreDoc**, Redis → **Valkey**. For government and bank clients in KZ, check separately where the data is physically stored.

| Service | What | When |
|---|---|---|
| Managed PostgreSQL | Postgres with extensions | the default |
| Sharded PostgreSQL | sharded Postgres through a router | Postgres that no longer fits one cluster |
| Managed MySQL | MySQL | PHP stack, CMS |
| StoreDoc | MongoDB-compatible (formerly Managed MongoDB) | document data |
| Managed Valkey | Redis-compatible (formerly Managed Redis) | cache, sessions, queues |
| YDB | distributed SQL, serverless with pay-per-request | scalable backends, serverless |
| Managed ClickHouse | columnar analytics | event analytics, logs |
| MPP Analytics for PostgreSQL | Greenplum | large corporate DWH |
| YTsaurus | Yandex big-data platform (MapReduce, dynamic tables) | petabytes and data processing |
| Managed OpenSearch | search and logs | search, SIEM |
| Managed Kafka | event broker | event bus, CDC |

**DigitalOcean** — simple and predictable pricing: PostgreSQL (pooling built in), MySQL, MongoDB, Valkey (drop-in Redis replacement), Kafka, OpenSearch. No exotic or proprietary engines, so leaving is easy. Good for MVPs, small SaaS and client projects.

**Others worth knowing:**

| Service | What | When |
|---|---|---|
| Supabase | Postgres + auth + storage + realtime + edge functions | MVP backend without your own server; Postgres stays Postgres |
| Neon | serverless Postgres with git-like branches (bought by Databricks) | preview environments, databases for agents |
| PlanetScale | Vitess MySQL and Postgres, no-downtime migrations | large MySQL/Postgres in production |
| Cloudflare D1 / KV / Durable Objects | SQLite at the edge, global KV, stateful objects | Workers apps, low latency worldwide |
| Turso | libSQL (SQLite fork), a database per user | thousands of small isolated databases |
| MongoDB Atlas | official Mongo cloud + vectors and search | Mongo in production without operations |
| Google Cloud | Cloud SQL, AlloyDB, Spanner, Firestore, Bigtable, BigQuery | Spanner = global SQL, BigQuery = analytics |
| Azure | Azure SQL, Cosmos DB (many APIs), Database for PostgreSQL | Microsoft stack |
| ClickHouse Cloud, Snowflake | analytics as a service | DWH without your own clusters |
| Upstash, Pinecone | serverless Redis / vectors, pay per request | small loads, functions, RAG |

## Task → default → when to switch

| Task | Default | Switch when |
|---|---|---|
| Normal backend, CRM, shop | PostgreSQL | almost never; replicas and pooling first |
| Cache, sessions, rate limit | Valkey | huge cache on one machine → Dragonfly |
| Background jobs | Postgres table (`SKIP LOCKED`) or Valkey streams | an event bus between teams → Kafka / NATS |
| Event analytics, clickstream | ClickHouse | many joins in BI → StarRocks |
| Infrastructure metrics | VictoriaMetrics | — |
| Business metrics next to data | TimescaleDB | millions of series → VictoriaMetrics |
| Site catalog search | Meilisearch | complex ranking → OpenSearch |
| Logs and SIEM | OpenSearch or ClickHouse | cheaper at volume → ClickHouse |
| RAG and semantic search | pgvector | hundreds of millions of vectors or complex filters → Qdrant |
| Knowledge graph, contact relations | Postgres with recursive CTEs | deep traversals and algorithms → Neo4j / Memgraph |
| Multi-region ACID | YugabyteDB | in AWS → Aurora DSQL; Cockroach if the licence fits |
| Huge writes with known queries | ScyllaDB / Cassandra | — |
| Config, leader election | etcd | — |
| Offline sync with clients | CouchDB + PouchDB | — |
| Analytics over files | DuckDB | shared team access → ClickHouse |
