---
id: ACU-001
titulo: No se usa Bedrock AgentCore; Bedrock solo provee embeddings
tipo: decision
estado: vigente
fase: F-1
prd_ref: ["D-02", "§2.1", "§2.5", "§5.1", "§5.3", "§0.3"]
aprobado_por: usuario (confirmado explícitamente: «mantengamos como está»)
fecha: 2026-08-26
---

**Qué se acordó.** Confirmado por el usuario el 2026-08-26. El sistema **no usa Amazon Bedrock AgentCore** ni Bedrock Agents. La
orquestación del agente es **LangGraph ejecutándose en la Lambda de contenedor**, con código
propio. El LLM de razonamiento es **`claude-sonnet-5` invocado contra la API de Anthropic
directamente**, no a través de Bedrock. Bedrock aparece **exclusivamente como proveedor de
embeddings** (`amazon.titan-embed-text-v2:0`) para el RAG.

**Por qué.** Evidencia recogida sobre `documents/PRD.md` v2.7:

- `grep -inE "agentcore|bedrock agent|knowledge base|action group|guardrail"` → **0 resultados**.
- Las 13 menciones de Bedrock se refieren todas a Titan Embeddings V2 (líneas 28, 112, 211,
  217, 253, 290, 642, 819, 934, 1109, 1407, 1458, 1507).
- El único permiso IAM de Bedrock es `bedrock:InvokeModel` sobre el ARN del modelo de
  embeddings (§2.5). No hay permisos de agente, de knowledge base ni de action group.
- La clave de Anthropic se lee de SSM y la Lambda llama a la API de Anthropic (§2.1, §2.7).

Tres decisiones del diseño dependen del control directo sobre la llamada al modelo:
la caché de prompt con **TTL de 1 h** como palanca de coste principal (−25,2 %, §5.3); el
**presupuesto de latencia** repartido en cinco tramos dentro de 29 s (§2.2); y el techo de
gasto sostenido por la cuota mensual del Usage Plan y la concurrencia reservada (§2.3, §9.5).

**Cómo se aplica.** No se introduce ninguna dependencia de AgentCore ni de Bedrock Agents en
`src/`, `terraform/` ni `requirements.txt`. El registro de herramientas vive en
`src/tools/__init__.py`, la memoria en DynamoDB (§4.5) y el grafo en `src/agent/graph.py`.

**Qué invalida este acuerdo.** Una decisión explícita del sponsor de migrar la orquestación a
AgentCore. Sería un cambio de arquitectura mayor —afecta a D-02, §2.1, §2.5, §5.1, §5.3 y a
todo el modelo de costes de §9— y **exigiría rehacer el modelo de costes desde cero**: el PRD
no contiene ninguna estimación para esa opción. No es un ajuste incremental.
