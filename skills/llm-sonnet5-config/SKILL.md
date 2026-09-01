---
name: llm-sonnet5-config
description: Configura la llamada a claude-sonnet-5 respetando las restricciones de la API que devuelven 400, y monta la caché de prompt con TTL de 1 hora, que es la principal palanca de coste. Úsala en F1 y en F6, y ante cualquier HTTP 400 sistemático.
---

# Configuración del LLM

Ignorar cualquiera de estos puntos produce **HTTP 400 en todas las peticiones**, no en
algunas. Verificado contra la referencia vigente de la API (§5.3).

## Restricciones que rompen el servicio

| Regla | Detalle |
|---|---|
| ID del modelo | Exactamente **`claude-sonnet-5`**. **Sin sufijo de fecha.** `claude-sonnet-5-20251101` no existe |
| `temperature`, `top_p`, `top_k` | **Eliminados. Enviarlos devuelve 400.** El reflejo habitual `ChatAnthropic(temperature=0)` **rompe el servicio entero** |
| `budget_tokens` | Eliminado. Devuelve 400 |
| `thinking` | El único modo válido sería `{"type": "adaptive"}`. **Aquí se deja desactivado**: la latencia importa más y la tarea es enrutamiento simple |
| Prefill del asistente | No soportado. No se puede forzar formato prellenando el último turno |
| `system` a mitad de conversación | No soportado. El system prompt va en el campo `system` de nivel superior |
| `max_tokens` | `MAX_OUTPUT_TOKENS = 1024` |

**El determinismo se busca por prompt, no por sampling.** No hay sustituto para
`temperature=0`; no se intenta emular con otros parámetros.

> **Riesgo R-01, a verificar en F1.** `langchain-anthropic` puede inyectar `temperature` por
> defecto al construir la petición. **Se debe confirmar con una petición real, capturando el
> cuerpo HTTP saliente**, que no se envían parámetros de sampling. Si el wrapper los inyecta
> y no permite suprimirlos, **se sustituye el nodo LLM por el SDK oficial `anthropic`**
> invocado directamente dentro del nodo de LangGraph, conservando el resto del grafo intacto.
> El resultado se registra como acuerdo `hallazgo`.

## Caché de prompt: obligatoria, y es la palanca de coste principal

- Un `cache_control: {"type": "ephemeral", "ttl": "1h"}` sobre el **último bloque del system
  prompt**. El orden de renderizado es `tools → system → messages`, de modo que una marca ahí
  cachea las definiciones de las tres herramientas y el system prompt juntos.
- **TTL de 1 hora, no el de 5 minutos por defecto.** La elección depende del **hueco entre
  peticiones que comparten prefijo**, no de la duración de la conversación. Con ~3 consultas
  por hora las peticiones llegan separadas ~20 minutos: un TTL de 5 minutos estaría frío casi
  siempre y **cada petición pagaría la prima de escritura**. Ahorro medido: **25,2 %** frente
  a no cachear.
- **El TTL debe ser configurable, no incrustado** (R-16). Si el tráfico pasara a continuo
  —peticiones a menos de 5 minutos—, el TTL de 5 minutos vuelve a ser estrictamente más barato.

### La trampa del suelo de 1.024 tokens (R-14)

El prefijo cacheable (`tools` + `system`) **debe superar los 1.024 tokens**. El perfil
objetivo lo deja en ~1.300.

> **Recortar el system prompt o las descripciones de herramientas por debajo de ese suelo
> desactiva la caché en silencio, sin ningún error, y encarece el sistema en lugar de
> abaratarlo.** Es el caso en que una optimización razonable produce el efecto contrario.

Cualquier recorte futuro del prompt **debe** verificar `cache_read_input_tokens > 0` antes de
darse por bueno.

### Invalidadores silenciosos prohibidos

**Nada variable dentro del system prompt.** Ni marcas de tiempo, ni `request_id`, ni
`employee_id`. Un solo byte que cambie anula la caché en cada petición. El system prompt vive
en `src/agent/prompts.py` como **constante única y byte-estable**.

### Verificación obligatoria

Una prueba de integración **debe** afirmar que en una segunda petición idéntica
`usage.cache_read_input_tokens > 0`. Es el criterio de salida de F6.

## Perfil de tokens objetivo (§9.3) — es presupuesto, no estimación

| Componente | Tokens |
|---|---:|
| System prompt | 600 |
| Definiciones de las 3 herramientas | 700 |
| **Prefijo cacheable** | **1.300** (debe superar 1.024) |
| Historial (`HISTORY_WINDOW_MESSAGES = 8`) | ~550 |
| Mensaje del usuario | 60 |
| Salida llamada 1 (`tool_use`) | 80 |
| Resultado de herramienta | ≤ 450 |
| Salida llamada 2 (respuesta) | 220 |

Si el system prompt o los payloads lo desbordan, **el techo de §9.4 deja de cumplirse**.

## Precios y coste unitario (§9.1)

Entrada 2,00 USD/MTok · Salida 10,00 · Lectura de caché ≈ 0,20 · Escritura TTL 1 h ≈ 4,00.
**Coste por consulta con caché de 1 h: 0,00875 USD.**

Elección frente a Opus 5: la tarea es **enrutamiento y síntesis breve**, no razonamiento
profundo. Sonnet 5 cuesta 2,5× menos y tiene menor latencia, que aquí es requisito de
producto (§1.2), no preferencia.

## Criterio de terminado

Una petición real responde sin 400, el cuerpo HTTP saliente no contiene parámetros de
sampling, y la segunda petición idéntica registra `cache_read_input_tokens > 0`.
