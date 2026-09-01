# Brief para generar la presentación — "Cómo se construyó AeroNova con Claude Code"

> **Para el agente que reciba este paquete.** No tienes acceso al repo original.
> Todo lo que necesitas está en esta carpeta (`ppt-context/`). Tu tarea: producir
> una presentación (PPT/Google Slides/Keynote/`.pptx` con `python-pptx`, o un
> deck en HTML/Marp si se pide) que explique **cómo se construyó el sistema
> agéntico AeroNova usando Claude Code**, con énfasis en las **buenas prácticas
> de ingeniería asistida por agente** que se aplicaron. No es un pitch de
> producto: el tema es el **método de trabajo**.

---

## 1. Qué se pide

- **Público:** equipo técnico y de producto que quiere adoptar Claude Code para
  proyectos serios. Conocen la nube y Python; no conocen este proyecto.
- **Duración:** 12–18 diapositivas, ~15 min de exposición.
- **Mensaje central:** con Claude Code se puede llevar un proyecto de
  infraestructura real de cero a producción **sin perder control**, si se le
  monta un **arnés**: plan vivo, contratos, puertas de fase, registro de
  decisiones, skills reutilizables y criterios de aceptación numéricos.
- **Tono:** concreto, con evidencia. Cada práctica va acompañada de "qué problema
  evita" y "cómo se ve en el repo".
- **Idioma:** español (México), sobrio.
- **Incluir el GIF** `aeronova_demo.gif` en una diapositiva de demo en vivo.

---

## 2. El sistema en un párrafo (contexto, no es el foco)

AeroNova es un **agente conversacional para el personal de mostrador** de una
aerolínea. Responde en español sobre estado de vuelos, reservas y normativa
interna. Es un **ReAct sobre LangGraph** (`load_memory → pensar ⇄ herramientas →
redactar → persistir`), con **15 herramientas de solo lectura**, **RAG** de
políticas (Titan Embeddings V2 + LanceDB), **memoria de sesión** en DynamoDB con
TTL, y **defensa en capas contra inyección de prompts**. Corre en AWS serverless
(API Gateway REST → Lambda de contenedor arm64 → DynamoDB/S3), descrito
íntegramente en **Terraform** (dos stacks). El coste está topado de fábrica
(caché de prompt, tope de rondas, cuota mensual, cortacircuitos por sesión,
presupuesto de AWS). Los datos son **sintéticos y deterministas** (seed 42),
validados por una cadena **medallion** con diez expectativas de calidad.

---

## 3. Números para las diapositivas de cifras

| Métrica | Valor | Fuente en el paquete |
|---|---|---|
| Fases del proyecto (F0–F10) | 11, cerradas con evidencia | `PLAN.md` |
| Commits | ~102, uno por hito de fase | `STATS.md` |
| Líneas de Python (src+pipelines+scripts+tests) | ~10 000 | `STATS.md` |
| Funciones de test | ~341 | `STATS.md` |
| Skills reutilizables | 23 | `SKILLS.md` |
| Herramientas del agente | 15, todas de solo lectura | `README.md` |
| Recursos de Terraform | ~61 en 2 stacks | `STATS.md` |
| Dataset dorado de aceptación | 53 casos / 14 familias, 8 umbrales, todos OK | `golden_result.txt` |
| Precisión de selección de herramienta | 100 % (umbral ≥ 90 %) | `golden_result.txt` |
| Prueba de carga | 500 sesiones, encolado y TTL verificados | `load_test_result.json` |
| Coste de una consulta (con caché 1 h) | ~0,009 USD | `aeronova_entregable_tarea2_publico.pdf` §6.4 |
| Infraestructura recurrente | ~0,40 USD/mes | idem |
| Gasto real de todo el desarrollo | ~3 USD | idem |
| Expectativas de datos | E-01…E-10, todas `pass` | `entregable` §6.3 |

---

## 4. El arnés: cómo se organizó el trabajo con Claude Code

El proyecto no se hizo "pídele a Claude que programe". Se montó una estructura
que el agente lee y actualiza en cada turno. **Esto es lo que hay que explicar.**

### 4.1 Documento normativo separado de la implementación
- `documents/PRD.md` (1 578 líneas): el **qué** y el **porqué**. Requisitos
  numerados (`DEBE`), restricciones de diseño (`D-NN`), riesgos (`R-NN`),
  invariantes (`I-NN`). No cambia salvo decisión explícita.
- El agente **no lee el PRD entero** en cada turno (arruina el presupuesto de
  tokens): cada tarea del plan cita las secciones que la gobiernan.

### 4.2 Plan vivo como única fuente de verdad del avance
- `memory/PLAN.md`: qué se hizo (`[x]` con evidencia), qué falta (`[ ]`), en qué
  fase estamos, cuánto presupuesto queda. Se lee **al empezar cada turno** y se
  escribe **después de cada actividad**. "Un agente que no lo lee alucina
  progreso; un agente que no lo escribe lo pierde."
- Cada `[x]` lleva su **evidencia** (comando ejecutado, salida, archivo).

### 4.3 Registro de decisiones (acuerdos)
- `memory/acuerdos/ACU-NNN-*.md` + índice `memory/INDEX.md`.
- Cuatro tipos: **decisión** (aprobada por el usuario), **hallazgo** (hecho no
  obvio verificado), **desviación** (cambio autorizado respecto al PRD),
  **contradicción** (dos secciones del PRD chocan → bloquea avance hasta
  resolver).
- El índice guarda solo un puntero + gancho de una línea; el contenido vive en el
  archivo. Ejemplos reales: ACU-001 (no usar AgentCore), ACU-003 (hallazgo:
  `langchain-anthropic` no inyecta parámetros de sampling), ACU-007
  (contradicción del PRD sobre el volumen de vuelos, resuelta capando a 9 000).

### 4.4 Puertas de fase (phase gates)
- `skills/phase-gate`: al cerrar F0…F10 se **ejecuta la comprobación real** del
  criterio de salida y se exige evidencia antes de avanzar. Sin excepción.
- `skills/harness-reentry`: justo después de cada puerta, el agente **relee** el
  arnés y las secciones que gobiernan la fase siguiente, y firma una
  "declaración de conformidad con evidencia" — antídoto contra la deriva
  acumulada.
- `skills/git-checkpoint`: la fase se confirma en git **solo** cuando pasó su
  puerta; incluye una revisión de higiene que impide subir un secreto.

### 4.5 Intake socrático antes de programar
- `skills/socratic-intake`: cada fase abre generando preguntas, respondiéndolas
  **citando secciones del PRD**, separando lo que se sabe de lo que se supone y
  pidiendo confirmación. **No se escribe una línea de código con un "NO SÉ" en
  pie.**

### 4.6 Skills = procedimientos reutilizables
- 23 skills en `skills/` (ver `SKILLS.md`). Cada una encapsula un procedimiento
  con su "cuándo usarla": `langgraph-agent`, `rag-index`, `medallion-pipeline`,
  `terraform-stacks`, `injection-defense`, `cost-gate`, `golden-dataset`,
  `observability-aws`, `llm-sonnet5-config`, etc.
- Efecto: el conocimiento del proyecto no vive en el hilo de chat, vive en
  archivos que el agente carga cuando toca.

### 4.7 Puerta de coste
- `skills/cost-gate`: **antes** de cualquier gasto (llamada al LLM en lote,
  siembra de datos, `terraform apply`, prueba de carga) se estima coste unitario,
  coste total, consumo de presupuesto y de cuota, y se pide aprobación.
- Presupuesto del proyecto declarado y seguido en `memory/costes.md`.

---

## 5. Buenas prácticas de ingeniería (el catálogo para las diapositivas)

Cada una: **práctica → problema que evita → evidencia en el paquete**.

1. **Contratos de datos + expectativas de lote** (`data-contracts`,
   `medallion-pipeline`). Contratos Pydantic v2 gobiernan la carga Bronze→Silver;
   expectativas E-01…E-10 a nivel de lote. Si una expectativa crítica falla, el
   pipeline **aborta** y el sistema se queda con "los datos de ayer", nunca con
   "datos rotos". *Evita:* corromper producción con un dataset malo. *Evidencia:*
   `entregable` §6.3 (E-01…E-10 `pass`), E-10 ("todo vuelo en estado operado
   tiene ≥ 1 reserva") se añadió al detectar el hueco.

2. **Datos sintéticos deterministas** (`synthetic-data`). `--seed 42`, sin LLM,
   plantillas + Faker; anomalías repartidas en dos "rutas" para probar la
   cuarentena y el manejo de datos corruptos. *Evita:* pruebas irreproducibles y
   depender de datos reales. *Evidencia:* `scripts/generate_synthetic.py` (no
   incluido, descrito en el entregable).

3. **RAG versionado e inmutable** (`rag-index`). Índice LanceDB con nombre
   `v=<timestamp>`, puntero `CURRENT` en S3, prueba de humo (5 consultas ≥ 0,35)
   y conmutación atómica; `rollback_rag.py` revierte sin redesplegar. *Evita:*
   que una recarga de corpus degrade la calidad sin vuelta atrás. *Evidencia:*
   `entregable` §6.3, `golden_result.txt` (familias `rag_aislado`, `rag_cruzado`).

4. **Regla de cifra canónica en el corpus.** Todos los documentos de una
   categoría afirman **el mismo número** para la misma norma. *Evita:* que el RAG
   recupere fragmentos que se contradicen y el agente no pueda dar una respuesta
   firme. *Evidencia:* comentario en el generador citado en el entregable.

5. **Defensa en capas contra inyección de prompts** (`injection-defense`).
   Tres vectores (documento recuperado, campo de datos, mensaje de usuario);
   D-1…D-6: escape de delimitadores, envoltura `<dato_operativo>` /
   `<documento_recuperado>` tratada como dato y no como orden, marcado de entrada
   sospechosa, filtro de salida que ni siquiera repite el texto inyectado.
   *Evidencia:* `golden_result.txt` familias `injection_*` (7/7, 4 familias).

6. **Límites de entrada con presupuesto de tokens** (L-1…L-6). Mensaje ≤ 1 200
   caracteres, ratio caracteres/tokens, prompt ensamblado ≤ 4 000 tokens con
   recorte de historial del más antiguo al más reciente. *Evita:* costes que se
   disparan y entradas abusivas. *Evidencia:* `golden_result.txt` familia
   `abuse_*` (rechazo **antes** de llamar al modelo, coste 0).

7. **Configuración del LLM a prueba de 400** (`llm-sonnet5-config`).
   `claude-sonnet-5` exacto; **sin** `temperature`/`top_p`/`top_k`; `thinking`
   desactivado; `cache_control` TTL 1 h sobre el system prompt (la principal
   palanca de coste, ~−25 %/consulta); `timeout` por debajo del techo de 29 s de
   API Gateway, `max_retries=0`. *Evidencia:* `entregable` §6.4.

8. **Dataset dorado como criterio de aceptación** (`golden-dataset`). 53 casos en
   14 familias, 8 umbrales numéricos, caché en disco por huella (prompt + tools +
   modelo), ejecución `--smoke` / `--full`. Se corre contra el **endpoint
   desplegado**, no contra mocks. *Evidencia:* `golden_result.txt`.

9. **Prueba de carga con `dry_run`** (`load-test-dryrun`). 500 sesiones para
   medir **encolado y TTL** sin pagar 500 llamadas al LLM. *Evidencia:*
   `load_test_result.json` (275 OK / 225 encoladas-rechazadas 429/503, TTL de
   DynamoDB verificado en 23/23).

10. **Infraestructura como código, en dos stacks** (`terraform-stacks`). Una
    Lambda de imagen exige que la imagen exista en ECR antes del `apply`, así que
    un stack único sería circular: `00-bootstrap` (ECR, DynamoDB, S3, SSM) y
    `10-app` (Lambda, API GW, CloudFront, alarmas). IAM acotado por ARN. **Ningún
    recurso se crea a mano por consola.** *Evidencia:* `STATS.md`, `README.md`
    (runbook).

11. **Sin secretos en Git.** `.gitignore` cubre `*.tfstate`, `.env`, `.tfvars`,
    `*.pem`. La clave de Anthropic vive solo en **SSM SecureString**, cargada a
    mano con `aws ssm put-parameter`, nunca por variable de Terraform. La
    revisión de higiene de `git-checkpoint` lo verifica en cada commit.
    *Evidencia:* `README.md` §Notas; el propio paquete lleva la versión **pública
    sin credenciales** del entregable.

12. **Observabilidad para correlacionar** (`observability-aws`). Logs JSON con
    redacción de PII, métricas EMF, trazas en **LangSmith** (qué pensó, qué
    herramienta llamó, qué devolvió), 10 alarmas de CloudWatch → SNS. *Evita:* no
    poder ligar una caída de calidad con una recarga de datos. *Evidencia:*
    `entregable` §4 (rail "Observabilidad y operación").

13. **Etiqueta de imagen = SHA de Git, nunca `latest`** (`lambda-container`).
    Con `latest`, Terraform no detecta el cambio y la Lambda conserva la imagen
    vieja. *Evidencia:* `README.md` paso 4; `scripts/build_and_push.sh`.

14. **Corrección guiada por síntoma real.** Ejemplos del cierre: el 504 bajo
    carga (se ajustó el reloj de pared del turno y el `timeout` del LLM por
    debajo de los 29 s); el `INTERNAL_ERROR` en conversación larga (se re-sanea
    el historial tras recortar por tokens); el corpus sin cobertura de "equipaje
    extraviado" que el agente sugería y no podía responder (se amplió
    `_FRASES_CATEGORIA` en las 7 categorías y se re-embebió el índice). *Evidencia:*
    `git log` resumido en `STATS.md`, `golden_result.txt` sin regresión.

---

## 6. Guion de diapositivas propuesto

Ajusta libremente, pero cubre estos hitos:

1. **Portada** — "De cero a producción con Claude Code: el caso AeroNova".
   Subtítulo: un agente conversacional serverless, construido con arnés.
2. **El problema de programar con un agente sin arnés** — alucina progreso,
   reabre decisiones, se salta pruebas, gasta sin control. (bullets del §4 intro)
3. **La idea: montar un arnés que el agente lee y escribe** — diagrama simple:
   PRD (qué) · PLAN.md (estado) · acuerdos (decisiones) · skills (procedimientos)
   · golden (aceptación).
4. **Plan vivo** — captura del formato `[x]/[ ]` con evidencia; la frase "un
   agente que no lo lee alucina progreso".
5. **Registro de decisiones** — los 4 tipos; 2–3 ACU reales (001, 003, 007).
6. **Puertas de fase + reentrada** — F0…F10, comprobación real, `git-checkpoint`
   con revisión de secretos.
7. **Intake socrático** — "no se escribe código con un NO SÉ en pie".
8. **Skills reutilizables** — rejilla con las 23 (de `SKILLS.md`); destacar 4–5.
9. **Datos: contratos + medallion + expectativas E-01…E-10** — el pipeline
   aborta antes que cargar datos rotos; caso E-10 añadido al detectar el hueco.
10. **RAG versionado** — índice inmutable + `CURRENT` + smoke test + rollback;
    regla de cifra canónica.
11. **Seguridad: inyección en 3 vectores + límites de entrada** — D-1…D-6;
    `abuse_*` rechaza antes del modelo.
12. **Coste topado de fábrica** — caché 1 h, tope de rondas, cuota, cortacircuitos,
    Budget; `cost-gate` antes de cada gasto; ~0,009 USD/consulta, ~3 USD todo el
    proyecto.
13. **Aceptación: el dataset dorado** — 53 casos, 8 umbrales, 100 % selección de
    herramienta; se corre contra el endpoint real. (pegar bloque de
    `golden_result.txt`)
14. **Carga** — 500 sesiones con `dry_run`; encolado y TTL verificados sin pagar
    500 llamadas.
15. **Demo en vivo** — insertar `aeronova_demo.gif` (grabación de la web real:
    estado de vuelo, reserva, política/RAG, radar operativo con gráficas,
    nacionales vs internacionales).
16. **Resultado y aprendizajes** — números del §3; 3 aprendizajes: (a) el arnés
    es barato y se paga solo, (b) evidencia por tarea mata la alucinación de
    progreso, (c) las skills convierten el chat en un sistema repetible.

Notas del orador: para cada práctica, di el problema concreto que evita (columna
"Evita" del §5). Evita jerga de marketing.

---

## 7. Assets en este paquete

| Archivo | Para qué |
|---|---|
| `BRIEF.md` | este documento |
| `aeronova_demo.gif` | capturas **reales** de la web desplegada (Chrome sobre CloudFront), 5 consultas — diapositiva 15 |
| `README.md` | arquitectura, estructura, runbook |
| `PRD.md` | documento normativo completo (referencia; no leerlo entero) |
| `PLAN.md` | plan vivo con el estado por fase |
| `INDEX.md` + `acuerdos/` | registro de decisiones |
| `SKILLS.md` | inventario de las 23 skills con su descripción |
| `STATS.md` | métricas del repo + `git log` resumido |
| `costes.md` | presupuesto y gasto real |
| `guia_uso_ui.md` | cómo se usa la interfaz desplegada |
| `golden_result.txt` | resultado del dataset dorado (53/53) |
| `load_test_result.json` | resultado de la prueba de carga |
| `aeronova_entregable.pdf` | entregable ejecutivo Tarea 1 |
| `aeronova_entregable_tarea2_publico.pdf` | entregable ejecutivo Tarea 2 (sin credenciales) — buena fuente de diagramas |

---

## 8. Reglas

- **No inventes cifras.** Si un dato no está en el paquete, dilo o pídelo.
- Los dos PDF de entregable ya tienen diagramas (arquitectura, bucle ReAct,
  medallion) que puedes reutilizar como imágenes en las diapositivas.
- El GIF es la única demo; no prometas una demo interactiva.
- No incluyas la `x-api-key` ni la URL del endpoint en la presentación (el
  entregable de este paquete es la versión pública, ya redactada).
- Si generas `.pptx`, usa `python-pptx`; si se pide algo más rápido, un deck
  **Marp** (Markdown) es aceptable.
