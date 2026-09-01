#!/usr/bin/env bash
# Paso 4 del runbook (PRD §13, skill lambda-container).
#
# Login en ECR -> docker build --platform linux/arm64 -> etiquetar con el SHA
# corto de Git -> push -> imprimir `image_tag=<sha>`, que consume
# `terraform plan -var="image_tag=..."` en `terraform/10-app`.
#
# La etiqueta es SIEMPRE el SHA, nunca `latest`: con `latest` Terraform no
# detecta el cambio y la Lambda conserva la imagen anterior (hallazgo 8, §13).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

AWS_PROFILE="${AWS_PROFILE:-aeronova}"
AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_PROFILE AWS_REGION

# El repositorio ECR lo crea `terraform/00-bootstrap`.
ECR_URL="$(terraform -chdir=terraform/00-bootstrap output -raw ecr_repository_url)"
ACCOUNT_ID="${ECR_URL%%.*}"
REGISTRY="${ECR_URL%/*}"

if [ -n "$(git status --porcelain)" ]; then
  echo "AVISO: hay cambios sin confirmar. La etiqueta reflejara el ultimo commit, no el arbol de trabajo." >&2
fi
TAG="$(git rev-parse --short HEAD)"

echo "==> login en ECR ($REGISTRY)"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY"

echo "==> docker build --platform linux/arm64 -t ${ECR_URL}:${TAG}"
docker build --platform linux/arm64 -t "${ECR_URL}:${TAG}" .

SIZE_BYTES="$(docker image inspect "${ECR_URL}:${TAG}" --format '{{.Size}}')"
if [ "$SIZE_BYTES" -ge 2147483648 ]; then
  echo "ERROR: la imagen mide ${SIZE_BYTES} bytes (>= 2 GB). Lambda la rechazara (§2.6)." >&2
  exit 1
fi

echo "==> push"
docker push "${ECR_URL}:${TAG}"

echo
echo "image_tag=${TAG}"
echo "image_uri=${ECR_URL}:${TAG}"
