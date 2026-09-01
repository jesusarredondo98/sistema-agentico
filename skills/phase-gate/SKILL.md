---
name: phase-gate
description: Verifica el criterio de salida de una fase F0-F10 del PRD antes de permitir avanzar a la siguiente, ejecutando la comprobación real y exigiendo evidencia. Úsala al final de cada fase, sin excepción. Aplica la regla de parada del PRD §14.
---

# Puerta de fase

El PRD §14 fija una regla que no admite matices:

> **Si una fase no alcanza su criterio de salida, el agente DEBE detenerse y reportar, no
> avanzar a la siguiente.**

Esta skill la hace operativa. No verifica que el trabajo *parezca* hecho: **ejecuta la
comprobación** y exige la salida del comando como prueba.

## Los once criterios de salida (PRD §14)

| Fase | Criterio de salida | Comprobación real |
|---|---|---|
| **F0** | La imagen construye para arm64 | `docker build --platform linux/arm64 .` → exit 0, imagen < 2 GB |
| **F1** | Una petición real responde sin 400, sin parámetros de sampling | Petición real + captura del cuerpo HTTP saliente |
| **F2** | Un lote con referencia colgante aborta por E-02; uno válido pasa | `pytest tests/contracts/` en verde, cobertura ≥ 95 % |
| **F2b** | Un `get_item` recupera un vuelo y un PNR conocidos; cuarentena de reservas ≈ 3 % | `aws dynamodb get-item` × 2 + `quarantine_rate` del manifiesto |
| **F3** | Pruebas unitarias en verde, incluidos los registros corruptos de Gold | `pytest tests/unit/` + cobertura ≥ 80 % en `src/tools/` y `src/logic/` |
| **F4** | Una consulta de política devuelve fragmentos sobre el umbral; el rollback retrocede y vuelve a avanzar | Consulta real + `rollback_rag.py --to <ts>` ida y vuelta |
| **F5** | El escenario de memoria multi-turno funciona en local | Turno 1 da el PNR, turno 2 lo reutiliza sin volver a pedirlo |
| **F6** | `cache_read_input_tokens > 0` en la segunda petición | Prueba de integración que lo afirma |
| **F7** | El endpoint responde 200 a una petición real | `curl` con `x-api-key` contra `api_url` |
| **F8** | Conversación multi-turno desde el navegador; U-1 a U-14 superadas | Lista de §8.5 completa con su resultado |
| **F9** | Todos los umbrales de §8.3 cumplidos | **Corrida completa**, nunca `--smoke` (R-17) |
| **F10** | Entregable §16 completo | Los 7 puntos verificados uno a uno |

## Procedimiento

### 1. Ejecutar, no razonar

La comprobación se **ejecuta**. Un criterio de salida evaluado por razonamiento («debería
funcionar porque el código es correcto») es exactamente lo que la puerta existe para impedir.

### 2. Recorrer las actividades de la fase en `PLAN.md`

Toda actividad de la fase debe estar `[x]` con evidencia, `[-]` justificada o `[!]` con
acuerdo. **Una sola `[ ]` o `[~]` cierra la puerta.**

### 3. Verificar que no se ha construido de más

Contrastar contra PRD §0.3: ¿se ha añadido algún recurso, dependencia o capa que el PRD
prohíbe? La expansión de alcance por iniciativa propia es el riesgo R-12 y se detecta aquí,
no en la entrega.

### 4. Emitir el veredicto

```markdown
### Puerta de fase F4 — APROBADA | RECHAZADA

| Comprobación | Resultado | Evidencia |
|---|---|---|
| Consulta sobre umbral 0,35 | ✅ | score 0,71 en `POL-MAS-004` |
| Rollback ida y vuelta | ✅ | `CURRENT` v=…140311Z → v=…091802Z → v=…140311Z |
| Actividades A-60..A-68 | ✅ 9/9 | `PLAN.md` |
| Sin alcance añadido (§0.3) | ✅ | sin Glue, sin orquestador, sin catálogo |
| Gasto de la fase | 0,00 USD LLM + <0,01 Bedrock | `costes.md` |

**Veredicto:** aprobada. Siguiente fase: F5.
```

### 5. Si se rechaza

Se **detiene el trabajo** y se reporta: qué criterio falló, con qué salida concreta, qué se
intentó y qué opciones hay. **No se empieza la fase siguiente «mientras tanto».** El PRD lo
prohíbe y la razón es práctica: una fase con base defectuosa contamina todas las posteriores
y el coste de deshacerlo crece con cada fase.

### 6. Encadenar con `harness-reentry`

Una puerta aprobada **no cierra la fase**. Inmediatamente después se invoca
`harness-reentry`, que reverifica el entendimiento del arnés antes de abrir la siguiente. Ese
es el mecanismo antialucinación del proyecto.

## Antipatrones

- Aprobar con «falta un detalle menor». Un detalle menor sin evidencia es un fallo sin
  descubrir; el criterio de salida es binario.
- Sustituir la comprobación real por una prueba unitaria que la simula. F7 no se aprueba con
  un mock del endpoint: se aprueba con un `curl`.
- Usar `--smoke` como criterio de salida de F9. Lo prohíbe R-17 explícitamente.
- Aprobar F9 con datos del perfil `dev`. El entregable exige `full` (R-19).

## Criterio de terminado

Veredicto emitido con evidencia ejecutada, `PLAN.md` actualizado con el estado de la fase, y
`harness-reentry` invocada a continuación.
