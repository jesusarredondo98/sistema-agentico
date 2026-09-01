# Tokens del design system

Valores extraídos del content stream de `pipeline_summary.pdf` (operadores `rg`/`RG`),
no estimados a ojo sobre una captura. Las cuentas de uso indican la jerarquía real.

## Paleta

| Token | Hex | Usos en el original | Dónde aparece |
|---|---|---:|---|
| `--navy` | `#1B3A5C` | 80 | Banda de portada, barras de sección, cabecera de tabla |
| `--accent` | `#2E75B6` | 72 | Insignias, barras de subsección, enlaces, viñetas, rótulos de grupo |
| `--tint` | `#E7EFF7` | 58 | Franja alterna de tabla, fondo de código |
| `--ink` | `#222222` | 44 | Texto principal |
| `--muted` | `#595959` | 30 | Pies de tabla y texto secundario |
| `--rule` | `#C9D3DE` | 26 | Bordes de tabla y reglas horizontales |
| `--navy-deep` | `#122A44` | 24 | Cabecera de las tablas dentro de `.qtable` |
| `--ink-code` | `#2B2B2B` | 10 | Texto monoespaciado |
| `--tint-strong` | `#CFE0F0` | 2 | Relleno de las etapas del diagrama |
| `--accent-soft` | `#9FC0E0` | 2 | Borde de las etapas, eyebrow de portada |
| `--highlight` | `#FFF3D6` | 2 | Fila destacada |
| `--muted-soft` | `#8C96A3` | 2 | Etiquetas tenues |

**Los dos azules hacen trabajos distintos y no son intercambiables.** `--navy` es
estructura: dice «aquí empieza algo». `--accent` es señal: dice «fíjate en esto».
Usar el marino para destacar un dato, o el acento para una cabecera de sección,
deshace la jerarquía aunque cada color por separado siga siendo correcto.

## Tipografía

| Rol | Familia | Peso | Tamaño |
|---|---|---|---|
| Título de portada | Calibri Light | 300 | 27 pt |
| Título de sección | Calibri | 700 | 14 pt |
| Título de subsección | Calibri | 700 | 10.5 pt |
| Cifra KPI | Calibri | 700 | 21 pt |
| Cuerpo | Calibri | 400 | 9.5 pt |
| Tabla y metadatos | Calibri | 400 | 8.2 pt |
| Rótulos, pies, eyebrow | Calibri | 400/700 | 7.4 pt |
| Código | Menlo | 400 | 0.92 em del contexto |

El título de portada en peso **300** es lo que más define el carácter del documento:
en bold pierde el aire y parece una presentación comercial.

## Retícula

- Página Letter, 612 × 792 pt.
- Margen lateral de contenido: 16 mm, aplicado por `.wrap`.
- Margen superior 16 mm y 14 mm inferior, salvo la primera página, donde el superior
  es 0 para que la portada sangre.
- KPIs y catálogo: rejillas de 3 y 2 columnas.

## Comprobación de fidelidad

```bash
# Paleta realmente usada en un PDF generado
python3 - <<'PY'
import re, zlib, collections
d = open("informe.pdf", "rb").read()
c = collections.Counter()
for m in re.finditer(rb'stream\r?\n', d):
    s = m.end()
    try: t = zlib.decompress(d[s:d.find(b'endstream', s)])
    except Exception: continue
    for mm in re.finditer(rb'([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+rg\b', t):
        r, g, b = (float(x) for x in mm.groups())
        c['#%02X%02X%02X' % (round(r*255), round(g*255), round(b*255))] += 1
for k, n in c.most_common(12): print(k, n)
PY
```

Si aparece un color que no está en la tabla de arriba, alguien ha escrito un hex
suelto en el HTML.
