---
name: injection-defense
description: Aplica la defensa en capas contra inyección de prompts en los tres vectores y los límites de entrada con presupuesto de tokens. Úsala en F6, y siempre que se añada un campo de texto libre que llegue al modelo.
---

# Defensa contra inyección y abuso de tokens

Dos amenazas distintas que comparten mecanismo: ambas entran por **contenido no confiable** y
ambas se contienen acotando qué puede hacer ese contenido.

## Los tres vectores (§12A.1)

| Vector | Origen | Trampa |
|---|---|---|
| Fragmentos del RAG | Corpus normativo | Se envolvían **sin neutralizar el delimitador** |
| **Mensaje del usuario** | Empleado autenticado | No estaba protegido en absoluto |
| **Resultados de herramienta** | Campos libres de DynamoDB: `nombre`, `motivo`, `puerta` | El menos evidente y el más real |

Un nombre de pasajero es **texto arbitrario que acaba dentro del contexto del modelo**. Aquí
lo genera `Faker`, pero el diseño **debe** tratarlo como hostil: en un sistema real lo escribe
un tercero (R-21).

## Las seis defensas (§12A.2)

**D-1 · Neutralización del delimitador — obligatoria.** Envolver en `<documento_recuperado>`
no sirve de nada si el contenido puede contener la etiqueta de cierre. Antes de envolver,
**todo texto no confiable sustituye `<` por `&lt;` y `>` por `&gt;`**. La etiqueta envolvente
queda imposible de falsificar desde dentro. *(Alternativa descartada: un nonce por petición
rompería la estabilidad byte a byte del prefijo cacheado y encarecería cada petición.)*

**D-2 · Envoltura de todo contenido no confiable, no solo del RAG.**

| Contenido | Envoltura |
|---|---|
| Fragmento del corpus | `<documento_recuperado id="…" titulo="…">…</documento_recuperado>` |
| Resultado de herramienta | `<dato_operativo fuente="consultar_estado_vuelo">…</dato_operativo>` |

Ambas se declaran en el system prompt como **zonas de datos, nunca de instrucciones**.

**D-3 · Radio de explosión acotado por diseño — la defensa más fuerte.** Ver `agent-tools`.
Preservarla es obligatorio; romperla es el riesgo R-20 (impacto crítico).

**D-4 · Sin canal de operador a mitad de conversación.** Sonnet 5 no admite mensajes `system`
intercalados. Todas las instrucciones viven en el campo `system` de nivel superior, fuera del
array de `messages`: **no existe ningún punto donde contenido no confiable pueda hacerse pasar
por instrucción del operador.**

**D-5 · Filtro de salida.** Antes de devolver la respuesta, el handler comprueba que no
contiene: fragmentos literales del system prompt (**tres frases distintivas fijadas como
firma**), el patrón `sk-ant-[A-Za-z0-9_-]{20,}`, ni la cadena `ANTHROPIC_API_KEY`. Si detecta
alguno, sustituye la respuesta por un mensaje genérico, **devuelve 200** y emite un evento de
seguridad. Comprobación local, sin coste.

**D-6 · Detección en la entrada: marcar, no bloquear.** El mensaje se contrasta con patrones
conocidos (`ignora (las )?instrucciones`, `system prompt`, `eres ahora`,
`modo (admin|desarrollador)`, `reveal your instructions`). Al coincidir **se registra y se
emite `InjectionSuspected`, pero la petición continúa.**

> Bloquear sería desproporcionado: el usuario es un empleado autenticado, el radio de
> explosión está acotado por D-3, y un falso positivo dejaría a un agente de mostrador sin
> servicio delante de un pasajero. **La señal sirve para vigilar, no para cortar.**

## Límites de entrada y presupuesto de tokens (§12A.3)

Un límite en **caracteres** es un mal indicador del coste: 2.000 caracteres son ~625 tokens en
español, ~2.000 en CJK o emoji y ~1.540 en base64 ofuscado. **El mismo límite admitía 4× el
coste.**

| # | Control | Valor | Al incumplirse |
|---|---|---|---|
| L-1 | Longitud de `message` | 1–1.200 caracteres | 400 `INVALID_REQUEST` |
| L-2 | Tokens estimados | ≤ 400, heurística `ceil(len/3.2)` | 400 `INPUT_TOO_LARGE` |
| L-3 | Ratio caracteres/tokens | ≥ 1,5 | 400 `INPUT_TOO_LARGE` |
| L-4 | **Prompt ensamblado** | **≤ 4.000 tokens.** Descarta historial de más antiguo a más reciente | Truncado, con métrica **y comunicado al usuario** vía `context.truncated` |
| L-5 | Turnos por sesión | ≤ 50 | 429 `SESSION_TURN_LIMIT` |
| L-6 | Resultado de herramienta | ≤ 450 tokens | Truncado con marca visible |

**L-4 es el que cerró un agujero de 9×**: con la ventana de 8 mensajes, un historial de
mensajes largos alcanzaba ~5.000 tokens frente a los 550 presupuestados, elevando el coste por
consulta de 0,00875 a 0,0168 USD **sin infringir ninguna validación**.

> **L-1, L-2 y L-3 se evalúan en el handler ANTES de construir el grafo**, de modo que una
> petición abusiva se rechaza **sin realizar ninguna llamada al LLM**: su coste es cero. Es lo
> que verifica la familia `abuse_*`.

## Cortacircuitos de coste por sesión (§12A.4)

La cuota mensual G-1 protege el total, pero **no impide que una sola sesión consuma el
presupuesto del mes**.

- El item `STATE` acumula `cost_usd_acumulado` sumando el `usage.cost_usd` de cada turno.
- Superados **0,25 USD** por sesión (≈ 28 consultas), se rechaza con **429
  `SESSION_BUDGET_EXCEEDED`**. El empleado abre sesión nueva; el abuso automatizado se detiene.
- Métrica `SessionCostUSD` con alarma en el percentil 99.

## La regla que no se relaja (R-23)

> **La validación en cliente es experiencia de usuario, nunca seguridad.** El servidor
> revalida siempre y es la única autoridad. **NO se relaja ninguna comprobación del servidor
> por el hecho de que el cliente ya la haga.** Las pruebas de §12A.5 golpean el API
> directamente, sin pasar por la interfaz.

## Criterio de terminado

Las cuatro familias `injection_*` al **100 %**, la familia `abuse_*` al 100 % **sin ninguna
llamada al LLM**, y el filtro de salida con su métrica `OutputFilterTriggered` conectada.
