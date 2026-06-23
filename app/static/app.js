/* WiFi Thermostat Manager — dashboard client.
   All paths are relative so the app works behind Home Assistant Ingress. */

const API = {
  async get(path) { return fetchJSON(path); },
  async send(path, method, body) {
    return fetchJSON(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  },
};

async function fetchJSON(path, opts) {
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

const state = { schemas: {}, commonFields: [], devices: {}, pending: {} };

/* ---------- Dial geometry ---------- */
const CX = 100, CY = 100, R = 80;
const START = 225, SWEEP = 270; // 270° arc with a gap at the bottom

function ptOnDial(angle) {
  const a = (angle * Math.PI) / 180;
  return { x: CX + R * Math.sin(a), y: CY - R * Math.cos(a) };
}
function arcPath(a0, a1) {
  const p0 = ptOnDial(a0), p1 = ptOnDial(a1);
  const large = (a1 - a0) % 360 > 180 ? 1 : 0;
  return `M ${p0.x.toFixed(2)} ${p0.y.toFixed(2)} A ${R} ${R} 0 ${large} 1 ${p1.x.toFixed(2)} ${p1.y.toFixed(2)}`;
}
function frac(value, min, max) {
  if (value == null || max <= min) return 0;
  return Math.max(0, Math.min(1, (value - min) / (max - min)));
}

/* ---------- Rendering ---------- */
const grid = document.getElementById("grid");
const emptyEl = document.getElementById("empty");
const cardTpl = document.getElementById("card-tpl");

function cardState(d) {
  const s = d.state;
  if (!s.available) return "unavailable";
  if (s.hvac_action === "heating") return "heating";
  if (s.hvac_mode === "off") return "off";
  return "idle";
}

function renderGrid(devices) {
  const ids = devices.map((d) => d.id);
  // Remove cards for deleted devices.
  grid.querySelectorAll(".card").forEach((c) => {
    if (!ids.includes(c.dataset.id)) c.remove();
  });
  devices.forEach((d) => {
    let card = grid.querySelector(`.card[data-id="${d.id}"]`);
    if (!card) card = createCard(d);
    updateCard(card, d);
  });
  emptyEl.classList.toggle("hidden", devices.length > 0);
}

function createCard(d) {
  const card = cardTpl.content.firstElementChild.cloneNode(true);
  card.dataset.id = d.id;
  card.querySelector(".dial-track").setAttribute("d", arcPath(START, START + SWEEP));

  card.querySelector(".card-menu").addEventListener("click", () => openModal(d.id));
  card.querySelector(".step-down").addEventListener("click", () => nudge(d.id, -1));
  card.querySelector(".step-up").addEventListener("click", () => nudge(d.id, +1));

  // Mode switch
  const modes = card.querySelector(".modes");
  d.supported_modes.forEach((m) => {
    const b = document.createElement("button");
    b.className = "mode-opt";
    b.textContent = m;
    b.dataset.mode = m;
    b.addEventListener("click", () => setMode(d.id, m));
    modes.appendChild(b);
  });

  grid.appendChild(card);
  return card;
}

function updateCard(card, d) {
  state.devices[d.id] = d;
  card.dataset.state = cardState(d);
  card.querySelector(".card-name").textContent = d.name;

  const s = d.state;
  const cur = s.current_temperature;
  const tgt = state.pending[d.id] ?? s.target_temperature;

  card.querySelector(".readout-num").textContent = cur == null ? "--" : fmt(cur);
  card.querySelector(".target-num").textContent = tgt == null ? "--" : fmt(tgt);

  // Dial fill up to the target, marker at the current temperature.
  const fill = card.querySelector(".dial-fill");
  const marker = card.querySelector(".dial-marker");
  if (tgt == null) {
    fill.setAttribute("d", "");
  } else {
    fill.setAttribute("d", arcPath(START, START + SWEEP * frac(tgt, d.min_temp, d.max_temp)));
  }
  if (cur == null) {
    marker.style.display = "none";
  } else {
    marker.style.display = "";
    const p = ptOnDial(START + SWEEP * frac(cur, d.min_temp, d.max_temp));
    marker.setAttribute("cx", p.x.toFixed(2));
    marker.setAttribute("cy", p.y.toFixed(2));
  }

  card.querySelectorAll(".mode-opt").forEach((b) => {
    b.setAttribute("aria-pressed", String(b.dataset.mode === s.hvac_mode));
  });
}

function fmt(n) {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

/* ---------- Commands ---------- */
const debounceTimers = {};

function nudge(id, direction) {
  const d = state.devices[id];
  if (!d) return;
  const step = d.temp_step || 0.5;
  const base = state.pending[id] ?? d.state.target_temperature ?? d.min_temp;
  let next = Math.round((base + direction * step) / step) * step;
  next = Math.max(d.min_temp, Math.min(d.max_temp, next));
  state.pending[id] = next;

  const card = grid.querySelector(`.card[data-id="${id}"]`);
  if (card) updateCard(card, d); // optimistic redraw

  clearTimeout(debounceTimers[id]);
  debounceTimers[id] = setTimeout(async () => {
    try {
      await API.send(`api/thermostats/${id}/temperature`, "POST", { temperature: next });
    } catch (err) {
      console.error(err);
    } finally {
      delete state.pending[id];
    }
  }, 600);
}

async function setMode(id, mode) {
  const card = grid.querySelector(`.card[data-id="${id}"]`);
  if (card) {
    card.querySelectorAll(".mode-opt").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
  }
  try {
    await API.send(`api/thermostats/${id}/mode`, "POST", { mode });
    await refresh();
  } catch (err) {
    console.error(err);
  }
}

/* ---------- Modal / forms ---------- */
const modal = document.getElementById("modal");
const typeSelect = document.getElementById("type-select");
const formEl = document.getElementById("device-form");
const formError = document.getElementById("form-error");
const modalTitle = document.getElementById("modal-title");
let editingId = null;

function buildField(f, value) {
  const wrap = document.createElement("div");
  wrap.className = "field";
  const label = document.createElement("label");
  label.textContent = f.label + (f.required ? " *" : "");
  label.htmlFor = `f_${f.key}`;
  wrap.appendChild(label);

  let input;
  if (f.type === "select") {
    input = document.createElement("select");
    f.options.forEach((opt) => {
      const o = document.createElement("option");
      o.value = opt; o.textContent = opt;
      input.appendChild(o);
    });
  } else {
    input = document.createElement("input");
    input.type = f.type === "number" ? "number" : "text";
    if (f.type === "number") input.step = "any";
    if (f.placeholder) input.placeholder = f.placeholder;
  }
  input.id = `f_${f.key}`;
  input.name = f.key;
  const v = value !== undefined ? value : f.default;
  if (v !== undefined && v !== null) input.value = v;
  wrap.appendChild(input);
  return wrap;
}

function renderForm(type, values = {}) {
  formEl.innerHTML = "";
  const schema = state.schemas[type];
  if (!schema) return;
  [...schema.fields, ...state.commonFields].forEach((f) => {
    formEl.appendChild(buildField(f, values[f.key]));
  });
}

function openModal(id = null) {
  editingId = id;
  formError.classList.add("hidden");
  modalTitle.textContent = id ? "Edit thermostat" : "Add thermostat";
  document.getElementById("delete-btn").classList.toggle("hidden", !id);

  if (id) {
    API.get(`api/thermostats/${id}/config`).then((data) => {
      const def = data.config || {};
      typeSelect.value = def.type;
      typeSelect.disabled = true;
      renderForm(def.type, def);
    });
  } else {
    typeSelect.disabled = false;
    typeSelect.value = typeSelect.options[0]?.value;
    renderForm(typeSelect.value);
  }
  modal.classList.remove("hidden");
}

function closeModal() {
  modal.classList.add("hidden");
  editingId = null;
}

function collectForm() {
  const out = { type: typeSelect.value };
  formEl.querySelectorAll("input, select").forEach((el) => {
    let val = el.value.trim();
    if (val === "") return;
    if (el.type === "number") val = Number(val);
    out[el.name] = val;
  });
  return out;
}

async function saveDevice() {
  const def = collectForm();
  formError.classList.add("hidden");
  try {
    if (editingId) {
      await API.send(`api/thermostats/${editingId}`, "PUT", def);
    } else {
      await API.send("api/thermostats", "POST", def);
    }
    closeModal();
    await refresh();
  } catch (err) {
    formError.textContent = err.message;
    formError.classList.remove("hidden");
  }
}

async function deleteDevice() {
  if (!editingId) return;
  if (!confirm("Remove this thermostat? It will also disappear from Home Assistant.")) return;
  try {
    await API.send(`api/thermostats/${editingId}`, "DELETE");
    closeModal();
    await refresh();
  } catch (err) {
    formError.textContent = err.message;
    formError.classList.remove("hidden");
  }
}

/* ---------- Status + polling ---------- */
const mqttPill = document.getElementById("mqtt-pill");
const mqttLabel = document.getElementById("mqtt-label");

function setMqttStatus(connected) {
  mqttPill.className = "pill " + (connected ? "pill-ok" : "pill-bad");
  mqttLabel.textContent = connected ? "Linked to Home Assistant" : "MQTT offline";
}

async function refresh() {
  try {
    const data = await API.get("api/thermostats");
    setMqttStatus(data.mqtt_connected);
    renderGrid(data.thermostats);
  } catch (err) {
    console.error(err);
  }
}

/* ---------- Wire up ---------- */
function initTypeSelect() {
  Object.entries(state.schemas).forEach(([type, schema]) => {
    const o = document.createElement("option");
    o.value = type; o.textContent = schema.label;
    typeSelect.appendChild(o);
  });
}

document.getElementById("add-btn").addEventListener("click", () => openModal());
document.querySelectorAll("[data-add]").forEach((b) => b.addEventListener("click", () => openModal()));
document.getElementById("save-btn").addEventListener("click", saveDevice);
document.getElementById("delete-btn").addEventListener("click", deleteDevice);
document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", closeModal));
modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });
typeSelect.addEventListener("change", () => renderForm(typeSelect.value));
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

(async function init() {
  try {
    const meta = await API.get("api/types");
    state.schemas = meta.schemas;
    state.commonFields = meta.common_fields;
    initTypeSelect();
  } catch (err) {
    console.error("Failed to load types", err);
  }
  await refresh();
  setInterval(refresh, 10000);
})();
