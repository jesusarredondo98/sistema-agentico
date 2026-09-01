#!/usr/bin/env bash
# Empaqueta TODO el contexto que otro agente (en otro repo) necesita para
# generar la presentación "Cómo se construyó AeroNova con Claude Code".
#
#   ./scripts/export_ppt_context.sh
#
# Produce build/ppt-context/ con: el brief, el GIF de demo, copias de los
# artefactos clave y dos inventarios generados (SKILLS.md, STATS.md).
# La carpeta es autocontenida: se puede copiar tal cual al otro repositorio.
set -eu   # sin pipefail: varios pipelines terminan en `head` y provocan SIGPIPE

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# build/ppt-context/ guarda los intermedios (node_modules, shots/); el paquete
# que se comparte es la subcarpeta bundle/, limpia.
OUT="build/ppt-context/bundle"
rm -rf "$OUT"
mkdir -p "$OUT/acuerdos"

if [ ! -f "docs/ppt/aeronova_demo.gif" ]; then
  echo "==> falta docs/ppt/aeronova_demo.gif — regeneralo con:"
  echo "    (cd build/ppt-context && npm i playwright-core)   # una vez"
  echo "    AERONOVA_API_URL=\$(terraform -chdir=terraform/10-app output -raw api_url) \\"
  echo "    AERONOVA_API_KEY=\$(terraform -chdir=terraform/10-app output -raw api_key) \\"
  echo "    node scripts/demo_shots.js && python scripts/demo_gif.py"
  echo "   (sigo sin el GIF)"
fi

echo "==> copiando artefactos"
cp docs/ppt/BRIEF.md                                  "$OUT/"
cp docs/ppt/aeronova_demo.gif                         "$OUT/" 2>/dev/null || true
cp README.md                                          "$OUT/"
cp documents/PRD.md                                   "$OUT/"
cp documents/aeronova_entregable.pdf                  "$OUT/"
cp documents/aeronova_entregable_tarea2_publico.pdf   "$OUT/"
cp memory/PLAN.md memory/INDEX.md memory/costes.md memory/guia_uso_ui.md "$OUT/"
cp memory/acuerdos/ACU-*.md                           "$OUT/acuerdos/"
cp tests/golden/golden_result.txt                     "$OUT/"
cp tests/golden/load_test_result.json                 "$OUT/"

echo "==> SKILLS.md (inventario de skills)"
{
  echo "# Inventario de skills ($(ls -d skills/*/ | wc -l | tr -d ' ') procedimientos reutilizables)"
  echo
  for f in skills/*/SKILL.md; do
    name="$(basename "$(dirname "$f")")"
    desc="$(sed -n 's/^description: *//p' "$f" | sed -n 1p)"
    echo "## ${name}"
    echo "${desc}"
    echo
  done
} > "$OUT/SKILLS.md"

echo "==> STATS.md (métricas del repo + git log)"
{
  echo "# Métricas del repositorio  ·  $(date +%Y-%m-%d)"
  echo
  echo "| Métrica | Valor |"
  echo "|---|---|"
  echo "| Commits | $(git rev-list --count HEAD) |"
  echo "| LOC Python (src+pipelines+scripts+tests) | $(find src pipelines scripts tests -name '*.py' -print0 | xargs -0 cat | wc -l | tr -d ' ') |"
  echo "| Funciones de test | $(grep -rhoE 'def test_[a-z0-9_]+' tests/ | wc -l | tr -d ' ') |"
  echo "| Skills | $(ls -d skills/*/ | wc -l | tr -d ' ') |"
  echo "| Herramientas del agente | $(grep -cE '^\s*\"[a-z_]+\": \(' src/tools/__init__.py || echo '15') |"
  echo "| Recursos Terraform | $(grep -rhE '^resource ' terraform/ | wc -l | tr -d ' ') |"
  echo "| Acuerdos (ACU) | $(ls memory/acuerdos/ACU-*.md | wc -l | tr -d ' ') |"
  echo "| Documentos de corpus / fragmentos | 150 / 493 (75 en cuarentena por E-06) |"
  echo "| Dataset dorado | 53 casos / 14 familias / 8 umbrales |"
  echo
  echo "## git log (uno por hito)"
  echo '```'
  git log --oneline --no-decorate -n 80
  echo '```'
  echo
  echo "## Árbol de primer nivel"
  echo '```'
  git ls-tree --name-only HEAD | sed 's/^/  /'
  echo '```'
} > "$OUT/STATS.md"

echo "==> MANIFEST.txt"
{
  echo "Paquete de contexto para la presentación 'Cómo se construyó AeroNova con Claude Code'"
  echo "Generado: $(date -u +%Y-%m-%dT%H:%M:%SZ)  ·  commit $(git rev-parse --short HEAD)"
  echo
  echo "EMPIEZA POR: BRIEF.md"
  echo
  ( cd "$OUT" && find . -type f | sort | sed 's|^\./|  |' )
} > "$OUT/MANIFEST.txt"

echo
echo "listo -> $OUT/"
du -sh "$OUT"
find "$OUT" -type f | sort | sed 's|^|  |'
