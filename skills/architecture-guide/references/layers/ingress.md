# Layer: traffic ingress

Source: Alexey's «Вход трафика» (checked 30 October 2026). How a request reaches the app: reverse proxies and load balancers, Kubernetes ingress, API gateways, service mesh, CDN, tunnels for servers without a public IP. In the last year ingress-nginx and free Kong closed — check project status before production.

Marks: licence **open / src / prop**; status **base / pop / grow** (grow = young, carries risk).

## Concepts

- **L4 vs L7.** L4 balances TCP/UDP without looking inside — fast, any protocol. L7 understands HTTP: routes by path and headers, terminates TLS, rewrites requests.
- **North–South vs East–West.** North–South = outside in (proxy, API gateway, CDN). East–West = between services (mesh, mTLS, policies). Different tasks, different tools.
- **Gateway API** — the new Kubernetes standard replacing Ingress: infra owns `Gateway`, teams own their `HTTPRoute`; supports TCP, gRPC and weights for canaries.

## Rule 0

Most projects need **one reverse proxy with automatic TLS (Caddy or Traefik) and a CDN in front**. An API gateway is needed when the API is sold to external clients with keys, plans and limits. A service mesh is needed when there are dozens of services and manual mTLS no longer holds.

## Classes and technologies

### PROXY — reverse proxies and load balancers
TLS termination, balancing, health checks, compression, cache, rate limiting. Automatic ACME certificates in the proxy are the new norm.

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Nginx** | open (BSD-2, F5) · base | event-driven workers, tens of thousands of connections per core; L7 + L4 stream; reload by signal; TLS manual/certbot, ACME module since 2025; C modules, njs, OpenResty (Lua). Plus adds active health checks, live API, dashboard | static files and caching; a classic proxy in front of an app; teams that know it | dynamic backends without reloads (Traefik or Envoy are easier); automatic TLS with zero effort (→ Caddy) |
| **Angie** | open (BSD-2) · grow | Nginx fork by its former developers, Nginx-compatible config; built-in ACME, status API, Prometheus metrics, active health checks, Docker integration, HTTP/3; popular in the CIS, in the Russian software registry | Nginx with Plus features for free; migrating from Nginx without rewriting configs | smaller international community than Nginx |
| **Caddy** | open (Apache 2.0) · pop | Go (memory-safe); Caddyfile or live JSON API; **ACME out of the box**, on-demand TLS issues a cert on the first request to a new domain; L4 via plugin; xcaddy builds | most small and medium projects; SaaS with customer custom domains; fast production without a DevOps team | extreme loads where every microsecond counts; complex L4 balancing |
| **Traefik** | open (MIT) · pop | discovers services from Docker labels, k8s CRDs, Gateway API, files; L7 + TCP/UDP; ACME; v3: Gateway API, HTTP/3, OpenTelemetry, WASM plugins; dashboard; popular after ingress-nginx closed | Docker Compose/Swarm with automatic routes; k8s Ingress or Gateway; homelab and small clusters | very complex routing logic (Envoy is more flexible) |
| **HAProxy** | open (GPLv2) · base | L4 + L7; Data Plane API; detailed metrics and logs; stick tables for rate limiting and bot defence; Lua, SPOE; ACME in new versions; excellent L4 for databases (Postgres, Galera) | high-load ingress; L4 for databases and TCP services; fine-grained abuse protection | dynamic container environments without extra work |
| **Envoy** | open (Apache 2.0, CNCF) · base | programmable L4/L7, gRPC, HTTP/3; YAML or dynamic xDS; mTLS with certs from a control plane; C++, Lua, WASM filters, ext_authz; retries, circuit breaker, outlier detection. Rarely hand-configured — driven by Istio, Envoy Gateway, cloud LBs | the base for your own gateway or mesh; gRPC services | hand config for a simple site (too verbose) |
| **Pingora** | open (Apache 2.0) · grow | a Rust **framework** from Cloudflare (replaced Nginx in their network), not a ready proxy; River is built on it | your own high-load proxy with special logic | needing a ready proxy, not code |

### K8S-IN — Kubernetes ingress
Controllers that turn Ingress or Gateway API resources into proxy config. **ingress-nginx is closed; the industry is moving to Gateway API.**

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **ingress-nginx** | open (Apache 2.0, **archived**) · base | announced end in November 2025, best-effort until **March 2026**, then no releases or security fixes; existing installs run. Not the same as F5's NGINX Ingress Controller / Gateway Fabric, which live on | only old clusters during migration | any new install; anything internet-facing without a migration plan |
| **Envoy Gateway** | open (Apache 2.0) · pop | official Gateway API on Envoy without Istio's complexity; policy CRDs: rate limit, JWT/OIDC, ext_authz, WASM, AI Gateway; self-hosted Supabase moved here from Kong | a new standard k8s ingress; replacing ingress-nginx and Kong | no Kubernetes |
| **NGINX Gateway Fabric** | open (Apache 2.0, F5) · pop | Gateway API on Nginx (optionally Plus) | Nginx teams moving to Gateway API | advanced policies (Envoy Gateway is richer) |
| **Traefik as a gateway** | open (MIT) · pop | Ingress, IngressRoute CRD, Gateway API; default in k3s; can read ingress-nginx annotations for easier migration | k3s, small clusters; quick move off ingress-nginx | huge clusters with thousands of routes |

### API-GW — API gateways
Proxies that know APIs: keys and OAuth, plans and quotas, versions, transformations, developer portal — for an API that is a product for external clients or partners. New subclass: **AI gateway** (token limits, routing between LLMs).

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Kong Gateway** | src (OSS **frozen at 3.9.1**, security fixes only; 3.10+ without a licence behaves like an expired Enterprise) · base | Nginx + OpenResty (Lua); Admin API, decK, CRDs; hundreds of plugins incl. AI Gateway; bet on paid Konnect; Supabase left for Envoy | an already purchased Enterprise or Konnect | a new self-hosted project on the free version; a long-term bet on the OSS branch |
| **Apache APISIX** | open (Apache 2.0, ASF) · pop | Nginx + OpenResty, config in etcd changes live without reloads; Admin API, YAML mode, CRDs; 80+ plugins, plugins in Lua, Go, Python, Java, WASM; AI plugins — the closest open Kong replacement | an open Kong alternative; dynamic routing over many services | not wanting etcd (standalone mode has limits) |
| **KrakenD** | open (Apache 2.0 CE) · pop | stateless Go; one JSON config in git (GitOps); **aggregates several backends into one response (BFF)**; JWT, rate limit | BFF for mobile and frontend; a declarative gateway in git | developer portal and monetisation |
| **Tyk** | open (MPL 2.0 gateway) · pop | Go + Redis; keys, quotas, GraphQL (federation), plugins in Go/Python/JS; gateway fully open, dashboard and portal paid | an API product with keys and quotas; GraphQL federation | a simple proxy |

### MESH — service mesh
mTLS, retries, access policies and observability between services without code changes. Trend: away from per-pod sidecars to **ambient** and eBPF modes.

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Istio (ambient)** | open (Apache 2.0, CNCF graduated) · base | ztunnel per node (Rust, L4 + mTLS) + Envoy waypoint proxies for L7 only where needed; mTLS without pod restarts; authz, traffic management, multi-cluster; ambient is GA; still the most complex | dozens to hundreds of services with zero trust; canaries, mirroring | five services (mTLS is simpler otherwise); a team without k8s experience |
| **Linkerd** | open code (Apache 2.0); **stable builds by Buoyant are paid for companies over 50 people** (free edge releases or build from source) · pop | Rust sidecar micro-proxy; mTLS by default, metrics, retries, multi-cluster | mTLS and metrics with minimal setup; small and medium companies | 50+ people without budget and without wanting edge releases |
| **Cilium** | open (Apache 2.0, CNCF graduated) · pop | eBPF in the kernel + per-node Envoy for L7; CNI, L3–L7 policies (incl. DNS names), WireGuard/IPsec encryption, kube-proxy replacement, Hubble, Gateway API; default in many managed k8s | network and security of k8s in one tool | old Linux kernels; Istio's full L7 set |
| **Consul Connect** | src (BSL 1.1, HashiCorp → IBM) · base | sidecar Envoy + Consul; service discovery, mTLS, intentions across VMs, bare metal and k8s, Nomad; smaller community since the licence change | mixed VM + k8s environments, Nomad | k8s only (→ Istio or Cilium); an open licence |
| **Kuma** | open (Apache 2.0, CNCF sandbox) · grow | sidecar Envoy, multi-zone, mTLS, policies; Kong Mesh is the commercial version | VM + k8s with an open licence | large production needing a big community |

### CDN — CDN and edge
Servers worldwide cache content near users and absorb DDoS; modern CDNs also run code at the edge, issue certificates and filter bots. Key metric: **cache hit ratio**.

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Cloudflare** | prop (SaaS, free plan with CDN and DDoS protection) · base | anycast in hundreds of cities; CDN, DNS, WAF, DDoS, Workers, Tunnel, Zero Trust; cache rules, Tiered Cache; hides the origin IP. Risk: single-vendor dependence — Cloudflare outages take down much of the internet | almost any public site; DDoS protection without own infrastructure; edge logic on Workers | traffic that must stay and be processed in-country; not wanting to give TLS keys to a third party |
| **Fastly** | prop · pop | instant cache purge, Compute (WASM), WAF, VCL-heritage flexible caching; pricier, aimed at large clients | media with frequent content updates | small budgets |
| **bunny.net** | prop · grow | European, pay-per-traffic, very cheap; CDN, storage, video streaming, Edge Scripting | cheap media and static delivery | Cloudflare-level security suite |
| **Varnish** | open (BSD-2) · base | in-memory HTTP cache with VCL rules, ESI; no TLS termination (put Nginx, HAProxy or Hitch in front) | your own CDN node; a cache in front of a heavy CMS | no capacity to maintain your own cache infrastructure |

### TUNNEL — ingress without a public IP
Publish a service from an office, home or closed network without open ports; the server dials out. **Smaller attack surface**: no forwarded ports on the router.

| Tech | Licence · status | Inside | Good for | Bad for |
|---|---|---|---|---|
| **Cloudflare Tunnel** | cloudflared Apache 2.0, service SaaS · pop | cloudflared agent → Cloudflare; HTTP, SSH, RDP, TCP, private networks; with **Access** an SSO wall before any request; free basic tier | services in the office and on own hardware; admin panels behind SSO | traffic must not pass through a third party |
| **Pangolin** | open (AGPLv3) · grow | server on a VPS with a public IP + WireGuard agents; Traefik inside; built-in auth and SSO; HTTP, TCP/UDP | your own tunnel without a vendor; homelab, office services | global CDN and DDoS protection |
| **frp** | open (Apache 2.0) · base | frps + frpc; TCP, UDP, HTTP(S), STCP; tokens, TLS; no UI or SSO | quickly forwarding a port out of a closed network | user authentication in front of the service |
| **Tailscale Funnel** | prop (client partly open) · pop | publishes a tailnet service to the internet over WireGuard + relays; internal access should stay tailnet-only with ACLs | demos and webhooks to a local machine | high-load production ingress |

## Clouds

Cloud LB and API gateway configs do not move between clouds. **If migrations are frequent, keep routing in your own proxy (Caddy, Traefik, Envoy) and use the cloud LB as a plain L4 entry.**

**Migration targets:**

| Cloud | Service | What | When |
|---|---|---|---|
| Yandex Cloud | Application Load Balancer | L7 routing, TLS, Ingress controller and Gateway API for Managed Kubernetes | app and cluster ingress |
| | Network Load Balancer | L4 TCP/UDP | your own proxy behind it, databases |
| | API Gateway | gateway from an OpenAPI spec, serverless, calls functions and containers | API for functions and containers |
| | Cloud CDN | CDN for Object Storage and own origins | static and media |
| | Smart Web Security | WAF, DDoS and bot protection, limits; attached to ALB as a profile | protecting public services |
| | Certificate Manager + Cloud DNS | Let's Encrypt certs and DNS | TLS and domains |
| DigitalOcean | Load Balancers | L4/L7, TLS, health checks, regional and global | ingress for Droplets and DOKS |
| | App Platform | built-in HTTPS, domains, CDN | PaaS apps |
| | Spaces CDN | CDN for buckets | static |
| | Cloud Firewalls | network filtering | close everything except the LB |
| | (DOKS) | own ingress via Traefik, Envoy Gateway or Cilium | — |
| Railway | Public Networking | HTTPS domains with automatic TLS, custom domains, global edge | public ingress |
| | TCP Proxy | publishing TCP ports | databases, MQTT, game servers |
| | Private Networking | internal DNS between project services | service-to-service without the internet |
| | Static Outbound IPs | fixed egress addresses | APIs with IP allowlists |
| | Caddy / Traefik / gateway templates | own gateway in the project | complex routing |

**Industry standard:**

| Cloud | Services |
|---|---|
| AWS | ALB / NLB; API Gateway (REST, HTTP, WebSocket, keys and quotas); CloudFront + Lambda@Edge / CloudFront Functions; Global Accelerator (anycast IPs); VPC Lattice (East–West between VPCs and accounts without your own mesh) |
| Google Cloud | Cloud Load Balancing (global L7/L4 on one anycast IP); Cloud CDN / Media CDN; API Gateway (simple) / Apigee (enterprise with monetisation); GKE Gateway (native Gateway API) |
| Azure | Front Door (global L7 + CDN + WAF); Application Gateway (for Containers — Gateway API for AKS); API Management (portal, policies, AI gateway); Load Balancer (L4) |
| Cloudflare | Proxy/CDN; Load Balancing (failover between origins, regions, clouds); Spectrum (TCP/UDP — games, SSH, MQTT); API Shield (schema validation, mTLS, API discovery); Tunnel + Access; Workers as a light gateway (A/B, redirects); Custom Hostnames for SaaS |

## Task → default → when to switch

| Task | Default | Switch when |
|---|---|---|
| A normal site or API on a server | Caddy + Cloudflare in front | Docker with many services → Traefik |
| High-load ingress, L4 for databases | HAProxy | — |
| Already on Nginx, want Plus features free | Angie | — |
| Kubernetes ingress | Envoy Gateway (Gateway API) | k3s and simplicity → Traefik; Nginx team → NGINX Gateway Fabric |
| Leaving ingress-nginx | Envoy Gateway or Traefik | — |
| Public API with keys and quotas | Apache APISIX | mobile BFF → KrakenD; portal and monetisation → Tyk |
| Leaving free Kong | Apache APISIX or Envoy Gateway | — |
| mTLS between services in k8s | Cilium (already the CNI) | complex traffic management → Istio ambient |
| Mesh for VMs and k8s together | Kuma | already on the HashiCorp stack → Consul |
| CDN and DDoS protection | Cloudflare | media only and cheap → bunny.net; in-country traffic → the local cloud's CDN |
| Publishing a service from the office | Cloudflare Tunnel + Access | no external vendor → Pangolin |
| SaaS with customer custom domains | Caddy on-demand TLS | on Cloudflare → Custom Hostnames |
