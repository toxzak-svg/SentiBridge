# SentiBridge Infrastructure

This directory contains infrastructure-as-code for deploying SentiBridge.

## Structure

```
infrastructure/
├── docker/              # Docker Compose for local development
├── terraform/           # Terraform for cloud infrastructure
│   ├── modules/         # Reusable Terraform modules
│   ├── environments/    # Environment-specific configurations
│   └── variables.tf     # Global variables
└── kubernetes/          # Kubernetes manifests (future)
```

## Local Development

```bash
cd docker
docker-compose up -d
```

## Cloud Deployment

See `terraform/README.md` for cloud deployment instructions.
