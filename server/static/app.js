"use strict";

/*
 * Fragebogen Haushaltsführungsschaden – Formular-Logik.
 * Fälle laut plan/PLAN.md, Abschnitt 6:
 *   A  leerer Fragebogen
 *   B  heute abgegeben -> Antworten nur lesen
 *   C  früher abgegeben -> vorausgefüllt, Absenden = Korrektur
 */

const SPEICHER_ID = "hfs_installations_id";
const SPEICHER_ENTWURF = "hfs_entwurf";

const ls = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* z. B. Privatmodus */ } },
  del(k) { try { localStorage.removeItem(k); } catch { /* ignorieren */ } },
};

function installationsId() {
  let id = ls.get(SPEICHER_ID);
  if (!id) {
    // crypto.randomUUID gibt es nur über HTTPS; im Heimnetz (HTTP) daher Fallback.
    id = crypto.randomUUID ? crypto.randomUUID()
      : Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, "0")).join("");
    ls.set(SPEICHER_ID, id);
  }
  return id;
}

const form = document.getElementById("fragebogen");
let def = null;
let maxStaffeln = 4;

// ------------------------------------------------------------ Aufbau ------
function el(tag, attrs = {}, kinder = []) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "text") e.textContent = v; else e.setAttribute(k, v);
  }
  for (const k of kinder) e.append(k);
  return e;
}

function baueFormular() {
  const geraete = document.getElementById("geraete");
  for (const g of def.geraete) {
    geraete.append(el("label", { class: "wahl" }, [
      el("input", { type: "checkbox", name: "geraet", value: g.key }), " " + g.label,
    ]));
  }

  const vor = document.getElementById("taetigkeiten-vor");
  const nach = document.getElementById("taetigkeiten-nach");
  for (const t of def.taetigkeiten) {
    const zeileVor = el("div", { class: "zeile" }, [
      el("label", { class: "wahl" }, [el("input", { type: "checkbox", name: `vor.${t.key}.aktiv` }), " " + t.label]),
      el("label", { class: "inline" }, ["Std./Woche",
        el("input", { type: "number", min: "0", max: "168", step: "0.5", inputmode: "decimal", name: `vor.${t.key}.stunden` })]),
    ]);
    if (t.detail) {
      zeileVor.append(el("label", { class: "inline breit" }, [t.detail,
        el("input", { maxlength: "200", name: `vor.${t.key}.detail` })]));
    }
    vor.append(zeileVor);

    nach.append(el("div", { class: "zeile" }, [
      el("label", { class: "wahl" }, [el("input", { type: "checkbox", name: `nach.${t.key}.aktiv` }), " " + t.label]),
      el("label", { class: "inline" }, ["wieder möglich ab",
        el("input", { type: "date", name: `nach.${t.key}.ab` })]),
    ]));
  }
}

function neueStaffel(werte = {}) {
  const box = document.getElementById("staffeln");
  if (box.children.length >= maxStaffeln) return;
  const s = document.getElementById("tpl-staffel").content.firstElementChild.cloneNode(true);
  for (const inp of s.querySelectorAll("[data-feld]")) inp.value = werte[inp.dataset.feld] ?? "";
  s.querySelector(".entfernen").addEventListener("click", () => { s.remove(); aktualisiere(); entwurfSpeichern(); });
  box.append(s);
  aktualisiere();
}

function aktualisiere() {
  const box = document.getElementById("staffeln");
  document.getElementById("staffel-plus").hidden = form.dataset.nurLesen === "1" || box.children.length >= maxStaffeln;

  let summe = 0;
  for (const inp of form.querySelectorAll('input[name$=".stunden"]')) {
    const v = parseFloat(inp.value.replace(",", "."));
    if (!isNaN(v)) summe += v;
    const haken = form.elements[inp.name.replace(".stunden", ".aktiv")];
    if (!isNaN(v) && v > 0 && haken) haken.checked = true;
  }
  document.getElementById("summe-stunden").textContent = summe.toLocaleString("de-DE");

  for (const block of form.querySelectorAll("[data-zeige-wenn]")) {
    const [name, wert] = block.dataset.zeigeWenn.split("=");
    const gewaehlt = form.querySelector(`input[name="${name}"]:checked`);
    block.hidden = !(gewaehlt && gewaehlt.value === wert);
  }
}

// ---------------------------------------------- Formular <-> Antwort ------
const zahl = v => { if (v === "" || v == null) return null; const n = parseFloat(String(v).replace(",", ".")); return isNaN(n) ? null : n; };
const ganz = v => { const n = zahl(v); return n == null ? null : Math.round(n); };
const datum = v => v || null;
const jaNein = name => { const r = form.querySelector(`input[name="${name}"]:checked`); return r ? r.value === "ja" : null; };
const radio = name => form.querySelector(`input[name="${name}"]:checked`)?.value || "";
const text = name => (form.elements[name]?.value || "").trim();

const EINFACHE_FELDER = ["anrede", "vorname", "nachname", "anteil_ich_prozent", "anteil_andere_prozent",
  "gehindert_von", "gehindert_bis", "gehindert_grund", "schmerzen", "personen", "kinder_alter",
  "wohnflaeche_qm", "raeume", "etagen", "besonderheiten", "garten_qm", "geraete_sonstiges",
  "bezahlte_hilfe_von", "bezahlte_hilfe_bis", "bezahlte_hilfe_taetigkeiten"];
const RADIO_TEXT = ["wohnform", "wohnverhaeltnis"];
const RADIO_JANEIN = ["garten", "haushaltshilfe_generell", "bezahlte_hilfe"];

function staffelnLesen() {
  return [...document.querySelectorAll("#staffeln .staffel")].map(s => {
    const w = {};
    for (const inp of s.querySelectorAll("[data-feld]")) w[inp.dataset.feld] = inp.value;
    return w;
  });
}

function sammle() {
  const vor = {}, nach = {};
  for (const t of def.taetigkeiten) {
    const aktiv = form.elements[`vor.${t.key}.aktiv`].checked;
    const stunden = zahl(form.elements[`vor.${t.key}.stunden`].value);
    const detail = form.elements[`vor.${t.key}.detail`]?.value.trim() || "";
    if (aktiv || stunden) vor[t.key] = { aktiv: true, stunden_pro_woche: stunden, detail };
    if (form.elements[`nach.${t.key}.aktiv`].checked) {
      nach[t.key] = { beeintraechtigt: true, wieder_moeglich_ab: datum(form.elements[`nach.${t.key}.ab`].value) };
    }
  }
  const hilfe = jaNein("bezahlte_hilfe");
  return {
    anrede: form.elements.anrede.value,
    vorname: text("vorname"),
    nachname: text("nachname"),
    anteil_ich_prozent: zahl(form.elements.anteil_ich_prozent.value),
    anteil_andere_prozent: zahl(form.elements.anteil_andere_prozent.value),
    gehindert_von: datum(form.elements.gehindert_von.value),
    gehindert_bis: datum(form.elements.gehindert_bis.value),
    gehindert_grund: text("gehindert_grund"),
    staffeln: staffelnLesen().filter(w => w.von && w.bis && w.prozent !== "")
      .map(w => ({ von: w.von, bis: w.bis, prozent: zahl(w.prozent) })),
    schmerzen: text("schmerzen"),
    personen: ganz(form.elements.personen.value),
    kinder_alter: text("kinder_alter"),
    wohnform: radio("wohnform"),
    wohnverhaeltnis: radio("wohnverhaeltnis"),
    wohnflaeche_qm: zahl(form.elements.wohnflaeche_qm.value),
    raeume: ganz(form.elements.raeume.value),
    etagen: ganz(form.elements.etagen.value),
    besonderheiten: text("besonderheiten"),
    garten: jaNein("garten"),
    garten_qm: jaNein("garten") ? zahl(form.elements.garten_qm.value) : null,
    geraete: [...form.querySelectorAll('input[name="geraet"]:checked')].map(e => e.value),
    geraete_sonstiges: text("geraete_sonstiges"),
    haushaltshilfe_generell: jaNein("haushaltshilfe_generell"),
    bezahlte_hilfe: hilfe,
    bezahlte_hilfe_von: hilfe ? datum(form.elements.bezahlte_hilfe_von.value) : null,
    bezahlte_hilfe_bis: hilfe ? datum(form.elements.bezahlte_hilfe_bis.value) : null,
    bezahlte_hilfe_taetigkeiten: hilfe ? text("bezahlte_hilfe_taetigkeiten") : "",
    taetigkeiten_vor: vor,
    taetigkeiten_nach: nach,
    einwilligung: form.elements.einwilligung.checked,
    installations_id: installationsId(),
  };
}

/** Trägt eine gespeicherte Antwort (Format wie von sammle()) ins Formular ein. */
function befuelle(a) {
  for (const n of EINFACHE_FELDER) if (form.elements[n]) form.elements[n].value = a[n] ?? "";
  for (const n of RADIO_TEXT) for (const r of form.querySelectorAll(`input[name="${n}"]`)) r.checked = r.value === a[n];
  for (const n of RADIO_JANEIN) {
    for (const r of form.querySelectorAll(`input[name="${n}"]`)) {
      r.checked = a[n] != null && r.value === (a[n] ? "ja" : "nein");
    }
  }
  for (const c of form.querySelectorAll('input[name="geraet"]')) c.checked = (a.geraete || []).includes(c.value);
  for (const t of def.taetigkeiten) {
    const v = (a.taetigkeiten_vor || {})[t.key];
    form.elements[`vor.${t.key}.aktiv`].checked = !!v;
    form.elements[`vor.${t.key}.stunden`].value = v?.stunden_pro_woche ?? "";
    if (form.elements[`vor.${t.key}.detail`]) form.elements[`vor.${t.key}.detail`].value = v?.detail || "";
    const n = (a.taetigkeiten_nach || {})[t.key];
    form.elements[`nach.${t.key}.aktiv`].checked = !!n?.beeintraechtigt;
    form.elements[`nach.${t.key}.ab`].value = n?.wieder_moeglich_ab || "";
  }
  document.getElementById("staffeln").replaceChildren();
  const st = a.staffeln || [];
  if (st.length) st.forEach(neueStaffel); else neueStaffel();
  form.elements.einwilligung.checked = false; // bei Korrektur erneut bestätigen
  aktualisiere();
}

// ------------------------------------------------- Entwurf (Browser) ------
function entwurfSpeichern() {
  if (form.dataset.nurLesen === "1") return;
  const d = sammle();
  d._staffeln_roh = staffelnLesen();
  ls.set(SPEICHER_ENTWURF, JSON.stringify(d));
}

function entwurfLesen() {
  try {
    const d = JSON.parse(ls.get(SPEICHER_ENTWURF) || "null");
    if (d && d._staffeln_roh) d.staffeln = d._staffeln_roh;
    return d;
  } catch { return null; }
}

// ------------------------------------------------------ Anzeige-Fälle -----
function zeige(id, status = {}) {
  const box = document.getElementById(id);
  for (const f of box.querySelectorAll("[data-feld]")) f.textContent = status[f.dataset.feld] || "";
  box.hidden = false;
}

function nurLesen() {
  form.dataset.nurLesen = "1";
  form.classList.add("nur-lesen");
  for (const e of form.elements) e.disabled = true;
  document.getElementById("abschnitt-absenden").hidden = true;
  for (const b of form.querySelectorAll(".entfernen")) b.hidden = true;
  aktualisiere();
}

// ----------------------------------------------------------- Absenden -----
function pruefe(d) {
  const f = [];
  if (!d.vorname) f.push("Bitte geben Sie Ihren Vornamen an.");
  if (!d.nachname) f.push("Bitte geben Sie Ihren Nachnamen an.");
  if (d.gehindert_von && d.gehindert_bis && d.gehindert_bis < d.gehindert_von) f.push("Zeitraum der Verhinderung: „bis“ liegt vor „von“.");
  for (const s of d.staffeln) {
    if (s.bis < s.von) f.push("Beeinträchtigung: Bei einem Zeitraum liegt „bis“ vor „von“.");
    if (s.prozent == null || s.prozent < 0 || s.prozent > 100) f.push("Beeinträchtigung: Prozent muss zwischen 0 und 100 liegen.");
  }
  if (!d.einwilligung) f.push("Bitte bestätigen Sie die Einwilligung zur Datenverarbeitung.");
  return f;
}

function zeigeFehler(liste) {
  const box = document.getElementById("fehler");
  box.replaceChildren(...liste.map(t => el("p", { text: t })));
  box.hidden = liste.length === 0;
  if (liste.length) box.scrollIntoView({ behavior: "smooth", block: "center" });
}

async function absenden(ev) {
  ev.preventDefault();
  const d = sammle();
  const fehler = pruefe(d);
  zeigeFehler(fehler);
  if (fehler.length) return;
  if (!confirm("Fragebogen jetzt verbindlich absenden? Änderungen sind erst ab morgen möglich.")) return;

  const knopf = document.getElementById("absenden");
  knopf.disabled = true;
  knopf.textContent = "Wird übermittelt …";
  try {
    const r = await fetch("api/antwort", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(d),
    });
    if (r.status === 201 || r.status === 409) {
      ls.del(SPEICHER_ENTWURF);
      for (const id of ["hinweis-korrektur", "hinweis-heute"]) document.getElementById(id).hidden = true;
      if (r.status === 201) zeige("hinweis-danke");
      else zeige("hinweis-heute", (await fetch(`api/status/${encodeURIComponent(installationsId())}`).then(x => x.json())));
      nurLesen();
      window.scrollTo(0, 0);
      return;
    }
    const info = await r.json().catch(() => ({}));
    const details = Array.isArray(info.detail)
      ? info.detail.map(x => `${(x.loc || []).slice(1).join(" › ")}: ${x.msg}`)
      : [info.detail || `Fehler ${r.status}`];
    zeigeFehler(["Die Übermittlung wurde abgelehnt:", ...details]);
  } catch {
    zeigeFehler(["Keine Verbindung zum Server. Ihre Eingaben bleiben auf diesem Gerät gespeichert – bitte versuchen Sie es später erneut."]);
  } finally {
    knopf.disabled = false;
    knopf.textContent = "Fragebogen verbindlich absenden";
  }
}

// -------------------------------------------------------------- Start -----
async function start() {
  let status = { fall: "A" };
  try {
    [def, status] = await Promise.all([
      fetch("api/fragebogen").then(r => r.json()),
      fetch(`api/status/${encodeURIComponent(installationsId())}`).then(r => r.json()),
    ]);
  } catch {
    document.getElementById("laden").textContent =
      "Der Fragebogen konnte nicht geladen werden. Bitte prüfen Sie Ihre Internetverbindung und laden Sie die Seite neu.";
    return;
  }
  maxStaffeln = def.max_staffeln;
  baueFormular();

  const entwurf = entwurfLesen();
  if (status.fall === "B") {
    befuelle(status.antwort);
    zeige("hinweis-heute", status);
    nurLesen();
  } else if (status.fall === "C") {
    befuelle(entwurf || status.antwort);
    zeige("hinweis-korrektur", status);
  } else {
    if (entwurf) befuelle(entwurf); else neueStaffel();
  }

  document.getElementById("laden").hidden = true;
  form.hidden = false;
  aktualisiere();

  document.getElementById("staffel-plus").addEventListener("click", () => neueStaffel());
  form.addEventListener("input", () => { aktualisiere(); entwurfSpeichern(); });
  form.addEventListener("change", () => { aktualisiere(); entwurfSpeichern(); });
  form.addEventListener("submit", absenden);
}

start();
