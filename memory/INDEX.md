# Índice de acuerdos

Una línea por acuerdo. **Nunca se guarda contenido aquí**, solo el puntero y el gancho que
permite decidir si merece la pena abrirlo.

Formato: `- [ACU-NNN](acuerdos/ACU-NNN-slug.md) — tipo · fase · gancho de una línea`

<!-- INICIO ACUERDOS -->
- [ACU-001](acuerdos/ACU-001-sin-agentcore.md) — decision · F-1 · No se usa AgentCore ni Bedrock Agents; Bedrock solo da embeddings Titan V2. Migrar exigiría rehacer §9 entero
- [ACU-002](acuerdos/ACU-002-rama-de-trabajo.md) — decision · F-1 · La implementación va en `feat/aeronova-implementacion`; un commit por fase; nunca push sin pedirlo
- [ACU-003](acuerdos/ACU-003-langchain-anthropic-sin-sampling.md) — hallazgo · F1 · `langchain-anthropic` 1.7.0 NO inyecta `temperature`/`top_p`/`top_k`; plan A de §5.3 confirmado, plan B descartado. R-01 no muerde con las versiones congeladas
- [ACU-004](acuerdos/ACU-004-usuario-iam-terraform.md) — decision · F2 · Despliegue con usuario IAM `aeronova-terraform` (perfil `aeronova`, AdministratorAccess), no root. Obligación de borrarlo en el teardown. `terraform apply`/`aws iam`/`ssm put-parameter` los ejecuta el usuario (clasificador de permisos)
- [ACU-005](acuerdos/ACU-005-concurrencia-reservada-lambda.md) — desviacion · F7 · **RESUELTO 2026-08-30**: Service Quotas subió el límite a 1000; `reserved_concurrent_executions` restaurado a 20
- [ACU-006](acuerdos/ACU-006-extras-de-demo.md) — desviacion · F8 · Extras de demo pedidos por el usuario: vista «Datos de prueba», contador de mensajes, gráfica RAG, Enter-envía, botón Contacto (hechos). Pendiente de OK: 3 tools nuevas (GSIs) + subir el tope de coste por sesión
- [ACU-007](acuerdos/ACU-007-full-vuelos-capados.md) — desviacion · F9 · Contradicción PRD (I-15): full=90k vuelos vs ^AN\d{3,4}$ (9.900 únicos, clave primaria). Resuelto: full capa vuelos a 9.000; reservas 100k y corpus 150 sin cambios
- [ACU-008](acuerdos/ACU-008-cuota-g1-al-doble.md) — desviacion · F10 · Cuota G-1 del Usage Plan de 2.000 a 10.000/mes (5x, sponsor): el tráfico de cierre (>3.000 pet.: golden x3 + carga x3 + pruebas manuales) agotó las 2.000. A 10.000 G-1 deja de ser el control vinculante; el techo real pasa a ser el AWS Budget de 20 USD (sin tocar) y el límite del workspace Anthropic
<!-- FIN ACUERDOS -->

## Acuerdos bloqueantes activos

Los acuerdos de tipo `contradiccion` en estado `vigente` **impiden avanzar de fase**. Se
listan aquí aparte para que el agente los vea sin abrir nada más.

*(Ninguno.)*
