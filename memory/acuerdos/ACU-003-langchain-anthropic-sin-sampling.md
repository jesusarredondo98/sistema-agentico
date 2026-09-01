---
id: ACU-003
titulo: langchain-anthropic 1.7.0 no inyecta parametros de sampling; plan A de §5.3 confirmado
tipo: hallazgo
estado: vigente
fase: F1
prd_ref: ["§5.3", "R-01", "I-02"]
aprobado_por: verificado con peticion real capturada
fecha: 2026-08-27
---

**Qué se verificó.** Con `anthropic==1.2.0` y `langchain-anthropic==1.7.0` (versiones
congeladas en `requirements.txt`), un nodo construido como

```python
ChatAnthropic(model="claude-sonnet-5", max_tokens=1024, thinking={"type": "disabled"})
```

y **sin** tocar `temperature` / `top_p` / `top_k` produce un cuerpo HTTP saliente
(`POST /v1/messages`) con exactamente estas claves de nivel superior:

```
['max_tokens', 'messages', 'model', 'system', 'thinking']
```

No aparecen `temperature`, `top_p`, `top_k` ni `budget_tokens`, ni al nivel superior ni
anidados. La peticion real devuelve `stop_reason: "end_turn"` (HTTP 200), no 400.

**Por qué importa.** El riesgo R-01 (probabilidad media, impacto alto) es que
`langchain-anthropic` inyecte `temperature` por defecto y **todas** las peticiones a
Sonnet 5 devuelvan 400. Internamente el builder de payload de langchain-anthropic sí
incluye `"temperature": self.temperature` en el literal del diccionario, pero **elimina las
claves con valor `None` antes de enviar**, por lo que con los campos sin fijar no llegan al
cable. El defecto de fábrica de los tres campos es `None`.

**Cómo se aplica.**

- **Plan A de §5.3 confirmado:** el nodo LLM usa `langchain-anthropic` directamente. **No**
  se activa el plan B (SDK `anthropic` dentro del nodo).
- Nunca se pasa `temperature=...` (ni `0`) al constructor de `ChatAnthropic`. El
  determinismo se busca por prompt (§5.3).
- `thinking` se fija **explicitamente** a `{"type": "disabled"}`: omitirlo en Sonnet 5
  activa el modo adaptativo.
- La prueba `tests/integration/test_llm_node.py` captura el cuerpo saliente y afirma la
  ausencia de las cuatro claves. Es regresion permanente: si una futura version de
  `langchain-anthropic` cambia el comportamiento, esa prueba lo detecta antes de desplegar.
- F5 reutiliza `src/agent/llm_node.py:llm_node` sin cambios estructurales, solo anadiendo
  `bind_tools`.

**Qué invalida este hallazgo.** Subir `langchain-anthropic` o `anthropic` de version sin
volver a ejecutar la prueba de captura; o pasar a un modelo distinto de `claude-sonnet-5`.
