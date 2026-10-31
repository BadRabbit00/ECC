# Layer: files, objects and data lake

Source: Alexey's «Файлы, объекты и data lake» (checked 30 October 2026). Where to keep images, documents, backups, datasets and build artifacts: S3-compatible stores, table formats, catalogs, query engines, block and file storage for containers. A lot changed in a year (MinIO closed, Cloudflare renamed services) — check project status before production.

Marks: licence **open / src / prop**; status **base / pop / grow** (grow = young, carries risk).

## Concepts

- **Block · file · object.** Block = a disk one machine sees (EBS, Volume). File = a shared NFS folder several machines see. Object = a file with a key and metadata over HTTP via the S3 API; scales almost infinitely, cannot be appended in pieces.
- **Lakehouse.** Parquet in S3 alone is a pile of files. A table format (Iceberg, Delta) adds transactions, schema, version history and row deletes; a catalog remembers where each table's current version is.
- **Bucket security.** Public buckets are a common leak. **Everything private by default**; serve via presigned URL or CDN. For backups enable **versioning and object lock**, so ransomware cannot erase them.

## Rule 0

User files go to **object storage**, not into the database and not onto the server disk. The database keeps only the key and metadata. A data lake is not needed while analytics fits ClickHouse or Postgres; it appears when there are terabytes and several engines work with them.

## Classes and technologies

### S3 — self-hosted object stores
Servers speaking the Amazon S3 API: erasure coding (redundant chunks across nodes), versioning, lifecycle rules, presigned URLs. Any S3 client works: SDKs, rclone, restic.

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **MinIO** | src (AGPLv3, **archived**) · base | timeline: May 2025 admin console removed from open version; Oct 2025 no more binaries/images; Dec 2025 maintenance mode; Feb 2026 "no longer maintained"; Apr 2026 repo archived, development moved to paid AIStor. Existing installs run, **no security patches** | only existing installs during migration | any new project; anything internet-facing |
| **SeaweedFS** | open (Apache 2.0) · pop | 10+ years active; Facebook Haystack model — small files packed into large volumes, one disk seek per small read; S3, FUSE, WebDAV, HDFS, Iceberg catalog; master + volume servers + filer (metadata in Postgres, Redis…); replication, EC for cold data. The most common MinIO replacement | millions of images and thumbnails; replacing MinIO in production; backups and artifacts | one-config simplicity (Garage is simpler); every rare S3 feature |
| **Garage** | open (AGPLv3) · pop | Rust, v2.x by non-profit Deuxfleurs; built for imperfect networks and several sites; CRDTs, no consensus per write; replication across 3 zones, no EC; low resources; S3 + K2V. AGPL: modified code offered as a service must be published | storage across 2–3 sites without your own DC; homelab and small companies; backups between offices | huge volumes where EC savings matter; all S3 features (object lock etc.) |
| **RustFS** | open (Apache 2.0) · grow | 1.0 GA in September 2026; MinIO-like architecture and UX (easier migration); S3, WebDAV, Swift, FTP, MCP, Iceberg REST catalog; EC, self-healing, replication, rebalancing; IAM, OIDC, KMS, SSE, multi-tenancy, OpenTelemetry. Only a few years old | "like MinIO" with an open licence; new projects ready for a fresh product | conservative production needing years of track record; critical data without a fallback plan |
| **Ceph RGW** | open (LGPL 2.1/3) · base | mature, Tentacle (v20); S3 + Swift on Ceph; one cluster gives blocks (RBD), files (CephFS) and objects (RGW); CRUSH places data without a central table; Rook for k8s; petabytes; needs an experienced team and 3–5+ servers | your own cloud or large DC; one store for VM disks, files and S3 | small projects; no one who can fix Ceph at night |
| **S3Proxy / LocalStack** | open (Apache 2.0, S3Proxy) · pop | S3Proxy exposes a local folder as S3; LocalStack emulates AWS services; not for production | CI and integration tests | real data |

### TABLE — table formats (lakehouse)
Metadata over Parquet in S3: ACID, schema evolution, time travel, row deletes for GDPR. Iceberg has mostly won the open-standard fight.

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Apache Iceberg** | open (Apache 2.0) · base | snapshots → manifests → Parquet/ORC/Avro; hidden partitioning, schema evolution, time travel; spec v3: binary deletion vectors, VARIANT type, row lineage (Snowflake, Databricks, DuckDB support v3); read by Spark, Trino, Flink, DuckDB, ClickHouse, Snowflake, BigQuery; native in S3 Tables, BigLake, Basin Catalog | a data lake used by several engines; cheap long-term analytics in S3 | small volumes (ClickHouse or Postgres are simpler); frequent point updates like OLTP |
| **Delta Lake** | open (Apache 2.0, Linux Foundation) · base | `_delta_log` + Parquet; MERGE, time travel, Change Data Feed; Delta 4.x; UniForm lets the same tables be read as Iceberg; Spark, Databricks, delta-rs, Trino | Databricks and Spark stacks | a multi-engine platform without Databricks (Iceberg is broader) |
| **Apache Hudi** | open (Apache 2.0) · base | from Uber for frequent CDC updates; copy-on-write or merge-on-read; record indexes, incremental queries; smaller community | a constant stream of CDC updates into the lake | new projects without special upsert needs (→ Iceberg) |
| **DuckLake** | open (MIT) · grow | 1.0 since April 2026; Parquet in S3 + **catalog in Postgres, SQLite or DuckDB** — no separate catalog service; transactions, snapshots, time travel, encryption; DuckDB is the main engine | your own small lakehouse on DuckDB + Postgres + S3; file analytics for agents | many engines (Spark, Snowflake) → Iceberg |
| **Apache Paimon** | open (Apache 2.0) · grow | from Flink Table Store; LSM tree on object storage; streaming upserts, changelog; Flink, Spark, Trino, StarRocks | Flink pipelines with upserts into the lake | no Flink in the stack |
| **Lance** | open (Apache 2.0) · grow | versioned columnar files with fast random row access (much faster than Parquet), vector indexes, multimodal data; LanceDB, DuckDB, Spark, Ray, pandas/Polars | training and RAG datasets; images + text + vectors | classic BI (→ Parquet and Iceberg) |

### CATALOG — table catalogs
A catalog stores which table version is current and swaps it atomically. Protocol standard: **Iceberg REST Catalog**. A good catalog also vends temporary S3 credentials and checks access rights.

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Apache Polaris** | open (Apache 2.0) · pop | opened by Snowflake, Apache TLP since February 2026; catalogs → namespaces → tables; Iceberg REST; central access policies; vendor-neutral (Spark, Trino, Flink, Snowflake, Dremio) | a shared catalog across engines and clouds | one DuckDB on a laptop |
| **Lakekeeper** | open (Apache 2.0) · grow | Rust, one binary + Postgres; Iceberg tables and views; credential vending; OpenFGA, OIDC | a self-hosted lake with proper authorisation | needing a big vendor behind it |
| **Unity Catalog (OSS)** | open (Apache 2.0, LF AI & Data) · pop | tables, volumes, functions, ML models; own API + Iceberg REST; grants; fullest inside Databricks, OSS is thinner | Databricks-oriented teams | self-hosted without Databricks (Polaris or Lakekeeper are simpler) |
| **Project Nessie** | open (Apache 2.0) · pop | git for data: branches, tags, commits across all tables, atomic multi-table merges; Iceberg REST + own API; by Dremio (now part of SAP) | isolating experiments, validating data before publishing | a plain catalog without branches |
| **Hive Metastore** | open (Apache 2.0) · base | Thrift, Ranger for rights; legacy in old Hadoop/Spark clusters | compatibility with an old stack | new projects |

### QUERY — engines over the lake
Store no data; read Parquet and Iceberg from S3 and run SQL. Storage separated from compute; different engines on the same data.

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Trino** | open (Apache 2.0) · base | Presto fork by its authors; MPP coordinator + workers; Iceberg, Delta, Hive, Postgres, MySQL, Kafka, ClickHouse…; **federated joins across systems**; Starburst is the commercial version | SQL access to the lake for analysts; joins across different systems | small data (DuckDB is faster and simpler); OLTP |
| **Apache Spark** | open (Apache 2.0) · base | distributed DataFrames, task DAGs; ETL, ML, streaming in one API; Spark 4: Spark Connect thin client, VARIANT, Python improvements; k8s, YARN, clouds | heavy ETL over terabytes; ML data preparation | sub-second interactive queries; small data |
| **DuckDB** | open (MIT) · pop | in-process columnar; Parquet, Iceberg v3 read/write, Delta, DuckLake, CSV, S3; replaces a Spark or Trino cluster for many tasks | lake analytics up to hundreds of GB; notebooks, scripts, agents | a shared server for many users |

### BLOCK/FS — block and file storage
When a program needs a real disk or a shared folder: databases in k8s, legacy apps, ML training. In k8s this is a PersistentVolume via a CSI driver.

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Longhorn** | open (Apache 2.0, CNCF) · pop | SUSE/Rancher; block over iSCSI/NVMe-oF; RWO, RWX via NFS; volume replicas on different nodes; snapshots, S3 backup, UI; one-command install | your own k8s cluster without a SAN; volume backups to S3 | databases with very high IOPS needs |
| **Ceph RBD / CephFS** | open (LGPL 2.1/3) · base | block (RBD) and POSIX file (CephFS) from one cluster; RWO and RWX; snapshots, clones, mirroring; Rook in k8s; base of many OpenStack and Proxmox clouds | a large own cluster, Proxmox, OpenStack | small teams |
| **JuiceFS** | open (Apache 2.0 Community) · pop | POSIX over S3: file blocks in S3, tree in Redis/Postgres/TiKV; FUSE, CSI, S3 gateway, HDFS API; local disk cache; popular for ML datasets and checkpoints | shared datasets for GPU nodes; a legacy app that needs a folder while data stays in S3 | databases on it |
| **NFS** | open (Linux kernel protocol) · base | RWX everywhere, managed in every cloud; trouble with file locking and many small files | shared files for several servers; managed cloud NFS | databases; heavy small-file loads |

## Clouds

The S3 API is almost everywhere, so objects move easily (rclone). **Egress is what costs**: classic clouds charge noticeably for terabytes out; R2 and Railway Buckets have free egress from the bucket.

**Migration targets:**

| Cloud | Service | What | When |
|---|---|---|---|
| Yandex Cloud | Object Storage | S3-compatible; standard / cold / ice classes, lifecycle, versioning, object lock, static site hosting | user files, backups, static content |
| | Cloud CDN | serving from Object Storage | media delivery |
| | Network disks | block disks for VMs, snapshots | server and database disks |
| | Data Processing | managed Spark | lake processing |
| | YTsaurus | big-data platform | petabytes |
| DigitalOcean | Spaces | S3-compatible with built-in CDN, bundled storage + traffic price | files, media, backups |
| | Volumes | block disks for Droplets and DOKS | database and service data |
| | Network File Storage | managed NFS | shared folders |
| Railway | Buckets | **private** S3-compatible, $0.015/GB-month, API requests and egress free. Limits: no public buckets (serve via presigned URL or proxy), no versioning, object lock, lifecycle or SSE yet; deleted bucket restorable for 52 hours | user uploads, exports |
| | Volumes | persistent disk attached to a service | template databases |
| | SeaweedFS / Garage / RustFS templates | your own S3 in the project | when Buckets lacks a feature |

**Industry standard:**

| Cloud | Services |
|---|---|
| AWS | S3 (classes, Intelligent-Tiering, object lock — the API reference); S3 Express One Zone (low latency, ML training, hot data); S3 Tables (managed Iceberg with auto-compaction); Glacier (archives); EBS / EFS / FSx (block / NFS / Lustre, Windows, ONTAP); Glue Data Catalog + Athena (catalog + serverless SQL) |
| Google Cloud | Cloud Storage (classes, Autoclass); BigLake (Iceberg for BigQuery and Spark); Filestore (NFS); Persistent Disk / Hyperdisk |
| Azure | Blob Storage (hot, cool, cold, archive); ADLS Gen2 (hierarchical namespace for analytics); Azure Files / NetApp Files (SMB, NFS); Managed Disks; OneLake in Fabric |
| Cloudflare | R2 (S3-compatible, **no egress fees**); since October 2026 the data platform is GA as **Basin**: Basin Catalog (managed Iceberg REST, ex-R2 Data Catalog), Basin SQL (ex-R2 SQL), Basin Pipelines; Images / Stream for media |

## Task → default → when to switch

| Task | Default | Switch when |
|---|---|---|
| User uploads in an app | S3 of the cloud we deploy to (Spaces, Object Storage, Buckets) | many downloads → Cloudflare R2 |
| Own S3 on own servers | SeaweedFS | 2–3 sites and few resources → Garage; "like MinIO" → RustFS |
| Leaving MinIO | SeaweedFS or RustFS | — |
| Own large DC: disks + files + S3 | Ceph (Rook in k8s) | — |
| Backups | S3 with versioning and object lock + restic | archive for years → cold classes (Glacier, Yandex ice) |
| Analytics over files | DuckDB + Parquet in S3 | — |
| Small own lakehouse | DuckLake (Postgres + S3) | several engines → Iceberg |
| Data lake for several engines | Iceberg + REST catalog (Polaris / Lakekeeper) | Databricks → Delta + Unity Catalog |
| Managed lakehouse without servers | S3 Tables / BigLake / Basin Catalog | — |
| SQL over the lake and other databases | Trino | small data → DuckDB |
| ML and multimodal datasets | Lance | — |
| Disks for own k8s | Longhorn | large cluster → Ceph |
| Shared folder for GPU nodes | JuiceFS | in a cloud → managed NFS |
| S3 in CI and tests | S3Proxy / LocalStack | — |
