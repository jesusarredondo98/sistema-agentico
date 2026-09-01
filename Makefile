# Makefile de AeroNova. Envoltura fina sobre el runbook de PRD §13.
# Los scripts a los que llama se completan en fases posteriores (ver stubs).

IMAGE ?= aeronova-agent
PLATFORM ?= linux/arm64
PROFILE ?= dev
SEED ?= 42

# Credencial de despliegue (ACU-004). Se puede sobrescribir: make data AWS_PROFILE=otro
export AWS_PROFILE ?= aeronova
export AWS_REGION ?= us-east-1

.DEFAULT_GOAL := help
.PHONY: help preflight data data-corpus test build deploy deploy-ui

help: ## Lista los objetivos disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

preflight: ## Verifica AWS CLI, Terraform >=1.6, Docker buildx y acceso a Titan V2 (PRD §13 paso 0)
	./scripts/preflight.sh

data: ## Pipeline medallion completo bronze -> silver -> gold (PRD §13 paso 3)
	python scripts/run_pipeline.py --profile $(PROFILE) --seed $(SEED)

data-corpus: ## Recarga incremental solo del corpus normativo (PRD §13 paso 6-bis, §6A.6)
	python scripts/run_pipeline.py --only corpus --profile $(PROFILE) --seed $(SEED)

test: ## Pruebas locales con cobertura (PRD §8.1)
	pytest --cov=src --cov-report=term-missing

build: ## docker build --platform linux/arm64 + push a ECR, etiqueta = SHA de Git (PRD §13 paso 4)
	./scripts/build_and_push.sh

deploy: ## terraform apply de 00-bootstrap y luego 10-app (PRD §13 pasos 1 y 5)
	cd terraform/00-bootstrap && terraform init && terraform apply
	cd terraform/10-app && terraform init && terraform apply -var="image_tag=$$(git rev-parse --short HEAD)"

deploy-ui: ## Sube ui/ a S3 e invalida CloudFront (PRD §10, §13)
	./scripts/deploy_ui.sh
