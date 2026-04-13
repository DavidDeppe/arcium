# Architecture Standards — Modern Cloud Platform Best Practices

Version: 1.0 | Audience: Architecture Review Board

---

## 1. Observability (Triad: Metrics, Logs, Traces)

All services must implement the full observability triad.

- **Distributed tracing**: Instrument every service with OpenTelemetry (OTEL). Traces must propagate across service boundaries using W3C Trace Context headers. A collector sidecar (OTEL Collector) must aggregate and export to a backend (Jaeger, Tempo, or a managed APM).
- **Structured logging**: All logs must be emitted as JSON with mandatory fields: `trace_id`, `span_id`, `service`, `severity`, `timestamp`. Log aggregation via a centralized platform (e.g., OpenSearch, Datadog, Loki).
- **Metrics**: Services expose `/metrics` in Prometheus format. A scraping stack (Prometheus + Grafana or managed equivalent) collects and visualizes SLI/SLO compliance.
- **Alerting**: SLO-based alerting (error budget burn rate) preferred over static thresholds. Runbooks linked from every alert.

---

## 2. Scalability and Elasticity

- **Stateless services**: No session state stored in application memory. Session data must live in an external store (Redis, DynamoDB). Enables horizontal scale-out without sticky sessions.
- **Horizontal autoscaling**: All compute must support horizontal autoscaling driven by queue depth, CPU, or custom metrics — not only time-based schedules.
- **Database read replicas**: Read-heavy workloads must route to read replicas. Write path and read path are separated at the application layer.
- **Async workloads**: Long-running or background tasks are decoupled from the request path using a message queue or event stream (SQS, Kafka, SNS+SQS). No synchronous HTTP calls for operations that can take > 500ms.
- **Frontend delivery**: Static assets served from a CDN. Server-side rendering components deployed as horizontally scalable units, not as a single monolithic server process.

---

## 3. Resiliency and Reliability

- **Circuit breakers**: All synchronous service-to-service calls implement circuit breaker patterns (Resilience4j, Hystrix, or language-native equivalents).
- **Graceful degradation**: Services define degraded-mode behavior for dependency failures. Critical paths must not fail completely when non-critical dependencies are unavailable.
- **Chaos engineering**: A structured chaos practice (GameDays, Chaos Monkey, or Gremlin) validates resiliency assumptions at least quarterly.
- **Multi-AZ deployment**: All stateful resources (databases, queues, caches) deployed across at least two availability zones. Compute spans all available AZs.
- **RTO/RPO defined**: Each service tier must have documented Recovery Time Objective and Recovery Point Objective. DR runbooks are tested annually.

---

## 4. Security Posture

- **Least privilege IAM**: Every service identity (task role, service account) holds only the permissions it requires. No wildcard resource ARNs in production policies.
- **Secrets management**: All credentials, API keys, and connection strings sourced from a secrets manager (AWS Secrets Manager, HashiCorp Vault). No secrets in environment variables, config files, or source control.
- **WAF and DDoS protection**: Public ingress protected by a Web Application Firewall. Rate limiting enforced at the edge.
- **mTLS for internal traffic**: Service-to-service calls within the cluster use mutual TLS or a service mesh (Istio, Linkerd, AWS App Mesh).
- **Dependency scanning**: Automated CVE scanning in CI (Snyk, Dependabot, or Grype). Critical and high CVEs must be remediated within 7 days.

---

## 5. FinOps and Cost Efficiency

- **Resource tagging**: All cloud resources tagged with at minimum: `env`, `team`, `service`, `cost-center`. Untagged resources flagged in a weekly audit.
- **Rightsizing**: Compute and database instances reviewed quarterly against utilization metrics. Oversized resources must be downsized within 30 days of identification.
- **Commitment coverage**: Steady-state baseline workloads covered by Reserved Instances or Savings Plans (target: ≥ 70% of compute spend). Burst capacity uses Spot/Preemptible where fault-tolerant.
- **Cost anomaly detection**: Cloud provider cost anomaly detection enabled with alerts routed to the owning team.

---

## 6. Developer Experience and Deployment

- **Feature flags**: New functionality gated by feature flags (LaunchDarkly, Unleash, or AWS AppConfig) to decouple deployment from release.
- **Progressive delivery**: Blue/green or canary deployments enforced for all production releases. No direct cutover deploys.
- **DORA metrics tracked**: Deployment frequency, lead time for changes, change failure rate, and mean time to restore are measured and visible to the team.
- **Infrastructure as Code**: All infrastructure defined in IaC (Terraform, CDK, Pulumi). No manual console changes in production. Drift detection enabled.
- **Dependency review in CI**: Third-party dependency licenses reviewed in CI. GPL-incompatible licenses blocked.
