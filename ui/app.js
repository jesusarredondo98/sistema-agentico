/* AeroNova · lógica de la interfaz de mostrador (PRD §10.1–§10.5).
   Sin framework, sin dependencias. La x-api-key vive en localStorage y NUNCA
   en este fichero (S-05): el bundle es público a través de CloudFront.
   La validación de cliente es experiencia de usuario, NUNCA seguridad (§10.2,
   R-23): el servidor revalida siempre y es la única autoridad. */
"use strict";

// ---------------------------------------------------------------------------
// Constantes de límite — reflejan §12A.3 / §2.7. Si el servidor cambia, aquí
// también, pero el servidor manda.
// ---------------------------------------------------------------------------
const L1_MAX = 1200;
const L1_AVISO = 960;            // 80 %
const L2_MAX_TOKENS = 400;
const L3_MIN_RATIO = 1.5;
const L5_MAX_TURNS = 50;
const L5_AVISO_TURNO = 40;
// El servidor manda: si la respuesta trae `session.cost_usd_limit`, se usa ese.
// Estos son el valor por defecto (ACU-006 lo subio a 0,75 para la demo).
let COSTE_SESION_MAX = 0.75;
let COSTE_SESION_AVISO = 0.60; // 80 %

const LS = {
  apiUrl: "aeronova.apiUrl",
  apiKey: "aeronova.apiKey",
  sesion: "aeronova.sessionId",
  respVista: "aeronova.responsablePanelVisto",
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

// ---------------------------------------------------------------------------
// localStorage con guardas (puede lanzar en modo privado / previews).
// ---------------------------------------------------------------------------
function lsGet(k) { try { return localStorage.getItem(k); } catch { return null; } }
function lsSet(k, v) { try { localStorage.setItem(k, v); } catch { /* no-op */ } }

// ---------------------------------------------------------------------------
// Heurística de tokens — paridad con src/logic/limits.py::estimate_tokens.
// ---------------------------------------------------------------------------
function estimateTokens(text) {
  if (!text) return 0;
  const n = text.length;
  const b = new TextEncoder().encode(text).length;
  const base = Math.ceil(n / 3.2);
  const multibyte = b > n * 1.3 ? Math.ceil(b / 2.5) : 0;
  return Math.max(1, base, multibyte);
}

function motivoRechazoEntrada(msg) {
  const n = msg.length;
  const b = new TextEncoder().encode(msg).length;
  const tok = estimateTokens(msg);
  const dominaMultibyte = b > n * 1.3;
  const ratio = n / Math.max(tok, 1);
  // Si el texto es mayoritariamente no latino, ese es el motivo relevante para el
  // usuario, dispare L-2 o L-3 (§10.2, fila L-2/L-3).
  if (dominaMultibyte && (tok > L2_MAX_TOKENS || ratio < L3_MIN_RATIO)) {
    return "El texto contiene mucho contenido no latino y consume más tokens de lo permitido. Reformúlalo con menos caracteres especiales.";
  }
  if (tok > L2_MAX_TOKENS) {
    return `El mensaje estima ~${tok} tokens y el máximo es ${L2_MAX_TOKENS}. Acórtalo antes de enviar.`;
  }
  if (ratio < L3_MIN_RATIO) {
    return "El texto es demasiado denso (pocos caracteres por token). Reformúlalo de forma más natural.";
  }
  return null;
}

// ---------------------------------------------------------------------------
// Estado de sesión
// ---------------------------------------------------------------------------
const estado = {
  turno: 0,
  costeAcumulado: 0,
  enVuelo: false,
  ultimaBandaContador: "neutro", // para anunciar solo al cruzar umbral (§10.5)
};

function sesionId() {
  let id = lsGet(LS.sesion);
  if (!id) {
    id = (crypto.randomUUID && crypto.randomUUID()) ||
      ("s-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 10));
    lsSet(LS.sesion, id);
  }
  return id;
}

function nuevaSesion() {
  try { localStorage.removeItem(LS.sesion); } catch { /* no-op */ }
  estado.turno = 0;
  estado.costeAcumulado = 0;
  $("#hilo").innerHTML = "";
  $("#estado-vacio").hidden = false;
  $("#banda-turnos").hidden = true;
  $("#aviso-coste").hidden = true;
  pintarSesionId();
  refrescarContador();
  refrescarTurnos();
  $("#campo-mensaje").focus();
}

function pintarSesionId() { $("#sesion-id").textContent = sesionId(); }

function refrescarTurnos() {
  const usados = estado.turno;
  const quedan = Math.max(0, L5_MAX_TURNS - usados);
  const el = $("#turnos-restantes");
  el.textContent = `Mensajes disponibles en esta sesión: ${quedan} de ${L5_MAX_TURNS}`;
  el.classList.toggle("pocos", quedan <= L5_MAX_TURNS - L5_AVISO_TURNO); // <= 10 restantes
  el.classList.toggle("agotado", quedan === 0);
}

// ---------------------------------------------------------------------------
// Render de mensajes
// ---------------------------------------------------------------------------
function nodoMsg(clase, rol) {
  const li = document.createElement("li");
  li.className = `msg ${clase}`;
  if (rol) {
    const r = document.createElement("div");
    r.className = "msg-rol";
    r.textContent = rol;
    li.appendChild(r);
  }
  const b = document.createElement("div");
  b.className = "msg-burbuja";
  li.appendChild(b);
  return { li, burbuja: b };
}

function añadir(li) {
  $("#estado-vacio").hidden = true;
  $("#hilo").appendChild(li);
  $("#conversacion").scrollTop = $("#conversacion").scrollHeight;
}

function pintarUsuario(texto) {
  const { li, burbuja } = nodoMsg("msg-usuario", "Tú");
  burbuja.textContent = texto;
  añadir(li);
}

function pintarNotaSistema(texto) {
  // Informativa, NUNCA error (§10.2): truncado de contexto, finish_reason max_rounds.
  const { li, burbuja } = nodoMsg("msg-sistema");
  burbuja.textContent = texto;
  añadir(li);
}

function pintarError(codigo, mensaje) {
  const { li, burbuja } = nodoMsg("msg-error", "Error");
  burbuja.textContent = mensaje;
  if (codigo) {
    const c = document.createElement("code");
    c.textContent = " (" + codigo + ")";
    burbuja.appendChild(c);
  }
  añadir(li);
}

function tablaDetalle(cuerpo) {
  const d = document.createElement("details");
  d.className = "detalle";
  const s = document.createElement("summary");
  s.textContent = "Detalle de la ejecución";
  d.appendChild(s);
  const cd = document.createElement("div");
  cd.className = "detalle-cuerpo";
  cd.appendChild(cuerpo);
  d.appendChild(cd);
  return d; // colapsado por defecto (§10.1, R-24)
}

function pintarAgente(resp) {
  const { li, burbuja } = nodoMsg("msg-agente", "AeroNova");
  burbuja.innerHTML = markdownAgente(resp.reply || "");

  const cont = document.createElement("div");

  const tools = resp.tools_used || [];
  if (tools.length) {
    const t = document.createElement("table");
    t.innerHTML = "<thead><tr><th>Herramienta</th><th>Resultado</th><th>ms</th></tr></thead>";
    const tb = document.createElement("tbody");
    for (const u of tools) {
      const tr = document.createElement("tr");
      const ok = String(u.status).toLowerCase() === "ok";
      tr.innerHTML =
        `<td><code>${escaparHtml(u.name)}</code></td>` +
        `<td class="${ok ? "val-ok" : "val-mal"}">${escaparHtml(u.status)}</td>` +
        `<td>${u.latency_ms != null ? u.latency_ms : "—"}</td>`;
      tb.appendChild(tr);
    }
    t.appendChild(tb);
    cont.appendChild(t);
  }

  const u = resp.usage || {};
  const meta = document.createElement("div");
  meta.textContent =
    `Rondas de herramienta: ${resp.tool_rounds ?? 0}` +
    `  ·  tokens in/out: ${u.input_tokens ?? 0}/${u.output_tokens ?? 0}` +
    `  ·  caché: ${u.cache_read_input_tokens ?? 0}` +
    `  ·  coste turno: ${(u.cost_usd ?? 0).toFixed(6)} USD`;
  cont.appendChild(meta);

  // Gráficas BAJO DEMANDA: no se dibujan solas. Un botón por gráfica
  // disponible; al pulsarlo se dibuja (y se vuelve a ocultar).
  const charts = (resp.charts || []).filter((g) => g && (g.series || []).length >= 2);
  if (charts.length) {
    const barra = document.createElement("div");
    barra.className = "graficas-acciones";
    const et = document.createElement("span");
    et.className = "graficas-et";
    et.textContent = charts.length === 1 ? "Gráfica disponible:" : "Gráficas disponibles:";
    barra.appendChild(et);
    const zona = document.createElement("div");
    zona.className = "graficas-zona";
    for (const g of charts) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn-grafica";
      b.textContent = "📊 " + g.titulo;
      let dibujada = null;
      b.addEventListener("click", () => {
        if (dibujada) { dibujada.remove(); dibujada = null; b.classList.remove("activo"); return; }
        dibujada = pintarGrafica(g);
        if (dibujada) { zona.appendChild(dibujada); b.classList.add("activo"); }
      });
      barra.appendChild(b);
    }
    li.appendChild(barra);
    li.appendChild(zona);
  }

  li.appendChild(tablaDetalle(cont));
  añadir(li);

  // Nota de truncado — la SEGUNDA frase es la que importa (§10.2).
  const ctx = resp.context || {};
  if (ctx.truncated) {
    const n = ctx.messages_dropped || 0;
    pintarNotaSistema(
      `Se recortaron los ${n} mensaje${n === 1 ? "" : "s"} más antiguo${n === 1 ? "" : "s"} ` +
      "para caber en el contexto. Los datos de la reserva activa se conservan."
    );
  }
  // finish_reason max_rounds -> nota, no error (§10.2).
  if (resp.finish_reason === "max_rounds") {
    pintarNotaSistema(
      "No pude completar la consulta con la información disponible. " +
      "Prueba a indicar el código de vuelo o el PNR."
    );
  }
}

// Gráfica de barras SVG, sin librerías. Los datos vienen ya calculados por el
// servidor a partir de los campos de una herramienta (nunca del modelo).
function pintarGrafica(g) {
  const series = (g && g.series) || [];
  if (series.length < 2) return null;
  const W = 320, H = 24 * series.length + 12, LB = 96, max = Math.max(...series.map((s) => s.valor), 0.001);
  const NS = "http://www.w3.org/2000/svg";
  const wrap = document.createElement("figure");
  wrap.className = "grafica";
  const cap = document.createElement("figcaption");
  cap.textContent = g.titulo + (g.unidad ? ` (${g.unidad})` : "");
  wrap.appendChild(cap);
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", g.titulo + ": " + series.map((s) => `${s.etiqueta} ${s.valor}`).join(", "));
  series.forEach((s, i) => {
    const y = 12 + i * 24;
    const bw = Math.max(2, ((W - LB - 40) * s.valor) / max);
    const et = document.createElementNS(NS, "text");
    et.setAttribute("x", "0"); et.setAttribute("y", y + 11); et.setAttribute("class", "g-et");
    et.textContent = s.etiqueta.length > 14 ? s.etiqueta.slice(0, 13) + "…" : s.etiqueta;
    const bar = document.createElementNS(NS, "rect");
    bar.setAttribute("x", LB); bar.setAttribute("y", y); bar.setAttribute("width", bw);
    bar.setAttribute("height", "16"); bar.setAttribute("rx", "3"); bar.setAttribute("class", "g-bar");
    const val = document.createElementNS(NS, "text");
    val.setAttribute("x", LB + bw + 5); val.setAttribute("y", y + 11); val.setAttribute("class", "g-val");
    val.textContent = s.valor;
    svg.append(et, bar, val);
  });
  wrap.appendChild(svg);
  const nota = document.createElement("small");
  nota.className = "grafica-nota";
  nota.textContent = "Gráfica generada en tu navegador con los datos que devuelve la herramienta (sin IA).";
  wrap.appendChild(nota);
  return wrap;
}

function escaparHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

// Markdown MÍNIMO y seguro para las respuestas del agente. Se escapa TODO el
// HTML primero; solo después se aplican **negrita**, `código`, listas con "- "
// o "1." y saltos de párrafo. Nunca inyecta etiquetas del texto original.
function markdownAgente(texto) {
  const inline = (s) => escaparHtml(s)
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`\n]+)`/g, "<code>$1</code>");

  const lineas = String(texto || "").replace(/\r\n?/g, "\n").split("\n");
  const html = [];
  let lista = null;      // "ul" | "ol" | null
  let parrafo = [];      // líneas de texto que forman un mismo párrafo

  const cerrarLista = () => { if (lista) { html.push(`</${lista}>`); lista = null; } };
  const cerrarParrafo = () => {
    if (parrafo.length) { html.push(`<p>${parrafo.map(inline).join("<br>")}</p>`); parrafo = []; }
  };

  for (const cruda of lineas) {
    const l = cruda.trimEnd();
    const mUl = l.match(/^\s*[-*]\s+(.*)$/);
    const mOl = l.match(/^\s*\d+[.)]\s+(.*)$/);
    if (mUl) {
      cerrarParrafo();
      if (lista !== "ul") { cerrarLista(); html.push("<ul>"); lista = "ul"; }
      html.push(`<li>${inline(mUl[1])}</li>`);
    } else if (mOl) {
      cerrarParrafo();
      if (lista !== "ol") { cerrarLista(); html.push("<ol>"); lista = "ol"; }
      html.push(`<li>${inline(mOl[1])}</li>`);
    } else if (l.trim() === "") {
      cerrarParrafo();
      cerrarLista();
    } else {
      cerrarLista();
      parrafo.push(l);
    }
  }
  cerrarParrafo();
  cerrarLista();
  return html.join("");
}

// ---------------------------------------------------------------------------
// Medidores (§10.2)
// ---------------------------------------------------------------------------
function refrescarContador() {
  const val = $("#campo-mensaje").value;
  const n = val.length;
  const cont = $("#contador");
  const campo = $("#campo-mensaje");
  cont.textContent = `${n} / ${L1_MAX} caracteres`;

  let banda = "neutro";
  if (n > L1_MAX) banda = "roja";
  else if (n >= L1_AVISO) banda = "ambar";

  cont.classList.toggle("ambar", banda === "ambar");
  cont.classList.toggle("roja", banda === "roja");
  campo.classList.toggle("entrada-ambar", banda === "ambar");
  campo.classList.toggle("entrada-roja", banda === "roja");

  // Anunciar solo al CRUZAR un umbral, no en cada pulsación (§10.5).
  if (banda !== estado.ultimaBandaContador) {
    if (banda === "ambar") cont.setAttribute("aria-label", `Aviso: ${n} de ${L1_MAX} caracteres`);
    else if (banda === "roja") cont.setAttribute("aria-label", `Límite superado: ${n} de ${L1_MAX} caracteres, no se puede enviar`);
    else cont.removeAttribute("aria-label");
    estado.ultimaBandaContador = banda;
  }

  actualizarBotonEnviar();
}

function actualizarBotonEnviar() {
  const val = $("#campo-mensaje").value;
  const bloqueadoL1 = val.length > L1_MAX;
  $("#btn-enviar").disabled = estado.enVuelo || bloqueadoL1 || val.trim().length === 0;
}

function refrescarBandaTurnos() {
  const b = $("#banda-turnos");
  if (estado.turno >= L5_AVISO_TURNO && estado.turno < L5_MAX_TURNS) {
    b.hidden = false;
    b.innerHTML = "";
    const txt = document.createElement("span");
    txt.textContent = `Turno ${estado.turno} de ${L5_MAX_TURNS}. Al llegar al límite tendrás que iniciar una sesión nueva.`;
    const btn = document.createElement("button");
    btn.className = "btn btn-acento";
    btn.type = "button";
    btn.textContent = "Nueva sesión";
    btn.addEventListener("click", nuevaSesion);
    b.append(txt, btn);
  } else {
    b.hidden = true;
  }
}

function refrescarAvisoCoste() {
  const p = $("#aviso-coste");
  if (estado.costeAcumulado >= COSTE_SESION_AVISO && estado.costeAcumulado < COSTE_SESION_MAX) {
    p.hidden = false;
    p.textContent = `Coste de sesión: ${estado.costeAcumulado.toFixed(3)} USD de ${COSTE_SESION_MAX.toFixed(2)}`;
  } else {
    p.hidden = true;
  }
}

// ---------------------------------------------------------------------------
// Envío
// ---------------------------------------------------------------------------
async function enviar(texto) {
  // Validación de entrada primero (§10.2 «preventivo»): L-1/L-2/L-3 no dependen
  // de que la conexión esté configurada.
  if (texto.length > L1_MAX) return;
  const motivo = motivoRechazoEntrada(texto);
  if (motivo) { mostrarAvisoEntrada(motivo); return; }

  const apiUrl = (lsGet(LS.apiUrl) || "").trim();
  const apiKey = (lsGet(LS.apiKey) || "").trim();
  if (!apiUrl || !apiKey) {
    abrirAjustes();
    $("#in-api-url").focus();
    pintarError(null, "Configura la URL del API y la x-api-key en Ajustes antes de enviar.");
    return;
  }

  pintarUsuario(texto);
  $("#campo-mensaje").value = "";
  refrescarContador();
  ocultarAvisoEntrada();

  estado.enVuelo = true;
  actualizarBotonEnviar();
  mostrarIndicadorTool("El asistente está consultando…");

  try {
    const r = await fetch(apiUrl, {
      method: "POST",
      headers: { "content-type": "application/json", "x-api-key": apiKey },
      body: JSON.stringify({
        employee_id: "EMP_001",
        session_id: sesionId(),
        message: texto,
      }),
    });

    let cuerpo = {};
    try { cuerpo = await r.json(); } catch { cuerpo = {}; }

    if (r.status === 429) {
      const cod = cuerpo && cuerpo.error && cuerpo.error.code;
      const msg = (cuerpo && cuerpo.message ? String(cuerpo.message) : "");
      if (cod === "SESSION_BUDGET_EXCEEDED") {
        $("#dlg-budget").showModal();
      } else if (/too many requests|throttl/i.test(msg)) {
        // Throttle transitorio del API Gateway (10/s): NO es la cuota mensual.
        pintarNotaSistema("Vas muy rápido para el servicio. Espera un par de segundos y reinténtalo.");
      } else {
        $("#dlg-quota").showModal(); // cuota mensual G-1 agotada
      }
      return;
    }

    if (!r.ok || (cuerpo && cuerpo.error)) {
      const e = (cuerpo && cuerpo.error) || {};
      pintarError(e.code || String(r.status), textoErrorLegible(e.code, e.message));
      return;
    }

    recibirRespuesta(cuerpo);
  } catch (err) {
    pintarError(
      "RED",
      "No se pudo contactar con el servicio. Revisa en Ajustes que la URL termina en «/v1/chat» " +
      "y que la clave es correcta. Si acabas de abrir la página, recárgala con Ctrl/Cmd + Shift + R. " +
      "(Detalle: " + String(err && err.message || err) + ")"
    );
  } finally {
    estado.enVuelo = false;
    ocultarIndicadorTool();
    actualizarBotonEnviar();
  }
}

function recibirRespuesta(resp) {
  estado.turno = (resp.session && resp.session.turn) || estado.turno + 1;
  if (resp.session && resp.session.cost_usd_accumulated != null) {
    estado.costeAcumulado = resp.session.cost_usd_accumulated;
  }
  if (resp.session && resp.session.cost_usd_limit) {
    COSTE_SESION_MAX = resp.session.cost_usd_limit;
    COSTE_SESION_AVISO = +(COSTE_SESION_MAX * 0.8).toFixed(4);
  }
  pintarAgente(resp);
  refrescarTurnos();
  refrescarBandaTurnos();
  refrescarAvisoCoste();
  if (estado.costeAcumulado >= COSTE_SESION_MAX) $("#dlg-budget").showModal();
}

function textoErrorLegible(codigo, mensajeServidor) {
  const mapa = {
    INVALID_REQUEST: "La petición no es válida. Revisa el mensaje e inténtalo de nuevo.",
    INPUT_TOO_LARGE: "El mensaje es demasiado largo o denso. Acórtalo e inténtalo de nuevo.",
    SESSION_TURN_LIMIT: "Esta sesión alcanzó el máximo de turnos. Inicia una sesión nueva.",
    SESSION_FORBIDDEN: "Esta sesión pertenece a otra persona. Inicia una sesión nueva.",
    LLM_RATE_LIMITED: "El servicio está saturado ahora mismo. Espera unos segundos y reinténtalo.",
    LLM_UPSTREAM_ERROR: "El proveedor del modelo devolvió un error. Reinténtalo en un momento.",
  };
  if (mapa[codigo]) return mapa[codigo];
  // INTERNAL_ERROR y cualquier otro: el servidor manda un mensaje ya redactado
  // para el usuario (p. ej. "pulsa Nueva sesión"); si no lo hay, texto genérico.
  const s = (mensajeServidor || "").trim();
  if (s && !/^error (de la API|interno)/i.test(s)) return s;
  return "Se produjo un error interno. Si persiste, inicia una sesión nueva o avisa a la persona responsable del servicio.";
}

// ---------------------------------------------------------------------------
// Indicador de herramienta
// ---------------------------------------------------------------------------
function mostrarIndicadorTool(txt) {
  $("#indicador-tool-texto").textContent = txt;
  $("#indicador-tool").hidden = false;
}
function ocultarIndicadorTool() { $("#indicador-tool").hidden = true; }

function mostrarAvisoEntrada(txt) {
  const a = $("#aviso-entrada");
  a.textContent = txt;
  a.hidden = false;
}
function ocultarAvisoEntrada() { $("#aviso-entrada").hidden = true; }

// ---------------------------------------------------------------------------
// Guía de uso y estado vacío (§10.3) — fuente única: examples.json
// ---------------------------------------------------------------------------
let EJEMPLOS = null;

async function cargarEjemplos() {
  try {
    const r = await fetch("examples.json", { cache: "no-cache" });
    EJEMPLOS = await r.json();
  } catch {
    EJEMPLOS = { destacados: [], grupos: [], no_puedo: [], consejos: [] };
  }
  pintarDestacados();
  pintarTarjetasEjemplo();
  pintarGuia();
}

// Consultas con más impacto: tarjetas grandes con el "por qué". Se muestran en
// el estado vacío y en la guía. Un clic las coloca en el cuadro (nunca envía).
function pintarDestacados() {
  const lista = EJEMPLOS.destacados || [];
  const enVacio = $("#destacados-lista");
  if (enVacio) {
    enVacio.innerHTML = "";
    for (const d of lista) enVacio.appendChild(tarjetaDestacado(d, null));
  }
  const enGuia = $("#guia-destacados");
  if (enGuia) {
    enGuia.innerHTML = "";
    for (const d of lista) enGuia.appendChild(tarjetaDestacado(d, "#dlg-guia"));
  }
}

function tarjetaDestacado(d, dialogoACerrar) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "destacado-card";
  const q = document.createElement("span");
  q.className = "destacado-q";
  q.textContent = d.texto;
  const p = document.createElement("span");
  p.className = "destacado-por-que";
  p.textContent = d.por_que || "";
  b.append(q, p);
  b.addEventListener("click", () => {
    if (dialogoACerrar) $(dialogoACerrar).close();
    insertarEjemplo(d.texto);
  });
  return b;
}

// Datos de prueba (demo): identificadores reales del conjunto sembrado.
async function cargarDatosPrueba() {
  // Muestra viva del servicio (varía por sesión); si no hay conexión o falla,
  // cae al JSON estático empaquetado.
  let d = null;
  const apiUrl = (lsGet(LS.apiUrl) || "").trim();
  const apiKey = (lsGet(LS.apiKey) || "").trim();
  if (apiUrl && apiKey) {
    try {
      const r = await fetch(apiUrl, {
        method: "POST",
        headers: { "content-type": "application/json", "x-api-key": apiKey },
        body: JSON.stringify({ mode: "sample" }),
      });
      if (r.ok) {
        const j = await r.json();
        if ((j.vuelos || []).length || (j.reservas || []).length) d = j;
      }
    } catch { /* cae al estático */ }
  }
  if (!d) {
    try { d = await (await fetch("sample_data.json", { cache: "no-cache" })).json(); }
    catch { d = { vuelos: [], reservas: [] }; }
  }
  pintarTablaDatos($("#tabla-vuelos"), ["Código", "Ruta", "Estado", ""], d.vuelos || [],
    (v) => [v.codigo, v.ruta, v.estado], (v) => `¿El vuelo ${v.codigo} está demorado?`);
  pintarTablaDatos($("#tabla-reservas"), ["PNR", "Estado", "Tarifa", "Vuelo", ""], d.reservas || [],
    (r) => [r.pnr, r.estado, r.tarifa, r.vuelo], (r) => `Dame los datos de la reserva ${r.pnr}`);
}

function pintarTablaDatos(tabla, cabeceras, filas, celdas, consultaDe) {
  tabla.innerHTML = "";
  const thead = document.createElement("thead");
  const trh = document.createElement("tr");
  for (const c of cabeceras) {
    const th = document.createElement("th");
    th.textContent = c;
    trh.appendChild(th);
  }
  thead.appendChild(trh);
  tabla.appendChild(thead);
  const tb = document.createElement("tbody");
  for (const fila of filas) {
    const tr = document.createElement("tr");
    for (const val of celdas(fila)) {
      const td = document.createElement("td");
      td.textContent = val;
      tr.appendChild(td);
    }
    const tdBtn = document.createElement("td");
    const b = document.createElement("button");
    b.type = "button";
    b.className = "btn btn-plano btn-usar";
    b.textContent = "Usar";
    b.addEventListener("click", () => {
      $("#dlg-datos").close();
      insertarEjemplo(consultaDe(fila));
    });
    tdBtn.appendChild(b);
    tr.appendChild(tdBtn);
    tb.appendChild(tr);
  }
  tabla.appendChild(tb);
}

function marcadorEn(texto) {
  const m = texto.match(/\b(AN\d{3,4}|[A-Z0-9]{6})\b/);
  return m ? m[0] : null;
}

function insertarEjemplo(texto) {
  // Se inserta y se selecciona el marcador. NUNCA se envía (§10.3, U-12).
  const campo = $("#campo-mensaje");
  campo.value = texto;
  campo.focus();
  const marc = marcadorEn(texto);
  if (marc) {
    const i = texto.indexOf(marc);
    campo.setSelectionRange(i, i + marc.length);
  } else {
    campo.setSelectionRange(texto.length, texto.length);
  }
  refrescarContador();
}

function pintarTarjetasEjemplo() {
  const cont = $("#tarjetas-ejemplo");
  cont.innerHTML = "";
  for (const g of (EJEMPLOS.grupos || [])) {
    const div = document.createElement("div");
    div.className = "grupo-ejemplo";
    const h = document.createElement("h3");
    h.textContent = g.capacidad;
    div.appendChild(h);
    const ul = document.createElement("ul");
    for (const ej of g.ejemplos) {
      const li = document.createElement("li");
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn-ejemplo";
      b.textContent = ej;
      b.addEventListener("click", () => insertarEjemplo(ej));
      li.appendChild(b);
      ul.appendChild(li);
    }
    div.appendChild(ul);
    cont.appendChild(div);
  }
}

function pintarGuia() {
  const cg = $("#guia-grupos");
  cg.innerHTML = "";
  for (const g of (EJEMPLOS.grupos || [])) {
    const wrap = document.createElement("div");
    wrap.className = "guia-grupo";
    const h = document.createElement("h4");
    h.textContent = g.capacidad;
    const ul = document.createElement("ul");
    for (const ej of g.ejemplos) {
      const li = document.createElement("li");
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn-ejemplo";
      b.textContent = ej;
      b.addEventListener("click", () => {
        $("#dlg-guia").close();
        insertarEjemplo(ej);
      });
      li.appendChild(b);
      ul.appendChild(li);
    }
    wrap.append(h, ul);
    cg.appendChild(wrap);
  }
  rellenarLista($("#guia-no-puedo"), EJEMPLOS.no_puedo || []);
  rellenarLista($("#guia-consejos"), EJEMPLOS.consejos || []);
}

function rellenarLista(ul, items) {
  ul.innerHTML = "";
  for (const it of items) {
    const li = document.createElement("li");
    li.textContent = it;
    ul.appendChild(li);
  }
}

// ---------------------------------------------------------------------------
// Ajustes
// ---------------------------------------------------------------------------
function abrirAjustes() {
  $("#ajustes").hidden = false;
  $("#btn-ajustes").setAttribute("aria-expanded", "true");
  $("#ajustes-ok").hidden = true;
  $("#in-api-url").value = lsGet(LS.apiUrl) || "";
  $("#in-api-key").value = lsGet(LS.apiKey) || "";
  $("#ajustes").scrollIntoView({ block: "nearest" });
}
function cerrarAjustes() {
  $("#ajustes").hidden = true;
  $("#btn-ajustes").setAttribute("aria-expanded", "false");
}

function guardarAjustes() {
  const url = $("#in-api-url").value.trim();
  const key = $("#in-api-key").value.trim();
  lsSet(LS.apiUrl, url);
  lsSet(LS.apiKey, key);
  actualizarHintConexion();
  const ok = $("#ajustes-ok");
  ok.textContent = (url && key) ? "Guardado ✓" : "Guardado (falta la URL o la clave)";
  ok.hidden = false;
  if (url && key) {
    setTimeout(() => { cerrarAjustes(); $("#campo-mensaje").focus(); }, 700);
  }
}

function conexionConfigurada() {
  return !!(lsGet(LS.apiUrl) || "").trim() && !!(lsGet(LS.apiKey) || "").trim();
}

function actualizarHintConexion() {
  $("#hint-conexion").hidden = conexionConfigurada();
}

// ---------------------------------------------------------------------------
// Simulaciones de interfaz (U-5..U-8) — fuerzan estado en cliente, sin servidor.
// ---------------------------------------------------------------------------
function simular(tipo) {
  cerrarAjustes();
  if (tipo === "turno40") {
    estado.turno = L5_AVISO_TURNO;
    refrescarBandaTurnos();
    return;
  }
  if (tipo === "truncado") {
    recibirRespuesta({
      reply: "Aquí tienes la información solicitada sobre la reserva.",
      tools_used: [{ name: "obtener_datos_reserva", status: "ok", latency_ms: 12 }],
      tool_rounds: 1, finish_reason: "end_turn",
      usage: { input_tokens: 900, output_tokens: 40, cache_read_input_tokens: 3072, cost_usd: 0.004 },
      session: { turn: estado.turno + 1, turn_limit: L5_MAX_TURNS, cost_usd_accumulated: estado.costeAcumulado, cost_usd_limit: COSTE_SESION_MAX },
      context: { truncated: true, messages_dropped: 6 },
    });
  } else if (tipo === "max_rounds") {
    recibirRespuesta({
      reply: "",
      tools_used: [{ name: "buscar_politicas_rag", status: "NOT_FOUND", latency_ms: 210 }],
      tool_rounds: 3, finish_reason: "max_rounds",
      usage: { input_tokens: 700, output_tokens: 80, cache_read_input_tokens: 3072, cost_usd: 0.006 },
      session: { turn: estado.turno + 1, turn_limit: L5_MAX_TURNS, cost_usd_accumulated: estado.costeAcumulado, cost_usd_limit: COSTE_SESION_MAX },
      context: { truncated: false, messages_dropped: 0 },
    });
  } else if (tipo === "budget") {
    $("#dlg-budget").showModal();
  } else if (tipo === "quota") {
    $("#dlg-quota").showModal();
  }
}

// ---------------------------------------------------------------------------
// Arranque
// ---------------------------------------------------------------------------
function init() {
  pintarSesionId();
  refrescarContador();
  refrescarTurnos();
  actualizarHintConexion();
  cargarEjemplos();
  cargarDatosPrueba();

  // Las herramientas de QA (U-4..U-8) solo aparecen con ?pruebas=1.
  if (new URLSearchParams(location.search).get("pruebas") === "1") {
    $("#ajustes-sim").hidden = false;
  }

  $("#campo-mensaje").addEventListener("input", refrescarContador);
  $("#campo-mensaje").addEventListener("keydown", (e) => {
    // Enter envía; Shift+Enter hace salto de línea. `isComposing` respeta el
    // teclado de acentos / IME (no enviar a mitad de composición).
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      $("#form-mensaje").requestSubmit();
    }
  });

  $("#form-mensaje").addEventListener("submit", (e) => {
    e.preventDefault();
    const txt = $("#campo-mensaje").value.trim();
    if (!txt || estado.enVuelo) return;
    enviar(txt);
  });

  $("#btn-nueva-sesion").addEventListener("click", nuevaSesion);
  $("#btn-budget-nueva").addEventListener("click", () => { $("#dlg-budget").close(); nuevaSesion(); });

  $("#btn-ajustes").addEventListener("click", () => ($("#ajustes").hidden ? abrirAjustes() : cerrarAjustes()));
  $("#btn-cerrar-ajustes").addEventListener("click", cerrarAjustes);
  $("#btn-guardar-ajustes").addEventListener("click", guardarAjustes);
  $("#in-api-key").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); guardarAjustes(); } });
  $("#in-api-url").addEventListener("change", (e) => lsSet(LS.apiUrl, e.target.value.trim()));
  $("#in-api-key").addEventListener("change", (e) => lsSet(LS.apiKey, e.target.value.trim()));
  $$("[data-sim]").forEach((b) => b.addEventListener("click", () => simular(b.dataset.sim)));

  $("#btn-guia").addEventListener("click", () => $("#dlg-guia").showModal());
  $("#btn-datos").addEventListener("click", () => {
    $("#dlg-datos").showModal();
    cargarDatosPrueba();  // muestra fresca del Gold en cada apertura
  });
  $("#btn-contacto").addEventListener("click", () => $("#dlg-contacto").showModal());

  // Panel de uso responsable: abierto en la primera visita, descarte con memoria.
  if (!lsGet(LS.respVista)) {
    $("#dlg-responsable").showModal();
  }
  $("#dlg-responsable").addEventListener("close", () => lsSet(LS.respVista, "1"));
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
