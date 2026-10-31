# Layer: coordination and configuration

Source: Alexey's «Координация и конфигурация» (checked 30 October 2026). How services find each other, where settings come from, how not to do one job twice, and how to switch features without a deploy: service discovery, distributed config, locks and leader election, feature flags, distributed application runtimes. Free/paid boundaries of flag tools move often — check the licence of the exact image.

Marks: licence **open / src / prop**; status **base / pop / grow** (grow = young, carries risk).

## Concepts

- **Consensus.** For nodes to agree on a leader or a value: Raft or Paxos. Quorum = majority, so use an odd count (3 or 5); three nodes survive losing one.
- **Fencing token.** A distributed lock can expire while the process still thinks it holds it (GC pause, network). Defence: a number that grows with every grant; **storage rejects writes carrying an old token**.
- **Flag ≠ config.** Config = how the system works (addresses, limits, timeouts). Feature flag = who sees a feature and when (percentage, segment, kill switch). Flags have a lifetime; **stale flags are technical debt**.

## Rule 0

Kubernetes already has discovery (service DNS names), leader election (Lease) and config (ConfigMap). For locks in an ordinary backend, **Postgres advisory locks** are enough. A separate Consul or ZooKeeper is needed when services live outside k8s on different machines. Flags can live in config at first; a flag service is needed when percentages, segments and non-developers managing them appear.

## Classes and technologies

### DISCOVERY — service discovery and distributed KV
A registry of where each service lives and whether it is healthy, plus a small strongly consistent store. Consensus-based: good for **small, important** data, bad for large data.

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **etcd** | open (Apache 2.0) · base | versioned KV, watch, lease; Raft; 3–5 nodes, gigabytes not terabytes; 3.6 (May 2025): memory at least halved, v2store removed, first official downgrade, feature gates; Lease TTL + compare-and-swap for election and locks | coordination, leader election, small config; your own control plane | user data; frequent writes of large values |
| **Consul** | src (BSL 1.1, HashiCorp → IBM) · base | service catalog + KV; Raft on servers, gossip between agents; DNS and HTTP API, health checks; agent per machine registers services; consul-template re-renders configs; multi-DC; many are leaving for open alternatives | VMs and bare metal without k8s; mixed environments, Nomad | k8s only (DNS and etcd already there); an open licence |
| **Apache ZooKeeper** | open (Apache 2.0) · base | znode hierarchy, ephemeral and sequential nodes; ZAB; Curator recipes (locks, barriers, election); Kafka dropped it (KRaft), still in ClickHouse (Keeper replaces it), Hadoop, Solr | maintaining existing systems on it | new projects (etcd is simpler) |
| **Nacos** | open (Apache 2.0, Alibaba) · pop | service registry + config centre; Raft for CP, Distro for AP; HTTP/gRPC, Spring Cloud and Dubbo; 3.x also registers MCP servers and AI agents | Spring Cloud / Dubbo microservices; registry and config in one | non-Java stacks; a k8s-native approach |
| **Kubernetes DNS + Lease** | open (Apache 2.0) · base | Service → DNS name via CoreDNS (`my-svc.my-ns.svc.cluster.local`), EndpointSlices, kube-proxy or Cilium balancing; Lease for controller election (client-go leaderelection) — **Rule 0 for discovery in k8s** | everything in one cluster | services outside the cluster or across clusters without extra tools |

### CONFIG — distributed configuration
Settings separate from code, with versions, environments and reload without a deploy. **Secrets do not belong here** — they go to a secret manager (see `access.md`).

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **ConfigMap + Reloader / GitOps** | open (Apache 2.0) · base | ConfigMap in git → Argo CD / Flux → cluster; Stakater Reloader does a rolling restart on change; history and audit via git and pull requests; rollback = `git revert` | k8s and GitOps; config that changes at most daily | live changes without a restart |
| **Consul KV + consul-template** | src (BSL 1.1) / MPL 2.0 (template) · base | KV tree; watch → re-render file → reload service; no built-in versions, limited audit | VM infrastructure on Consul | new projects without Consul |
| **Spring Cloud Config** | open (Apache 2.0) · base | Git, Vault, JDBC sources; `@RefreshScope`, Spring Cloud Bus; profiles per environment, value encryption | Spring Boot microservices | non-JVM stacks |
| **Apollo Config** | open (Apache 2.0, from Ctrip) · pop | apps → environments → clusters → namespaces; real-time push; releases with rollback, grey release to part of the instances; web UI with rights and approvals; audit | many services and non-developers changing settings | small projects |

### LOCKS — locks and leader election
Patterns, not products: make sure a cron job runs on one instance, not five; pick a primary among replicas. **Main mistake: treating a distributed lock as absolute. Use fencing tokens and idempotency.**

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Postgres advisory locks** | open · base | `pg_try_advisory_lock(key)`; released when the session drops; whoever holds it is the leader; transaction-level variants exist. **Gotcha: PgBouncer transaction pooling breaks session locks** | one cron executor among replicas; protecting migrations from parallel runs | services without a shared database |
| **Kubernetes Lease** | open · base | Lease object with holderIdentity and duration via etcd; client-go leaderelection, controller-runtime. **The leader must stop working if it fails to renew** | operators and singleton services in k8s | outside k8s |
| **etcd / ZooKeeper election** | open · base | Lease + key revision (etcd), ephemeral sequential znodes (ZK); election APIs, Curator LeaderLatch; **etcd revision grows monotonically — a ready fencing token** | critical coordination where double execution is unacceptable | simple tasks (Postgres is enough) |
| **Valkey / Redis lock** (`SET NX`, Redlock) | open (BSD-3 Valkey) · pop | `SET key value NX PX ttl`; Redlock across several nodes; no consensus, depends on clocks and persistence; without a fencing token correctness is not guaranteed (Kleppmann's Redlock critique) | locks as an **optimisation**: task dedup, rate limit, "don't recompute the cache in parallel" | money, stock levels, anything where double execution breaks data |

### FLAGS — feature flags and remote config
Switch features without a deploy: gradual rollout by percentage, segments, A/B tests, kill switch. API standard: **OpenFeature** — code targets it, the provider (Unleash, Flagsmith, flagd) can change without rewriting.

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **OpenFeature + flagd** | open (Apache 2.0, CNCF incubating) · pop | OpenFeature is an interface, not storage: one SDK + providers; flagd reads flags from a file, k8s CRD or HTTP, evaluates locally (sidecar or in-process); no UI — flags as JSON in git with review | vendor independence; flags as code in GitOps | product managers needing a UI with segments (add a provider with UI) |
| **Unleash** | open (AGPLv3 current versions, early ones Apache 2.0; + Enterprise) · base | flags, activation strategies, variants, environments; SDK evaluates from cache, Unleash Edge for scale; UI, history, stale-flag hints; SSO, change requests, advanced rights paid | a team needing a UI and gradual rollouts; self-hosted flags | A/B analysis with metrics (GrowthBook is stronger) |
| **Flagsmith** | open (BSD-3 + Enterprise) · pop | flags + values (remote config) by user traits, segments; remote or local evaluation; UI | mobile apps and remote config; self-hosted with a permissive licence | deep experiment statistics |
| **GrowthBook** | open (MIT + enterprise dirs) · pop | flags + A/B experiments; local SDK evaluation; **metrics computed by SQL over your own warehouse** (ClickHouse, BigQuery, Postgres), no events sent to a vendor; Bayesian and frequentist stats | A/B tests with honest statistics; having your own event store | plain on/off only |
| **Flipt** | src (Fair Core License → MIT after 2 years; SDKs MIT) · grow | v2: flags stored in a git repo, branches as environments; UI commits to a branch; server or client SDKs, SSE updates; FCL forbids a competing SaaS; Pro (GitHub/GitLab integrations, MRs from UI, commit signing) paid | GitOps teams wanting flags with review | embedding Flipt in a product for clients without an Enterprise licence |
| **PostHog flags** | open (MIT core; cloud SaaS) · pop | flags, experiments, surveys tied to the same users and events as PostHog analytics | a startup already on PostHog analytics | large-scale self-hosting (PostHog is heavy) |
| **LaunchDarkly** | prop (SaaS) · base | flags, experiments, release pipelines, streaming to SDKs; the fullest feature set; expensive, data at the vendor | a large company with budget | startups and self-hosted requirements |

### RUNTIME — distributed application runtimes
Handle typical distributed-system tasks (service calls, state, pub/sub, actors, workflows) behind a standard API; the concrete infrastructure (Kafka, Valkey, Postgres) is plugged in by config. **Virtual actors** = a stateful entity that lives "somewhere" in the cluster.

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Dapr** | open (Apache 2.0, CNCF graduated) · pop | sidecar with building blocks: invocation, state, pub/sub, actors, workflows, secrets, conversation (LLM); any language over HTTP/gRPC, SDKs for Go, Java, .NET, Python, JS; components for Kafka, Valkey, Postgres, clouds; 1.16 (September 2025): cross-app workflows, faster workflows, SSE and MCP proxying, tool calling, JWT/OIDC workload identity | polyglot microservices with one approach; swapping broker or database without code changes | a monolith or a couple of services (extra layer); fine-grained broker-specific features |
| **Microsoft Orleans** | open (MIT) · base | .NET grains — virtual actors with state; silo cluster, state in databases; activates an entity on access wherever it lives; Xbox, Azure | games, IoT, live state of millions of entities on .NET | non-.NET |
| **Akka / Apache Pekko** | Akka src (BSL since 2022); Pekko open (Apache 2.0, ASF fork) · base | actors, cluster, sharding, persistence on the JVM (Scala, Java) | JVM systems with an actor model | a new project without actor expertise |

## Clouds

Clouds give the least here. Discovery is usually the platform's internal DNS; feature flags exist only at AWS (AppConfig) and Azure (App Configuration). Cloud-bound flags must move on migration — **write code against OpenFeature**.

**Migration targets:**

| Cloud | Service | What | When |
|---|---|---|---|
| Yandex Cloud | Cloud DNS private zones | internal service names | discovery for VMs |
| | Managed Kubernetes | CoreDNS, Lease, ConfigMap | discovery and config in the cluster |
| | Lockbox | secrets and sensitive config | settings with secrets |
| | VM metadata / Instance Groups | config at startup, autoscaling | VM config |
| | (no discovery or flag service; ZooKeeper only inside Managed ClickHouse and Kafka) | — | — |
| DigitalOcean | VPC + private DNS | network and names for Droplets | discovery |
| | DOKS | standard k8s | discovery, Lease, ConfigMap |
| | App Platform env | per-component env vars | PaaS config |
| Railway | Private Networking (`*.railway.internal`) | internal DNS between services | discovery |
| | Shared and reference variables | shared config and cross-service references | config |
| | Environments / PR environments | separate project environments (partly replace infra-level flags) | isolating changes |
| | Unleash / Flagsmith / GrowthBook templates | flag service in the project | feature flags |

**Industry standard:**

| Cloud | Services |
|---|---|
| AWS | Cloud Map / ECS Service Connect (discovery outside EKS); AppConfig (config and flags with validation, gradual rollout and alarm-based auto-rollback); Parameter Store (hierarchical config); DynamoDB conditional writes (locks and election for serverless) |
| Google Cloud | Service Directory; Firebase Remote Config (client flags and values, A/B); Cloud DNS private zones |
| Azure | App Configuration (config + flags, labels, snapshots, audience filters; .NET and Spring); Private DNS; Blob lease as a lock for election |
| Cloudflare | Workers KV (global eventually consistent config read at the edge in ms); **Durable Objects** (one stateful instance worldwide — ready-made coordination and locks); service bindings (Worker-to-Worker calls without the network) |

## Task → default → when to switch

| Task | Default | Switch when |
|---|---|---|
| Discovery in Kubernetes | service DNS (built in) | multi-cluster → Cilium Cluster Mesh or a mesh |
| Discovery on VMs without k8s | Consul | open licence → DNS + own health checks, or etcd |
| Config in k8s | ConfigMap in git + Reloader | live changes many times a day → flags or Apollo |
| Config for Spring microservices | Spring Cloud Config | UI with rights → Apollo or Nacos |
| One cron executor among replicas | Postgres advisory lock | in k8s → Lease |
| Double execution unacceptable | etcd election + fencing token | — |
| "Don't do the work twice" as an optimisation | Valkey `SET NX` with TTL | — |
| Flags without vendor lock-in | OpenFeature SDK + a provider | — |
| Flags as code with review | flagd or Flipt | — |
| Flags with a UI for the team | Unleash | permissive licence → Flagsmith |
| A/B tests with honest statistics | GrowthBook | already on PostHog → its experiments |
| Flags in AWS | AppConfig through an OpenFeature provider | — |
| Polyglot microservices with shared patterns | Dapr | — |
| Live state of millions of entities | Orleans (.NET) / Durable Objects (edge) | JVM → Pekko |
