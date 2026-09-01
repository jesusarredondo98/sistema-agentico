---
name: pdf-report
description: Genera informes técnicos en PDF con el design system de AeroNova (portada azul marino a sangre, KPIs, barras de sección numeradas, tablas con franjas y diagramas de flujo por etapas). Úsala cuando pidan un informe, reporte, resumen técnico, entregable o documentación en PDF; también al convertir a PDF un Markdown existente como el PRD. Renderiza HTML con Chrome headless.
---

# Informe técnico en PDF

Design system extraído de `pipeline_summary.pdf`. La paleta procede del content stream
del PDF original, no de una estimación visual.

## Flujo

1. Crea una carpeta de trabajo y **copia** `assets/report.css` junto al HTML que escribas.
   El `<link>` es relativo: si el CSS no está al lado, el PDF sale sin estilo y sin avisar.
2. Escribe el HTML partiendo de `assets/template.html`, que contiene todos los componentes.
3. Renderiza:

   ```bash
   python3 scripts/build_pdf.py informe.html -o informe.pdf
   ```

4. **Abre el PDF y míralo** antes de darlo por bueno. Comprueba saltos de página,
   tablas partidas y viudas. No entregues un PDF que no hayas visto.

## Estructura obligatoria

El orden no es negociable: es lo que hace reconocible al documento.

```
cover  →  meta  →  kpis  →  [section → contenido]×N
```

- **`.cover`** va fuera de `.wrap` y sangra hasta el borde. Siempre la primera.
- Todo lo demás va dentro de `<div class="wrap">`.
- Las secciones se numeran correlativamente desde 1, sin saltos.

## Componentes

| Clase | Para qué | Regla |
|---|---|---|
| `.cover` | Portada | `eyebrow` en versalitas, `h1` en Calibri Light, `lede` de una línea |
| `.meta` | Autoría y procedencia | Autor y fecha a la izquierda; enlaces y contexto a la derecha |
| `.kpis` / `.kpi` | Cifras de cabecera | **Exactamente 3.** Cifra en `.value`, rótulo en `.lab` |
| `.section` | Cabecera de sección | `<span class="n">N</span>` + `<h2>` |
| `.subsection` | Subapartado | `<h3>` con numeración `4.1`, `4.2`… |
| `.pipeline` / `.stage` / `.chev` | Diagrama de etapas | `.box` con el nombre, `.cap` debajo con el detalle |
| `ul.findings` | Hallazgos y decisiones | Entradilla en `<strong>` y desarrollo después |
| `.catalog` / `.group` | Listados en dos columnas | `.head` es el rótulo del grupo |
| `table.data` | Datos | Cabecera azul marino, franjas alternas automáticas |
| `td.num` / `th.num` | Columna numérica | Alinea a la derecha con cifras tabulares |
| `tr.highlight` + `.badge` | Fila elegida | Fondo crema. **Una por tabla como mucho** |
| `.qtable` | Tabla con barra de título | Para resultados de consulta o bloques con encabezado propio |
| `.caption` | Pie de tabla | La lectura que el lector no debe tener que deducir |
| `.page-break` / `.keep` | Paginación | Forzar salto / impedir que un bloque se parta |

## Reglas de estilo

- **Nunca escribas colores literales en el HTML.** Usa las variables de `:root`. Un
  `#1B3A5C` suelto en el marcado rompe el sistema en la primera revisión.
- Toda tabla lleva `.caption` debajo salvo que sea obvia. El pie dice qué significa
  el dato, no lo repite.
- Los números van en `td.num`. Mezclar alineaciones en una columna numérica se nota.
- `<code>` para rutas, identificadores y nombres de fichero. Dentro de una barra azul
  o de la portada, el CSS ya invierte el fondo: no lo fuerces.
- Un informe de una página no necesita KPIs. Si los pones, que sean tres.

## Verificación antes de entregar

```bash
pdfinfo informe.pdf | grep -E "Pages|Page size"   # Letter, 612x792 pts
pdffonts informe.pdf                              # Calibri + Menlo, todas embebidas
```

Después **lee el PDF** con la herramienta de lectura y revísalo página a página.

## Fuentes

Calibri (Regular, Bold, Light, Italic) y Menlo. En macOS con Office instalado ya están.
Si faltan, `report.css` degrada a Carlito —métricamente compatible con Calibri— y
después a Lato y a la fuente del sistema. Menlo cae a DejaVu Sans Mono o Consolas.
La pila de respaldo cambia el color del documento: revísalo si no tienes Calibri.

## Fallos conocidos

- **PDF sin estilos:** el CSS no está junto al HTML. Es siempre esto.
- **Chrome se cuelga sin generar nada:** no añadas `--run-all-compositor-stages-before-draw`
  ni `--virtual-time-budget`; juntos bloquean Chrome 150+. El script ya usa el conjunto
  mínimo verificado.
- **Chrome no arranca:** exporta `CHROME_BIN` con la ruta al ejecutable.
- **Los colores salen en gris:** falta `print-color-adjust: exact`, que `report.css`
  ya incluye. Si has escrito tu propio CSS, añádelo.
