---
name: load-test-dryrun
description: Ejecuta la prueba de carga de 500 sesiones con modo dry_run, que mide encolado y TTL sin pagar 500 llamadas al LLM. Úsala una sola vez, en F9. Requiere aprobación de coste y consume el 25 % de la cuota mensual.
---

# Prueba de carga

500 sesiones concurrentes contra el endpoint desplegado, un mensaje por sesión.
**Se ejecuta una sola vez, en F9, y su resultado se archiva.** No es una prueba de iteración.

## Qué mide realmente, y por qué eso cambia el diseño

La concurrencia reservada de 20 (§2.2) hace que las 500 **se encolen**.

> **La prueba mide el encolado y el TTL de DynamoDB, no la concurrencia real.** Esto es
> intencional y **debe documentarse en el informe** para no presentarlo como una prueba de
> escalado (hallazgo 29).

De ahí se sigue el modo `dry_run`: si lo que se mide es el encolado y el TTL, **la llamada al
LLM es incidental** y pagarla 500 veces es gasto que no compra señal (hallazgo 44).

## Modo `dry_run` — obligatorio en el handler

El handler acepta `{"dry_run": true}`, que **recorre el camino completo** —validación,
comprobación de propiedad de sesión, lectura de memoria, escritura de memoria con su
`expires_at`— y **corta antes de invocar el modelo**, devolviendo una respuesta sintética con
el contrato de §4.2.

| Regla | Motivo |
|---|---|
| `dry_run` queda **registrado en el log** de cada invocación | Trazabilidad |
| **NO** está disponible desde la UI | R-18 |
| La respuesta sintética **debe ser evidentemente artificial** | Que nadie la confunda con un dato real (R-18) |

## Reparto y coste

| Sesiones | Modo | Coste |
|---:|---|---:|
| 100 | LLM real | 0,88 USD |
| 400 | `dry_run` | 0,00 USD |
| **500** | | **0,88 USD** en lugar de 4,38 |

Las 100 reales bastan para confirmar que el camino completo aguanta bajo contención; las 400
restantes miden encolado y TTL, que es el objetivo declarado.

## Consumo de cuota — el detalle que sorprende

> **Las 500 sesiones consumen 500 peticiones de la cuota mensual G-1** (2.000/mes), un **25 %**,
> con independencia de que 400 sean `dry_run`: **la cuota cuenta peticiones al API Gateway, no
> llamadas al LLM.** Si se agota, el endpoint devuelve 429 el resto del mes.

Por eso la prueba se ejecuta en F9 y **no cerca de la entrega** (R-15): agotar la cuota antes
de la demo es un fallo de planificación, no técnico.

## Requisitos del script

- **Pide confirmación interactiva.**
- **Imprime el coste estimado antes de arrancar y el real al terminar.**
- Verificación de TTL: tras la carga, comprobar que los items tienen `expires_at` correcto.

> La expiración real de DynamoDB puede tardar **hasta 48 h**, así que se valida **el atributo,
> no la desaparición del item**.

## Criterio de terminado

Ejecutada una sola vez, con el reparto 100/400, coste real ≤ 1,00 USD registrado en
`memory/costes.md`, `expires_at` verificado como atributo, y la salvedad sobre encolado
redactada en el informe.
