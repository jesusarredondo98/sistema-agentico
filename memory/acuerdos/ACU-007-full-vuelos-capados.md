---
id: ACU-007
titulo: El perfil `full` capa los vuelos a 9.000 (el patrón `^AN\d{3,4}$` no da para 90.000)
tipo: desviacion
estado: vigente
fase: F9
prd_ref: ["§7.2", "§5.4", "§16", "I-15"]
aprobado_por: usuario
fecha: 2026-08-30
---

**Contradicción detectada (I-15).** El PRD pide dos cosas incompatibles:

- §7.2 / §16: el entregable y F9 se construyen con `--profile full` = **90.000 vuelos**,
  100.000 reservas, 150 documentos.
- §5.4: el código de vuelo está fijado en `^AN\d{3,4}$`. Eso deja **9.900 códigos
  únicos posibles** (`AN100`…`AN9999`), y la tabla `aeronova-flights` los usa como
  **clave primaria única**.

No se puede tener 90.000 vuelos con código único que case `^AN\d{3,4}$`. El generador
(`gen_flights`, bucle `while len(codigos) < n` con `rng.randint(100, 9999)`) entra en
**bucle infinito** al pasar de ~9.900. `full` **nunca fue construible** tal cual: F2b solo
corrió `dev` (4.500 vuelos < 9.900).

**Qué se acordó (opción A).** `PROFILES["full"]["flights"]` pasa de 90.000 a **9.000**
(deja ~900 códigos libres para las referencias huérfanas de la ruta A). Reservas y corpus
sin cambios (100.000 / 150): el PNR `^[A-Z0-9]{6}$` tiene 2.200 M de combinaciones, no hay
problema. El entregable §16 se construye con este `full` (≈ 109.150 items) y muestra
`profile: full, flights: 9000` en el `_manifest.json`.

**Por qué esta y no otra.**
- No se relaja `^AN\d{3,4}$` (opción B): rompería tools, regex de la UI, `test_examples`,
  el golden dataset y los ejemplos, por un número de portada.
- No se añade fecha a la clave de vuelos (opción D): cambia la PK en `00-bootstrap`, obliga
  a que `consultar_estado_vuelo` reciba una fecha y a re-desplegar.
- `dev` (opción C) era válida —§7.2 dice que conserva todas las proporciones y casos
  borde— pero el usuario prefiere el volumen alto de reservas en el entregable.

**Cómo se aplica.**
- `scripts/generate_synthetic.py`: `PROFILES["full"]["flights"] = 9_000`. `gen_flights`
  pasa a construir el pool completo `AN100..AN9999` y muestrear `n` (rápido y sin bucle).
- El `_manifest.json` de Gold seguirá registrando `profile` y los `counts` reales.
- F9 (golden dataset + prueba de carga) y F10 (PDF) corren sobre este `full`.

**Qué invalida este acuerdo.** Que se decida ampliar el patrón de código de vuelo o cambiar
la clave de la tabla, en cuyo caso se podría volver a 90.000 vuelos.
