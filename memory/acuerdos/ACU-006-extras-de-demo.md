---
id: ACU-006
titulo: Extras de demo sobre la interfaz y el agente (más allá del PRD)
tipo: desviacion
estado: vigente
fase: F8
prd_ref: ["§10", "§4.2", "§5.4", "I-13", "§12A.4"]
aprobado_por: usuario
fecha: 2026-08-29
---

**Qué se desvía.** Durante la puesta a punto de la demo, el usuario pidió una serie de
añadidos que el PRD no contempla. Todos son de solo lectura y no cambian el modelo de
amenazas de fondo, pero se apartan de la letra del PRD y se registran aquí para no perder
el control de los cambios.

**Hecho y desplegado:**

- **Vista «Datos de prueba»** en la UI: dos tablas con códigos de vuelo y PNR reales del
  conjunto sembrado (seed 42) para que quien pruebe la demo no tenga que adivinar claves.
  Client-side, `ui/sample_data.json`. Sin impacto en el backend.
- **Contador «Mensajes disponibles en esta sesión: N de 50»** persistente en la UI (antes
  solo la banda del turno 40). Puro cliente, refleja L-5, no lo cambia.
- **Gráfica determinista de relevancia RAG.** Campo nuevo `charts` en la respuesta §4.2
  (aditivo). `tool_node._chart_for` genera un spec de barras **solo** para
  `buscar_politicas_rag` (score de cada fragmento, ≥2, tope 6). Sin LLM, sin librerías; la
  UI lo pinta en SVG. Restringido a esa whitelist "para que no se dispare". Citado en el
  panel de uso responsable y en un pie bajo cada gráfica.
- **Enter envía el mensaje** (Shift+Enter = salto de línea). Botón **«Contacto»** (correo +
  LinkedIn). Puro cliente.
- **CORS de la respuesta real y de las gateway responses** (`UI_ORIGIN` + `to_proxy` +
  `aws_api_gateway_gateway_response`). Esto NO es un extra: es corregir A-105, que solo
  cubría el preflight OPTIONS. El chat del navegador fallaba sin ello.
- **Saneo del historial al cargarlo** (`memory._sanitize_history`): la ventana de 8
  mensajes podía cortar un par `tool_use`/`tool_result` → Anthropic 400 → `INTERNAL_ERROR`
  en el turno ~3. Tampoco es un extra: es un bug de F5/F6.

**Pendiente de decisión del usuario (no implementado):**

- **3 herramientas nuevas de solo lectura** (rompe I-13, "las tres herramientas"):
  `vuelos_por_ciudad`, `pasajeros_de_vuelo` (muestra aleatoria determinista de 5),
  `mascotas_por_vuelo` (recuento). Requieren **GSIs** en las tablas `flights` y
  `reservations` (`terraform/00-bootstrap`), `dynamodb:Query` en esos índices en la política
  IAM de la Lambda, una frase en el system prompt, reverificar la prueba de caché de F6
  (I-05, el prefijo cacheable cambia) y una nota para F9 (el golden dataset asume 3 tools).
- **Subir el cortacircuitos de coste por sesión** de 0,25 a ~0,75 USD (§12A.4, valor
  "pinned"). Env var, reversible.

**Cómo se aplica.** Todo lo "hecho" está en la rama `feat/aeronova-implementacion` con sus
commits. Lo "pendiente" no se toca hasta que el usuario lo confirme explícitamente.

**Qué invalida este acuerdo.** Que el sponsor decida que la demo debe ceñirse al PRD (se
revierte lo aditivo: `charts`, la vista de datos, el contador, las tools nuevas), o que se
formalice cada extra en el PRD.
