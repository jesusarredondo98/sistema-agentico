#!/usr/bin/env bash
# Sube ui/ al bucket privado de la interfaz e invalida la caché de CloudFront
# (PRD §10, §13). El bucket lo crea 00-bootstrap; la distribución, 10-app.
#
# Uso:  ./scripts/deploy_ui.sh
#       make deploy-ui
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

AWS_PROFILE="${AWS_PROFILE:-aeronova}"
AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_PROFILE AWS_REGION

BUCKET="$(terraform -chdir=terraform/00-bootstrap output -raw s3_ui_bucket)"
DIST_ID="$(terraform -chdir=terraform/10-app output -raw cloudfront_distribution_id)"

# Sella `app.js` y `styles.css` con la versión (SHA corto) en un árbol temporal:
# una pestaña abierta durante un despliegue anterior recoge el JS nuevo sin
# hard-refresh, porque el index.html (siempre revalidado) apunta a otra URL.
VER="$(git rev-parse --short HEAD 2>/dev/null || date +%s)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -R ui/. "$STAGE/"
sed -i '' -E "s|(href=\"styles\.css)\"|\1?v=${VER}\"|; s|(src=\"app\.js)\"|\1?v=${VER}\"|" "$STAGE/index.html"

echo "==> sync ui/ (v=${VER}) -> s3://${BUCKET}/"
# `no-cache` en todo: es una demo de bajo tráfico y prima que el navegador
# recoja siempre la última versión (evita "no me funciona" por caché vieja).
aws s3 sync "$STAGE/" "s3://${BUCKET}/" --delete --exclude ".*" --exclude "*.md" \
  --cache-control "no-cache, must-revalidate"

echo "==> invalidación de CloudFront (${DIST_ID})"
ID="$(aws cloudfront create-invalidation --distribution-id "$DIST_ID" \
  --paths '/*' --query 'Invalidation.Id' --output text)"

echo "==> invalidación ${ID} en curso"
aws cloudfront wait invalidation-completed --distribution-id "$DIST_ID" --id "$ID" \
  && echo "==> invalidación completada"

URL="$(terraform -chdir=terraform/10-app output -raw ui_url)"
echo
echo "UI publicada en: ${URL}"
