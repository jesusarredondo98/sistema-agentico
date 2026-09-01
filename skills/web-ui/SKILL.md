---
name: web-ui
description: Construye la interfaz estática de AeroNova (HTML/JS sin framework) heredando el design system de skills/pdf-report, con medidores de límites, guía de uso y panel de uso responsable. Úsala en F8. El PDF del entregable y la web deben parecer el mismo producto.
---

# Interfaz de AeroNova

Página única estática. **Sin framework, sin build step, sin dependencias externas.** Se sirve
desde S3 privado vía CloudFront con OAC.

## El design system se hereda, no se inventa

La paleta, la tipografía y la retícula salen de **`skills/pdf-report/reference/design-tokens.md`**
y de `skills/pdf-report/assets/report.css`. El PDF del entregable §16 y esta interfaz son el
mismo producto visto en dos medios: **si no se parecen, uno de los dos está mal**.

**Los dos azules hacen trabajos distintos y no son intercambiables:**

- `--navy` **#1B3A5C** es **estructura**: dice «aquí empieza algo». Cabeceras, barras, marcos.
- `--accent` **#2E75B6** es **señal**: dice «fíjate en esto». Estados, enlaces, foco, medidores.

Usar el marino para destacar un dato, o el acento para una cabecera, deshace la jerarquía
aunque cada color por separado siga siendo correcto.

## Reconciliación con el tema oscuro

El PRD §10.1 pide **tema oscuro**; el design system del PDF es claro. Se resuelve
**conservando los papeles, no los valores**: mismas familias de color, roles invertidos.

| Rol | PDF (claro) | UI (oscuro) | Regla |
|---|---|---|---|
| Fondo | `--paper` #FFFFFF | `--navy-deep` #122A44 | El marino profundo pasa a ser el papel |
| Superficie elevada | `--tint` #E7EFF7 | `--navy` #1B3A5C | Burbujas del agente, paneles |
| Texto principal | `--ink` #222222 | #E7EFF7 (`--tint`) | Contraste ≥ 7:1 |
| Texto secundario | `--muted` #595959 | `--accent-soft` #9FC0E0 | |
| **Señal** | `--accent` #2E75B6 | **`--accent` #2E75B6** | **No cambia. Es el ancla de identidad** |
| Aviso | `--highlight` #FFF3D6 | #FFF3D6 sobre fondo oscuro | Ámbar del 80 % |
| Reglas y bordes | `--rule` #C9D3DE | rgba de `--accent-soft` | |

Tipografía: **Calibri** con la misma pila de respaldo (`Carlito`, `Lato`, system-ui) y
**Menlo** para código, rutas e identificadores. Escala en `rem`, no en `pt`: el destino es
pantalla.

> **Nunca se escribe un color literal en el marcado.** Todo pasa por variables de `:root`, tal
> como exige la skill `pdf-report`. Un `#1B3A5C` suelto rompe el sistema en la primera revisión.

## Funcionalidad base (§10.1)

- Campos para la URL del API y la `x-api-key`, ambos en `localStorage`. **La clave NUNCA se
  incrusta en `app.js`**: el bundle es público a través de CloudFront.
- `session_id` con `crypto.randomUUID()` al primer mensaje, persistido, **visible en pantalla**
  y con botón «Nueva sesión».
- **Indicador de qué herramienta se está ejecutando**, leído de `tools_used`. Es lo que hace
  visible el comportamiento agéntico durante la demostración.
- Panel plegable por mensaje con `tools_used`, `tool_rounds` y `usage`. **Colapsado por
  defecto**: el usuario es un agente de mostrador con un pasajero delante, no un operador de
  plataforma (R-24).
- El contrato de error de §4.3 se renderiza como **mensaje legible**, nunca `[object Object]`.

## Comunicación de límites (§10.2)

> **Un límite que el usuario descubre al chocar contra él se percibe como una avería.**

Cuatro principios: **preventivo** antes que correctivo · **progresivo** (normal → aviso al
80 % → bloqueo, nunca un salto directo a error) · **explicativo y accionable** (qué pasa y qué
hacer) · **discreto**.

| Límite | Aviso | Tratamiento |
|---|---|---|
| **L-1** 1.200 caracteres | 960 (80 %) | Contador vivo `960/1.200`. Neutro → ámbar → **rojo con envío deshabilitado** |
| **L-2/L-3** tokens y ratio | — | Validación con la **misma heurística que el servidor**; mensaje concreto **antes** de enviar |
| **L-5** 50 turnos | turno 40 | Banda persistente con «Nueva sesión» destacado |
| Coste de sesión 0,25 USD | 0,20 (80 %) | Aviso discreto en cabecera; al agotarse, diálogo con «Nueva sesión» |
| **L-4** truncado | al ocurrir | Marca en el hilo, en el punto donde ocurrió |
| `max_rounds` | al ocurrir | **Nota explicativa, no un error** |
| **G-1** cuota (429) | — | Pantalla de cuota agotada. **No se inventa un medidor de cuota**: el cliente no puede conocer el consumo del Usage Plan |

> **La segunda frase del aviso de truncado es la que importa:** «Se recortaron los N mensajes
> más antiguos. **Los datos de la reserva activa se conservan.**» Sin ella, el usuario ve que
> el agente «olvida» y deja de confiar. Con ella entiende qué pasó — y es cierto, porque
> `pnr_activo` vive en el item `STATE` (§4.5).

**Regla vinculante:** la validación en cliente es **experiencia de usuario, nunca seguridad**
(R-23). El servidor revalida siempre.

## Guía de uso (§10.3) — la palanca más barata contra el gasto

Una consulta que omite el código de vuelo dispara `falta_datos`, necesita un turno más y
**cuesta el doble**: 0,0175 en lugar de 0,00875 USD. La guía no es cortesía.

- **Estado vacío del chat**: tarjetas de ejemplo agrupadas por las 4 capacidades (vuelos, PNR,
  políticas, **combinadas** — estas son las que mejor lucen el comportamiento agéntico).
- **Enlace permanente «¿Qué puedo preguntar?»** en la cabecera.
- Al pulsar un ejemplo: **se inserta en el campo**, se enfoca y se selecciona el marcador
  (`AN405`, `ABC123`). **NUNCA se envía automáticamente** — enviar al hacer clic gastaría
  presupuesto en datos de ejemplo, que es el desperdicio que la guía evita.
- Secciones **«Qué no puedo hacer»** y **«Consejos para consultas eficaces»**.

**Fuente única:** `ui/examples.json`, no incrustado en el HTML. Una prueba unitaria verifica
formatos (`^AN\d{3,4}$`, `^[A-Z0-9]{6}$`), que cada grupo declara una `expected_tool` existente
en el registro, y que ningún ejemplo supera L-1.

> **Los valores deben ser reales, no marcadores.** Para la demo, `ui/examples.json` se puebla
> con códigos y PNR que **existan de verdad** en el conjunto sembrado, tomados del
> `_manifest.json` de la última carga. Un ejemplo que devuelve «no encuentro esa reserva»
> durante la demo transmite lo contrario de lo que se quiere demostrar (R-25, comprobación U-14).

## Panel de uso responsable (§10.4)

Abierto en la primera visita, descartable con memoria en `localStorage`. Explica qué sabe y
qué no sabe hacer, que hay que **verificar antes de comprometer algo con un pasajero**, por
qué existen los límites, cómo escribir consultas eficaces y que **no se escriben credenciales
ni datos de pago en el chat**.

> **Qué NO se explica aquí:** los mecanismos de defensa de §12A. No es accionable para un
> agente de mostrador y sí es útil para quien quisiera evadirlos.

## Accesibilidad (§10.5)

- Los estados **no se distinguen solo por color**: llevan icono y texto.
- Medidores con `role="status"` y `aria-live="polite"`; el bloqueo al 100 % con
  `aria-live="assertive"`.
- El contador se anuncia **solo al cruzar un umbral**, no en cada pulsación.

## Criterio de terminado

La lista **U-1 a U-14** de §8.5 superada y adjunta al informe. U-5, U-6, U-7 y U-8 se fuerzan
con **respuestas simuladas desde el cliente**: reproducir un truncado real o agotar una cuota
real para probar la interfaz es caro e innecesario.
