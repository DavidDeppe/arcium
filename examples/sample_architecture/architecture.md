# CloudLedger Platform — Architecture Document

**Version**: 2.1  
**Author**: Platform Engineering Team  
**Date**: 2026-04-01  
**Status**: Draft — submitted for Architecture Review Board approval

---

## Overview

CloudLedger is a SaaS financial analytics platform serving mid-market enterprise customers. The platform ingests transaction data from customer ERP systems, applies categorization and forecasting models, and exposes results via a REST API and a web dashboard.

This document describes the target production architecture for the v2 platform rewrite, migrating from an on-premises deployment to a cloud-native AWS environment.

---

## System Components

### API Layer

- **AWS API Gateway (HTTP API)**: Routes inbound requests to backend services. Handles authentication via JWT validation (Lambda authorizer).
- **Application Load Balancer (ALB)**: Distributes traffic across the ECS Fargate task fleet. Health checks configured at `/health`.
- **AWS WAF**: Attached to API Gateway for rate limiting and OWASP rule set enforcement.

### Application Services

Three primary services deployed as ECS Fargate tasks:

| Service | Language | Responsibility |
|---|---|---|
| `ingestion-service` | Python 3.12 | Accepts transaction uploads, validates schema, writes to S3 staging |
| `processing-service` | Python 3.12 | Reads from S3, runs categorization + forecasting, writes to RDS |
| `api-service` | Python 3.12 / FastAPI | Serves REST API, reads from RDS, handles customer authentication |

All three services are deployed from Docker images stored in Amazon ECR. Task definitions specify CPU and memory limits. Services scale based on a scheduled autoscaling policy: scale up at 08:00 UTC, scale down at 22:00 UTC to reduce overnight costs.

### Data Layer

- **Amazon RDS Aurora PostgreSQL**: Primary database for processed transaction data and customer records. Single-AZ deployment (Multi-AZ flagged for post-launch). Automated backups enabled (7-day retention). No read replicas — all queries hit the primary writer instance.
- **Amazon ElastiCache Redis**: Session cache and short-lived computation results. Single-node deployment.
- **Amazon S3**: Raw transaction file staging and long-term archive. Versioning enabled. Lifecycle policy moves objects to Glacier after 90 days.

### Frontend

- **React SPA**: Single-page application bundled and deployed as a Node.js Express server running on a single ECS Fargate task (2 vCPU / 4GB). Static assets served directly from the Express server. No CDN in place.
- **Authentication**: AWS Cognito User Pools for customer identity. JWT tokens issued on login and validated at API Gateway.

### CI/CD Pipeline

- **GitHub Actions**: Pull request checks run lint, unit tests, and Docker build. Main branch merges trigger a deployment pipeline:
  1. Build and push Docker image to ECR
  2. Update ECS task definition
  3. Trigger ECS rolling update (replace 50% of tasks at a time)
- **Infrastructure as Code**: All AWS resources defined in Terraform. State stored in S3 with DynamoDB locking. Applied manually by a platform engineer from a local machine — no automated Terraform apply in CI yet.

### Secrets and Configuration

- **AWS Systems Manager Parameter Store**: Database credentials and third-party API keys stored as SecureString parameters. Services retrieve values at startup via `boto3`. Parameters are not rotated automatically.
- **Environment variables**: Feature flags and non-sensitive configuration passed as ECS task environment variables defined in the task definition JSON.

### Monitoring

- **Amazon CloudWatch**: ECS task metrics (CPU, memory) published to CloudWatch. Custom metrics for ingestion throughput emitted via the CloudWatch SDK. Alarms configured for CPU > 80% and memory > 85%.
- **Logging**: Services write structured JSON logs to CloudWatch Logs via the `awslogs` log driver. Log format includes `timestamp`, `service`, `level`, and `message`. No `trace_id` or `span_id` fields. Logs retained for 30 days.

### Networking

- **VPC**: Dedicated VPC with public subnets (ALB, NAT gateway) and private subnets (ECS tasks, RDS, ElastiCache). VPC Flow Logs enabled.
- **Security Groups**: ECS tasks accept traffic only from the ALB security group. RDS accepts connections only from the ECS task security group.
- **Availability Zones**: ALB spans three AZs. ECS tasks and RDS currently in a single AZ (us-east-1a); multi-AZ expansion planned post-launch.

---

## Capacity Planning

Expected initial load: 500 concurrent users, 2,000 API requests/minute peak. Scaling policy will be adjusted once real traffic patterns are observed. No load testing has been conducted against the current architecture.

---

## Known Gaps (Team-Identified)

The platform engineering team has identified the following items as deferred post-launch:

1. Multi-AZ for RDS and ElastiCache
2. Automated Terraform apply in CI
3. Credential rotation for Parameter Store secrets
4. Load testing

All other items are considered in-scope for v2 launch.
