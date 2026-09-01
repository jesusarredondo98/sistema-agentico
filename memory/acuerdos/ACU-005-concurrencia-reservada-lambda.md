---
id: ACU-005
titulo: Despliegue temporal con la Lambda sin concurrencia reservada (PRD §2.2 pide 20)
tipo: desviacion
estado: resuelto
fase: F7
prd_ref: ["§2.2", "§2.7", "I-01"]
aprobado_por: usuario
fecha: 2026-08-28
resuelto: 2026-08-30
---

**Qué desvía.** El PRD §2.2 fija `reserved_concurrent_executions = 20` en la Lambda del
agente como techo de gasto en rafaga (un valor "pinned", no ajustable sin decision). En el
primer `terraform apply` de `10-app`, AWS lo rechazo:

```
InvalidParameterValueException: Specified ReservedConcurrentExecutions for function
decreases account's UnreservedConcurrentExecution below its minimum value of [10]
```

La cuenta AWS arranca con el limite **global** de "Concurrent executions" en **10**
(default de cuenta nueva), verificado con:

- `aws lambda get-account-settings` -> `AccountLimit.ConcurrentExecutions = 10`
- `aws service-quotas get-service-quota --service-code lambda --quota-code L-B99A9384`
  -> `Value = 10.0`, `Adjustable = true`

AWS exige dejar >= 10 sin reservar, asi que con limite 10 el unico valor reservable es 0.

**Qué se acordó (opcion B).** Desplegar F7 **ahora** con la Lambda **sin concurrencia
reservada** (`-var="reserved_concurrency=-1"`), registrar la desviacion, y **restaurar a 20**
cuando Service Quotas apruebe el aumento del limite global a 1000 (solicitud ya enviada,
estado PENDING: `aws service-quotas list-requested-service-quota-change-history`).

**Por qué es aceptable de forma temporal.** El proposito de §2.2 (evitar una factura
descontrolada por rafaga) sigue cubierto por varias barreras que no dependen de este ajuste:

- Usage Plan del API Gateway: `quota_settings { limit = 2000, period = "MONTH" }` +
  throttle 10/20 (I-01).
- Cortacircuitos de coste por sesion (§12A.4): STATE acumula `cost_usd_acumulado`; a
  > 0.25 USD la sesion responde 429 `SESSION_BUDGET_EXCEEDED`.
- AWS Budgets de 20 USD con alarmas 50/80/100 % (§11).
- El propio limite de cuenta de 10 actua como techo de facto de concurrencia mientras siga
  vigente.

**Cómo se aplica.**

- `terraform/10-app/variables.tf`: `variable "reserved_concurrency"` con **default 20**
  (el valor del PRD sigue siendo el que manda en el codigo).
- `terraform/10-app/main.tf`: `reserved_concurrent_executions = var.reserved_concurrency`.
- Despliegue temporal: `terraform apply -var="image_tag=<sha>" -var="reserved_concurrency=-1"`.
- **Cierre de la desviacion** (cuando el usuario avise "cuota aprobada a 1000"): confirmar
  con `aws lambda get-account-settings` que `ConcurrentExecutions >= 30`, ejecutar
  `terraform apply -var="image_tag=<sha>"` **sin** el override (vuelve a 20), verificar en
  la consola / `aws lambda get-function-concurrency`, y pasar este acuerdo a `estado: resuelto`.

**Qué invalida este acuerdo.** Que AWS apruebe el aumento de cuota (se cierra restaurando
20), o que el sponsor decida que 20 ya no es el techo correcto (se actualiza el default de
la variable y el PRD).

---

**RESUELTO (2026-08-30).** Service Quotas aprobó el aumento del límite global de
concurrencia de la cuenta a **1000** (`aws lambda get-account-settings` -> 1000;
`service-quotas` L-B99A9384 -> 1000.0). Se restauró `reserved_concurrent_executions = 20`
con `terraform apply` sin el override (`aws lambda get-function-concurrency` ->
`ReservedConcurrentExecutions: 20`). El techo de gasto en ráfaga de §2.2 vuelve a estar
como lo pide el PRD.

---

**NOTA (2026-09-01) — subida temporal a 40 para hard testing.** Durante las
pruebas de estrés del cierre, ráfagas de >20 peticiones concurrentes chocaban
con el techo de 20 y API Gateway devolvía 500 (contrapresión esperada, pero
molesta en las pruebas). El sponsor pidió subir `reserved_concurrency` a **40**
mientras duran los hard tests. La cuenta lo permite (límite global 1000). El
techo de gasto en ráfaga de §2.2 sube de forma proporcional durante esta
ventana; el AWS Budget de 20 USD y el cortacircuitos por sesión siguen intactos.
**Volver a 20** (`terraform apply` sin override, default de la variable) al
terminar las pruebas.
