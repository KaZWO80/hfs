"use strict";

/*
 * Fragebogen Haushaltsführungsschaden – Formular-Logik.
 * Aktenzeichen-Verfahren laut plan/PLAN.md, Abschnitt 12.2:
 *   1. Anmeldung mit Aktenzeichen + Nachname
 *   2. Vorhandene Abgabe -> Formular mit den Angaben der neuesten Datei
 *   3. Absenden -> neue Datei (Korrektur), unverändert -> Hinweis
 */

const SITZUNG = "hfs_sitzung";           // sessionStorage: Aktenzeichen + Nachname
const ENTWURF = "hfs_entwurf_";          // localStorage + Aktenzeichen: nicht abgesendete Eingaben

const speicher = (s) => ({
  get(k) { try { return s.getItem(k); } catch { return null; } },
  set(k, v) { try { s.setItem(k, v); } catch { /* z. B. Privatmodus */ } },
  del(k) { try { s.removeItem(k); } catch { /* ignorieren */ } },
});
const ls = speicher(window.localStorage);
const ss = speicher(window.sessionStorage);

const form = document.getElementById("fragebogen");
const anmeldeForm = document.getElementById("anmeldung");
let def = null;
let maxStaffeln = 4;
let sitzung = null;     // { aktenzeichen, nachname }
let stand = null;       // Kennung der neuesten Abgabe ("2026-11-04_143000") oder null

const $ = (id) => document.getElementById(id);
const azSchluessel = (az) => ENTWURF + az.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");

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
  const geraete = $("geraete");
  for (const g of def.geraete) {
    geraete.append(el("label", { class: "wahl" }, [
      el("input", { type: "checkbox", name: "geraet", value: g.key }), " " + g.label,
    ]));
  }
  const vor = $("taetigkeiten-vor");
  const nach = $("taetigkeiten-nach");
  for (const t of def.taetigkeiten) {
    const zeileVor = el("div", { class: "zeile" }, [
      el("label", { class: "wahl" }, [el("input", { type: "checkbox", name: `vor.${t.key}.aktiv` }), " " + t.label]),
      el("label", { class: "inline stunden" }, [el("span", { text: "Std./Woche" }),
        el("input", { type: "number", min: "0", max: "168", step: "0.5", inputmode: "decimal", name: `vor.${t.key}.stunden` })]),
    ]);
    if (t.detail) {
      zeileVor.append(el("label", { class: "inline breit" }, [el("span", { text: t.detail }),
        el("input", { maxlength: "200", name: `vor.${t.key}.detail` })]));
    }
    vor.append(zeileVor);
    nach.append(el("div", { class: "zeile" }, [
      el("label", { class: "wahl" }, [el("input", { type: "checkbox", name: `nach.${t.key}.aktiv` }), " " + t.label]),
      el("label", { class: "inline datum" }, [el("span", { text: "wieder möglich ab" }),
        el("input", { type: "date", name: `nach.${t.key}.ab` })]),
    ]));
  }
}

function neueStaffel(werte = {}) {
  const box = $("staffeln");
  if (box.children.length >= maxStaffeln) return;
  const s = $("tpl-staffel").content.firstElementChild.cloneNode(true);
  for (const inp of s.querySelectorAll("[data-feld]")) inp.value = werte[inp.dataset.feld] ?? "";
  s.querySelector(".entfernen").addEventListener("click", () => { s.remove(); aktualisiere(); entwurfSpeichern(); });
  box.append(s);
  aktualisiere();
}

function aktualisiere() {
  $("staffel-plus").hidden = $("staffeln").children.length >= maxStaffeln;

  let summe = 0;
  for (const inp of form.querySelectorAll('input[name$=".stunden"]')) {
    const v = zahl(inp.value);
    if (v != null) summe += v;
    const haken = form.elements[inp.name.replace(".stunden", ".aktiv")];
    if (v != null && v > 0 && haken) haken.checked = true;
  }
  $("summe-stunden").textContent = summe.toLocaleString("de-DE");

  for (const block of form.querySelectorAll("[data-zeige-wenn]")) {
    const [name, wert] = block.dataset.zeigeWenn.split("=");
    const gewaehlt = form.querySelector(`input[name="${name}"]:checked`);
    block.hidden = !(gewaehlt && gewaehlt.value === wert);
  }
}

// ---------------------------------------- Aufteilung Ich / Andere = 100 % --
function ergaenzeAnteil(geaendert, anderes) {
  const v = zahl(geaendert.value);
  if (v == null) { anderes.value = ""; }
  else if (v >= 0 && v <= 100) { anderes.value = String(Math.round((100 - v) * 100) / 100); }
  pruefeAnteil(false);
}

function anteilOk() {
  const ich = zahl(form.elements.anteil_ich_prozent.value);
  const andere = zahl(form.elements.anteil_andere_prozent.value);
  if (ich == null && andere == null) return true;
  return ich != null && andere != null && Math.abs(ich + andere - 100) < 0.001;
}

function pruefeAnteil(anzeigen) {
  const ok = anteilOk();
  const box = $("anteil-fehler");
  if (ok) box.hidden = true; else if (anzeigen) box.hidden = false;
  return ok;
}

// ------------------------------------------------ Zeiträume (Staffeln) ----
function staffelnLesen() {
  return [...document.querySelectorAll("#staffeln .staffel")].map(s => {
    const w = {};
    for (const inp of s.querySelectorAll("[data-feld]")) w[inp.dataset.feld] = inp.value;
    return w;
  });
}

/** Markiert unvollständige oder fehlerhafte Zeiträume. Liefert Fehlertexte. */
function pruefeStaffeln(anzeigen) {
  const fehler = [];
  for (const s of document.querySelectorAll("#staffeln .staffel")) {
    const w = {};
    for (const inp of s.querySelectorAll("[data-feld]")) w[inp.dataset.feld] = inp.value.trim();
    const p = zahl(w.prozent);
    const leer = !w.von && !w.bis && w.prozent === "";
    let text = "";
    if (!leer && (!w.von || !w.bis || w.prozent === "")) text = "Bitte „von“, „bis“ und „Beeinträchtigung (%)“ vollständig ausfüllen.";
    else if (!leer && w.bis < w.von) text = "„bis“ liegt vor „von“.";
    else if (!leer && (p == null || p < 0 || p > 100)) text = "Die Beeinträchtigung muss zwischen 0 und 100 % liegen.";
    const box = s.querySelector(".feldfehler");
    if (!text) { box.hidden = true; s.classList.remove("fehlerhaft"); continue; }
    fehler.push(`Beeinträchtigung gestaffelt: ${text}`);
    if (anzeigen) { box.textContent = text; box.hidden = false; s.classList.add("fehlerhaft"); }
  }
  return fehler;
}

// ------------------------------- Tätigkeiten vor dem Unfall: Stunden ----
/** Angehakte Tätigkeiten ohne Stunden (> 0) markieren. Liefert Fehlertexte. */
function pruefeStunden(anzeigen) {
  const fehlend = [];
  for (const t of def.taetigkeiten) {
    const zeile = form.elements[`vor.${t.key}.aktiv`].closest(".zeile");
    const aktiv = form.elements[`vor.${t.key}.aktiv`].checked;
    const s = zahl(form.elements[`vor.${t.key}.stunden`].value);
    const fehlt = aktiv && !(s > 0);
    if (fehlt) fehlend.push(t.label);
    if (!fehlt) zeile.classList.remove("fehlerhaft");
    else if (anzeigen) zeile.classList.add("fehlerhaft");
  }
  return fehlend.length
    ? [`Tätigkeiten vor dem Unfall: Bitte Stunden pro Woche angeben für: ${fehlend.join(", ")}.`]
    : [];
}

// ---------------------------------------------- Formular <-> Antwort ------
function zahl(v) {
  if (v === "" || v == null) return null;
  const n = parseFloat(String(v).replace(",", "."));
  return isNaN(n) ? null : n;
}
const ganz = v => { const n = zahl(v); return n == null ? null : Math.round(n); };
const datum = v => v || null;
const jaNein = name => { const r = form.querySelector(`input[name="${name}"]:checked`); return r ? r.value === "ja" : null; };
const radio = name => form.querySelector(`input[name="${name}"]:checked`)?.value || "";
const text = name => (form.elements[name]?.value || "").trim();

const EINFACHE_FELDER = ["anrede", "vorname", "anteil_ich_prozent", "anteil_andere_prozent",
  "gehindert_von", "gehindert_bis", "gehindert_grund", "schmerzen", "personen", "kinder_alter",
  "wohnflaeche_qm", "raeume", "etagen", "besonderheiten", "garten_qm", "geraete_sonstiges",
  "bezahlte_hilfe_von", "bezahlte_hilfe_bis", "bezahlte_hilfe_taetigkeiten"];
const RADIO_TEXT = ["wohnform", "wohnverhaeltnis"];
const RADIO_JANEIN = ["garten", "haushaltshilfe_generell", "bezahlte_hilfe"];

function sammle() {
  const vor = {}, nach = {};
  for (const t of def.taetigkeiten) {
    const aktiv = form.elements[`vor.${t.key}.aktiv`].checked;
    const stunden = zahl(form.elements[`vor.${t.key}.stunden`].value);
    const detail = form.elements[`vor.${t.key}.detail`]?.value.trim() || "";
    if (aktiv || stunden) vor[t.key] = { aktiv: true, stunden_pro_woche: stunden, detail, };
    if (form.elements[`nach.${t.key}.aktiv`].checked) {
      nach[t.key] = { beeintraechtigt: true, wieder_moeglich_ab: datum(form.elements[`nach.${t.key}.ab`].value), hinweis: "" };
    }
  }
  const hilfe = jaNein("bezahlte_hilfe");
  return {
    aktenzeichen: sitzung.aktenzeichen,
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
  };
}

/** Trägt Antworten ins Formular ein; ein leeres Objekt leert das Formular. */
function befuelle(a) {
  for (const n of EINFACHE_FELDER) if (form.elements[n]) form.elements[n].value = a[n] ?? "";
  for (const n of RADIO_TEXT) for (const r of form.querySelectorAll(`input[name="${n}"]`)) r.checked = r.value === a[n];
  for (const n of RADIO_JANEIN) {
    for (const r of form.querySelectorAll(`input[name="${n}"]`)) r.checked = a[n] != null && r.value === (a[n] ? "ja" : "nein");
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
  $("staffeln").replaceChildren();
  const st = a.staffeln || [];
  if (st.length) st.forEach(neueStaffel); else neueStaffel();
  form.elements.einwilligung.checked = false; // bei jeder Abgabe neu bestätigen
  $("anteil-fehler").hidden = true;
  aktualisiere();
}

// ------------------------------------------------- Entwurf (Browser) ------
function entwurfSpeichern() {
  if (!sitzung || form.hidden) return;
  const d = sammle();
  d.staffeln = staffelnLesen(); // auch unvollständige Zeiträume merken
  ls.set(azSchluessel(sitzung.aktenzeichen), JSON.stringify({ basis: stand, daten: d }));
}

function entwurfLesen() {
  try {
    const e = JSON.parse(ls.get(azSchluessel(sitzung.aktenzeichen)) || "null");
    return e && e.basis === stand ? e.daten : null; // nur passend zur neuesten Abgabe
  } catch { return null; }
}

// ------------------------------------------------------ Anzeige -----------
function zeige(id, werte = {}) {
  const box = $(id);
  for (const f of box.querySelectorAll("[data-feld]")) f.textContent = werte[f.dataset.feld] || "";
  box.hidden = false;
}

function ansicht(name) {
  $("laden").hidden = name !== "laden";
  anmeldeForm.hidden = name !== "anmeldung";
  form.hidden = name !== "formular";
  for (const id of ["hinweis-danke", "hinweis-korrektur"]) $(id).hidden = true;
  window.scrollTo(0, 0);
}

function fehlerText(info, status) {
  if (Array.isArray(info.detail)) return info.detail.map(x => `${(x.loc || []).slice(1).join(" › ")}: ${x.msg}`);
  return [info.detail || `Fehler ${status}`];
}

function zeigeFehler(boxId, liste) {
  const box = $(boxId);
  box.replaceChildren(...liste.map(t => el("p", { text: t })));
  box.hidden = liste.length === 0;
  if (liste.length) box.scrollIntoView({ behavior: "smooth", block: "center" });
}

// ----------------------------------------------------------- Anmelden -----
async function anmelden(az, nachname, still = false) {
  const knopf = $("anmelden");
  knopf.disabled = true;
  try {
    const r = await fetch("api/anmelden", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ aktenzeichen: az, nachname }),
    });
    const info = await r.json().catch(() => ({}));
    if (!r.ok) {
      ss.del(SITZUNG);
      ansicht("anmeldung");
      if (!still || r.status !== 403) {
        zeigeFehler("anmeldung-fehler", r.status === 422
          ? ["Bitte prüfen Sie das Aktenzeichen (Buchstaben, Ziffern, „/“, „-“ oder „.“)."]
          : fehlerText(info, r.status));
      }
      return null;
    }
    sitzung = { aktenzeichen: az, nachname: info.vorhanden ? info.antwort.nachname : nachname };
    ss.set(SITZUNG, JSON.stringify(sitzung));
    stand = info.vorhanden ? info.stand : null;
    zeigeFehler("anmeldung-fehler", []);
    zeigeFormular(info);
    return info;
  } catch {
    zeigeFehler("anmeldung-fehler", ["Keine Verbindung zum Server. Bitte prüfen Sie Ihre Internetverbindung."]);
    ansicht("anmeldung");
    return null;
  } finally {
    knopf.disabled = false;
  }
}

function zeigeFormular(info) {
  ansicht("formular");
  befuelle(entwurfLesen() || (info.vorhanden ? info.antwort : {}));
  form.elements.nachname.value = sitzung.nachname;
  $("anzeige-aktenzeichen").textContent = sitzung.aktenzeichen;
  if (info.vorhanden) zeige("hinweis-korrektur", info);
  zeigeFehler("fehler", []);
  pruefeStaffeln(false);
}

function abmelden() {
  if (sitzung) ls.del(azSchluessel(sitzung.aktenzeichen));
  ss.del(SITZUNG);
  sitzung = null;
  stand = null;
  anmeldeForm.reset();
  zeigeFehler("anmeldung-fehler", []);
  ansicht("anmeldung");
}

// ----------------------------------------------------------- Absenden -----
function pruefe(d) {
  const f = [];
  if (!d.vorname) f.push("Bitte geben Sie Ihren Vornamen an.");
  if (!pruefeAnteil(true)) f.push("Aufteilung der Haushaltsführung: „Ich“ und „Andere“ müssen zusammen 100 % ergeben.");
  if (d.gehindert_von && d.gehindert_bis && d.gehindert_bis < d.gehindert_von) f.push("Zeitraum der Verhinderung: „bis“ liegt vor „von“.");
  f.push(...pruefeStaffeln(true));
  f.push(...pruefeStunden(true));
  if (!d.einwilligung) f.push("Bitte bestätigen Sie die Einwilligung zur Datenverarbeitung.");
  return f;
}

async function absenden(ev) {
  ev.preventDefault();
  const d = sammle();
  const fehler = pruefe(d);
  zeigeFehler("fehler", fehler);
  if (fehler.length) return;
  if (!confirm("Fragebogen jetzt an die Kanzlei absenden?")) return;

  const knopf = $("absenden");
  knopf.disabled = true;
  knopf.textContent = "Wird übermittelt …";
  try {
    const r = await fetch("api/antwort", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(d),
    });
    const info = await r.json().catch(() => ({}));
    if (r.status === 201) {
      ls.del(azSchluessel(sitzung.aktenzeichen));
      stand = info.stand;
      ansicht("danke");
      zeige("hinweis-danke", info);
      return;
    }
    if (r.status === 403 || r.status === 429) { abmelden(); zeigeFehler("anmeldung-fehler", fehlerText(info, r.status)); return; }
    zeigeFehler("fehler", r.status === 409 ? fehlerText(info, r.status)
      : ["Die Übermittlung wurde abgelehnt:", ...fehlerText(info, r.status)]);
  } catch {
    zeigeFehler("fehler", ["Keine Verbindung zum Server. Ihre Eingaben bleiben auf diesem Gerät gespeichert – bitte versuchen Sie es später erneut."]);
  } finally {
    knopf.disabled = false;
    knopf.textContent = "Fragebogen absenden";
  }
}

// -------------------------------------------------------------- Start -----
async function start() {
  try {
    def = await fetch("api/fragebogen").then(r => r.json());
  } catch {
    $("laden").textContent = "Der Fragebogen konnte nicht geladen werden. Bitte prüfen Sie Ihre Internetverbindung und laden Sie die Seite neu.";
    return;
  }
  maxStaffeln = def.max_staffeln;
  baueFormular();

  anmeldeForm.addEventListener("submit", ev => {
    ev.preventDefault();
    const az = anmeldeForm.elements.aktenzeichen.value.trim();
    const name = anmeldeForm.elements.nachname.value.trim();
    if (!az || !name) { zeigeFehler("anmeldung-fehler", ["Bitte Aktenzeichen und Nachnamen eingeben."]); return; }
    anmelden(az, name);
  });
  document.addEventListener("click", ev => {
    const aktion = ev.target.closest("[data-aktion]")?.dataset.aktion;
    if (aktion === "abmelden") abmelden();
    if (aktion === "bearbeiten" && sitzung) anmelden(sitzung.aktenzeichen, sitzung.nachname);
  });
  form.elements.anteil_ich_prozent.addEventListener("input", e => ergaenzeAnteil(e.target, form.elements.anteil_andere_prozent));
  form.elements.anteil_andere_prozent.addEventListener("input", e => ergaenzeAnteil(e.target, form.elements.anteil_ich_prozent));
  $("staffel-plus").addEventListener("click", () => neueStaffel());
  $("staffeln").addEventListener("input", () => pruefeStaffeln(false));
  $("taetigkeiten-vor").addEventListener("input", () => pruefeStunden(false));
  $("taetigkeiten-vor").addEventListener("change", () => pruefeStunden(false));
  form.addEventListener("input", () => { aktualisiere(); entwurfSpeichern(); });
  form.addEventListener("change", () => { aktualisiere(); entwurfSpeichern(); });
  form.addEventListener("submit", absenden);

  let gespeichert = null;
  try { gespeichert = JSON.parse(ss.get(SITZUNG) || "null"); } catch { /* ignorieren */ }
  if (gespeichert) await anmelden(gespeichert.aktenzeichen, gespeichert.nachname, true);
  else ansicht("anmeldung");
}

start();
