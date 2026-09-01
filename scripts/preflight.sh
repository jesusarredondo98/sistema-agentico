#!/usr/bin/env bash
# Paso 0 del runbook (PRD §13). Verifica los cuatro prerrequisitos y falla con
# mensaje claro si falta alguno. R-04 (acceso a Titan, probabilidad ALTA) es el
# motivo de que este script exista y sea bloqueante.
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
TITAN_MODEL="${BEDROCK_EMBED_MODEL:-amazon.titan-embed-text-v2:0}"
fail=0

red()  { printf '\033[31m[FALLO]\033[0m %s\n' "$*" >&2; fail=1; }
ok()   { printf '\033[32m[OK]\033[0m    %s\n' "$*"; }

# 1 - AWS CLI configurado
if ! command -v aws >/dev/null 2>&1; then
  red "AWS CLI no esta instalado. Instala 'awscli' v2."
elif ! aws sts get-caller-identity >/dev/null 2>&1; then
  red "AWS CLI instalado pero sin credenciales validas. Ejecuta 'aws configure'."
else
  ok "AWS CLI configurado ($(aws sts get-caller-identity --query Account --output text) / $REGION)."
fi

# 2 - Terraform >= 1.6
if ! command -v terraform >/dev/null 2>&1; then
  red "Terraform no esta instalado. Se requiere >= 1.6."
else
  tf_ver="$(terraform version -json 2>/dev/null | sed -n 's/.*"terraform_version": *"\([^"]*\)".*/\1/p')"
  [ -z "$tf_ver" ] && tf_ver="$(terraform version | head -1 | sed 's/Terraform v//')"
  if [ "$(printf '%s\n1.6.0\n' "$tf_ver" | sort -V | head -1)" != "1.6.0" ]; then
    red "Terraform $tf_ver es anterior a 1.6. Actualiza."
  else
    ok "Terraform $tf_ver (>= 1.6)."
  fi
fi

# 3 - Docker con soporte buildx
if ! command -v docker >/dev/null 2>&1; then
  red "Docker no esta instalado."
elif ! docker info >/dev/null 2>&1; then
  red "El daemon de Docker no responde. Arranca Docker Desktop."
elif ! docker buildx version >/dev/null 2>&1; then
  red "Docker no tiene el plugin 'buildx'. Necesario para --platform linux/arm64."
else
  ok "Docker con buildx ($(docker buildx version | awk '{print $2}'))."
fi

# 4 - Acceso al modelo Titan Embeddings V2 habilitado en Bedrock (R-04)
if ! command -v aws >/dev/null 2>&1; then
  red "No se puede comprobar Titan V2 sin AWS CLI."
else
  probe="$(aws bedrock-runtime invoke-model \
      --region "$REGION" \
      --model-id "$TITAN_MODEL" \
      --content-type application/json \
      --accept application/json \
      --body "$(printf '{"inputText":"preflight"}' | base64)" \
      /dev/null 2>&1)" && titan_ok=1 || titan_ok=0
  if [ "$titan_ok" -eq 1 ]; then
    ok "Acceso a $TITAN_MODEL habilitado en Bedrock ($REGION)."
  else
    red "Sin acceso a $TITAN_MODEL en Bedrock ($REGION). Habilitalo en la consola: Bedrock > Model access > Titan Text Embeddings V2. Detalle: $(printf '%s' "$probe" | tail -1)"
  fi
fi

if [ "$fail" -ne 0 ]; then
  printf '\n\033[31mPreflight FALLIDO.\033[0m Corrige lo anterior antes de continuar con el runbook.\n' >&2
  exit 1
fi
printf '\n\033[32mPreflight OK.\033[0m Puedes seguir con el paso 1 (terraform/00-bootstrap).\n'
