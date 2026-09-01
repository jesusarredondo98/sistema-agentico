/**
 * Capturas reales de la UI desplegada de AeroNova para el GIF de la presentacion.
 *
 * Abre la web en CloudFront con un Chrome real (playwright-core, sin descargar
 * navegador), inyecta las credenciales en localStorage y lanza 5 consultas,
 * guardando PNGs numerados en build/ppt-context/shots/.
 *
 *   AERONOVA_UI_URL=... AERONOVA_API_URL=... AERONOVA_API_KEY=... \
 *   node scripts/demo_shots.js
 *
 * Luego `python scripts/demo_gif.py` arma docs/ppt/aeronova_demo.gif.
 */
const fs = require("fs");
const path = require("path");
// playwright-core se instala en build/ppt-context/node_modules (fuera de git).
const PW = path.resolve(__dirname, "..", "build", "ppt-context", "node_modules", "playwright-core");
const { chromium } = require(fs.existsSync(PW) ? PW : "playwright-core");

const CHROME =
  process.env.CHROME_BIN ||
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const UI_URL = process.env.AERONOVA_UI_URL || "https://d1v908g2u3hf9q.cloudfront.net";
const API_URL = process.env.AERONOVA_API_URL;
const API_KEY = process.env.AERONOVA_API_KEY;
const OUT = path.resolve(__dirname, "..", "build", "ppt-context", "shots");

const CONSULTAS = [
  "¿El vuelo AN1008 está demorado?",
  "Dame los datos de la reserva GVJIYN",
  "¿Puedo llevar un gato en cabina y qué peso máximo tiene?",
  "Dame el radar operativo de BCN",
  "¿Cuántos vuelos nacionales e internacionales salen de MEX?",
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  if (!API_URL || !API_KEY) {
    console.error("faltan AERONOVA_API_URL / AERONOVA_API_KEY");
    process.exit(1);
  }
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(OUT, { recursive: true });

  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const ctx = await browser.newContext({
    viewport: { width: 1180, height: 820 },
    deviceScaleFactor: 2,
  });
  // Credenciales + panel de uso responsable ya visto: la UI arranca lista.
  // Sesión nueva en cada corrida (evita arrastre de contexto entre demos).
  const SESSION = `demo-ui-${Date.now()}`;
  await ctx.addInitScript(
    ([u, k, s]) => {
      try {
        localStorage.setItem("aeronova.apiUrl", u);
        localStorage.setItem("aeronova.apiKey", k);
        localStorage.setItem("aeronova.sessionId", s);
        localStorage.setItem("aeronova.responsablePanelVisto", "1");
      } catch (e) {}
    },
    [API_URL, API_KEY, SESSION]
  );

  const page = await ctx.newPage();
  await page.goto(UI_URL, { waitUntil: "networkidle" });
  await sleep(800);
  // Cierra cualquier dialogo abierto (ajustes / guia / uso responsable).
  for (const sel of ["#dlg-responsable", "#dlg-ajustes", "#dlg-guia"]) {
    const d = page.locator(`${sel}[open], ${sel}.abierto`);
    if (await d.count()) {
      await page.keyboard.press("Escape").catch(() => {});
      await sleep(150);
    }
  }
  await page.evaluate(() => document.querySelectorAll("dialog[open]").forEach((d) => d.close()));
  await sleep(300);

  let n = 0;
  const shot = async (tag) => {
    const f = path.join(OUT, `${String(n).padStart(3, "0")}_${tag}.png`);
    await page.screenshot({ path: f });
    n++;
  };

  await shot("inicio");

  for (let i = 0; i < CONSULTAS.length; i++) {
    const q = CONSULTAS[i];
    const campo = page.locator("#campo-mensaje");
    await campo.click();
    await campo.fill("");
    // Tecleo con efecto maquina de escribir + capturas intermedias.
    for (let c = 0; c < q.length; c += Math.max(2, Math.ceil(q.length / 8))) {
      await campo.fill(q.slice(0, c + 1));
      if (c % Math.max(4, Math.ceil(q.length / 4)) === 0) await shot(`q${i + 1}_typing`);
      await sleep(40);
    }
    await campo.fill(q);
    await shot(`q${i + 1}_typed`);

    await page.locator("#form-mensaje").evaluate((f) => f.requestSubmit());
    // Indicador de herramienta en curso.
    await page
      .waitForSelector("#indicador-tool:not([hidden])", { timeout: 4000 })
      .catch(() => {});
    await shot(`q${i + 1}_working`);

    // Respuesta lista: hay una burbuja de agente nueva con texto y el
    // indicador "consultando" ya se ocultó. (El botón Enviar sigue disabled
    // porque el textarea quedó vacío, no sirve como señal.)
    await page.waitForFunction(
      (want) => {
        const bs = document.querySelectorAll("#hilo .msg-agente");
        if (bs.length < want) return false;
        const txt = (
          bs[bs.length - 1].querySelector(".msg-burbuja")?.textContent || ""
        ).trim();
        const ind = document.querySelector("#indicador-tool");
        return txt.length > 20 && (!ind || ind.hidden);
      },
      i + 1,
      { timeout: 60000 }
    );
    await sleep(600);
    await page.evaluate(() =>
      document.querySelector("#conversacion")?.scrollTo(0, 1e6)
    );
    await sleep(400);
    await shot(`q${i + 1}_reply`);
    await sleep(500);
    await shot(`q${i + 1}_reply2`);
  }

  await browser.close();
  console.log(`ok -> ${OUT}  (${n} capturas)`);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
