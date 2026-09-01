---
name: guia-uso-ui
description: Guía paso a paso para abrir y usar la interfaz web desplegada de AeroNova (URL de CloudFront, dónde sacar la URL del API y la x-api-key, flujo de una consulta, límites visibles, qué hacer si falla).
metadata:
  type: reference
---

# Cómo usar la interfaz de AeroNova

La UI está publicada en **https://d1v908g2u3hf9q.cloudfront.net** (salida `ui_url` de
`terraform/10-app`). Es una página estática; toda la lógica corre en el navegador y llama al
endpoint del agente. Ver también [[acu-005-concurrencia-reservada-lambda]] (despliegue) y
`memory/PLAN.md` F7/F8.

## 1. Conseguir la URL del API y la x-api-key

```bash
cd /Users/jesusarredondo/Documents/augmented-humands/Tareas/m4/sistema_agentico
AWS_PROFILE=aeronova terraform -chdir=terraform/10-app output -raw api_url
AWS_PROFILE=aeronova terraform -chdir=terraform/10-app output -raw api_key
```

- `api_url` → algo como `https://lbsnyvy2ba.execute-api.us-east-1.amazonaws.com/prod/v1/chat`.
- `api_key` → la clave del Usage Plan (marcada `<sensitive>`, `output -raw` la imprime). Es la
  misma que se comparte con quien vaya a probar el servicio; da una autenticación simple por
  `x-api-key`, con cuota mensual de 2.000 peticiones (§2.3, I-01).

## 2. Configurar la conexión en la UI

1. Abre https://d1v908g2u3hf9q.cloudfront.net. En la **primera visita** se abre solo el panel
   «Cómo usar este asistente»; ciérralo con **Empezar**.
2. Arriba a la derecha, pulsa **Ajustes**.
3. Pega la **URL del API** y la **x-api-key**.
4. Pulsa **Guardar y usar**. Sale «Guardado ✓» y el panel se cierra solo. Los valores quedan
   en el `localStorage` de ese navegador (nunca viajan en el código de la página, S-05).
5. El aviso ámbar «Antes de empezar, abre Ajustes…» desaparece cuando la conexión está puesta.

## 3. Hacer una consulta

- Escribe en el campo de abajo y pulsa **Enviar** (o `Ctrl/Cmd + Enter`).
- Mientras responde, aparece «El asistente está consultando…».
- Cada respuesta del agente trae un desplegable **«Detalle de la ejecución»** (colapsado) con
  las herramientas usadas, las rondas y el coste del turno.
- Ejemplos que funcionan con los datos sembrados (seed 42):
  - `¿El vuelo AN1008 está demorado?` · `¿Se canceló el AN1049?`
  - `Dame los datos de la reserva YXMWYB`
  - `¿Puedo llevar un gato en cabina?` · `¿Qué compensación aplica por una demora de 4 horas?`
- Las tarjetas del estado vacío y el enlace **«¿Qué puedo preguntar?»** insertan el ejemplo en
  el campo con el marcador (`AN405`, `ABC123`) seleccionado para que lo sustituyas. **No se
  envían solas.**

## 4. Límites que verás (§10.2)

| Señal | Qué significa |
|---|---|
| Contador `N / 1200 caracteres` en ámbar (≥ 960) / rojo (> 1200) | L-1. En rojo, **Enviar** se desactiva |
| «El texto contiene mucho contenido no latino…» | L-2/L-3, antes de enviar, sin gastar |
| Banda «Turno 40 de 50…» | L-5, se acerca el límite de turnos de la sesión |
| Pastilla «Coste de sesión: 0,2xx USD de 0,25» | Cortacircuitos de coste (§12A.4). Al llegar a 0,25 sale un diálogo y hay que abrir sesión nueva |
| Nota «Se recortaron los N mensajes más antiguos… Los datos de la reserva activa se conservan.» | L-4, truncado de contexto. El PNR activo sigue vigente |
| «Servicio no disponible … cuota mensual» | G-1, la cuota de 2.000 peticiones/mes se agotó |

**Nueva sesión** (botón arriba a la derecha) limpia el hilo y genera un `session_id` nuevo.

## 5. Si el chat da error

- **«No se pudo contactar con el servicio»** → revisa la URL en Ajustes; comprueba que el
  endpoint responde: `curl -s -o /dev/null -w '%{http_code}' -X POST "<api_url>" -H "x-api-key: <key>" -H 'content-type: application/json' -d '{"employee_id":"EMP_001","session_id":"probe-0001","message":"hola","dry_run":true}'` → debe dar `200`.
- **Falla solo desde el navegador y no con curl** → suele ser CORS: la respuesta del POST
  **debe** llevar `Access-Control-Allow-Origin: https://d1v908g2u3hf9q.cloudfront.net`. Lo
  fija la env var `UI_ORIGIN` de la Lambda (`terraform/10-app`); si falta, `terraform apply`
  con esa variable y reconstruir la imagen.
- **403 sin más** → falta o está mal la `x-api-key`.
- **429** → o el cortacircuitos de coste de la sesión (abre sesión nueva) o la cuota mensual
  G-1 (contactar al responsable).
- El **primer** mensaje tras un rato inactivo puede tardar ~15-25 s (arranque en frío del
  contenedor); el ping de EventBridge cada 5 min mantiene uno caliente.

## 6. Redesplegar la UI tras un cambio en `ui/`

```bash
AWS_PROFILE=aeronova ./scripts/deploy_ui.sh   # s3 sync + invalidación de CloudFront
# o: make deploy-ui
```
