---
id: ACU-008
titulo: Cuota mensual G-1 del Usage Plan elevada de 2.000 a 10.000
tipo: desviacion
estado: vigente
fase: F10
prd_ref: ["§2.3", "§9.2", "§9.5", "I-01"]
aprobado_por: usuario
fecha: 2026-08-31
---

**Qué desvía.** El PRD §2.3 / §9.2 fija la cuota del Usage Plan de API Gateway en
**2.000 peticiones/mes** con `period = MONTH` como **techo duro estructural** del
gasto de LLM (G-1 de §9.5, ≈ 17,50 USD/mes). Es un valor "pinned".

**Qué se acordó.** Subir la cuota a **10.000/mes** — 5× las 2.000 del PRD
(`var.usage_plan_quota`, default en `terraform/10-app/variables.tf`). El sponsor lo
pidió explícitamente tras recibir en la UI:

> Servicio no disponible — El asistente ha alcanzado su cuota mensual de consultas.

Primera petición fue "el doble" (4.000); en el mismo intercambio la subió a
"5 veces más al inicial".

**Por qué se agotó.** El cierre del proyecto concentra tráfico que **no es de
producción y sí cuenta contra G-1** — §9.5 ya avisa de que `pytest tests/golden`,
`chat_cli.py` y la prueba de carga no la atraviesan por casualidad, son ~60 % del
presupuesto de §9.4. Desglose del mes:

| Origen | Peticiones aprox. |
|---|---:|
| F7/F8: despliegue, humo del endpoint, 2 rondas de CORS, fix de INTERNAL_ERROR (10 turnos), U-14 (9 ejemplos ×2), sondeos del rediseño Material | ~650 |
| F9: humo del golden durante el desarrollo (DOC_RE, forbid lists, prefijo RB) + corrida completa (49) | ~200 |
| F9: **prueba de carga del 2026-08-30** (100 reales + 400 dry_run) | 500 |
| F10 (día 31): golden completo tras cablear E-06 y rework de corpus | 49 |
| F10 (día 31): golden completo tras el fix del prompt (regla 2) | 49 |
| F10 (día 31): **reintento de la prueba de carga** que reventó en el chequeo de TTL por falta de `AWS_PROFILE` (las 500 HTTP sí se ejecutaron) | 500 |
| F10 (día 31): **segundo reintento de la prueba de carga** ya con perfil | 500 |
| Pruebas manuales del sponsor en la página | decenas |
| **Total** | **> 3.000** |

Los `warmup` por EventBridge y los `aws lambda invoke` directos **no** cuentan
(no pasan por API Gateway). El pico del día 31 (≈ 1.100) vino del rework del cierre:
dos golden completos porque se encontró que E-06 no estaba cableada y que el prompt
rechazaba PNRs válidos, y **dos pruebas de carga** porque la primera abortó en el
chequeo posterior de TTL (error de credenciales, ya blindado con try/except).

**Efecto en el control de costes.** El techo teórico de LLM pasa de ≈ 17,50 a
≈ 87,50 USD/mes **si cada petición fuese una llamada real al modelo** — no lo son
(los `dry_run` y los 429 no gastan tokens; el gasto real acumulado del proyecto va
por ~1,6 USD). Lo importante: **a 10.000, G-1 deja de ser el control vinculante.**
El techo real pasa a ser:

- **G-3 — AWS Budgets a 20 USD** con alertas al 50/80/100 % (§11). **No se toca.**
  Es ahora la barrera dura del lado AWS.
- **G-2 — límite de gasto del workspace de Anthropic** (fuera de Terraform, lo fija
  el operador). Es el único que cubre el gasto que no pasa por API Gateway.
- **§12A.4 — cortacircuitos de coste por sesión** (0,75 USD, ACU-006).

**Cómo se aplica.**

- `terraform/10-app/variables.tf`: `variable "usage_plan_quota"` default **10000**.
- `terraform apply` de `10-app` (lo ejecuta el usuario, clasificador de permisos).
- La cuota `period = MONTH` **nunca** pasa a `DAY` (I-01, hallazgo 38): con `DAY`
  serían ~26× el techo.

**Qué invalida este acuerdo.** Que el sponsor decida volver a 2.000 al cerrar la
demo (se restaura el default y este acuerdo pasa a `revertido`), o que el gasto
real se acerque a los 20 USD del AWS Budget (habría que renegociar Budget + cuota
a la vez).

---

**NOTA (2026-09-01) — 10.000 → 50.000.** El cierre siguió generando pruebas de
estrés (ráfagas de 20-40 concurrentes, regresiones repetidas, ajustes de
timeout, nueva tool `cobertura_reservas` con su golden). El sponsor pidió subir
la cuota a **50.000/mes** para no toparse durante los hard tests. Sigue sin ser
el control vinculante: el AWS Budget de 20 USD (G-3) y el límite del workspace
de Anthropic (G-2) son el techo real, y el gasto real del proyecto va por ~3-4
USD. `var.usage_plan_quota` default **50000**. `period = MONTH` intacto (I-01).
