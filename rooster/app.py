#!/usr/bin/env python3
"""
rooster - kleine webservice om de schakeltijden per stekker te bewerken.

Toont een pagina met per stekker drie velden (aanlooptijd, harde uit-tijd,
ochtendstart) en slaat wijzigingen op in schema.json. stekker.py leest dat
bestand elke minuut opnieuw, dus wijzigingen werken binnen een minuut.

De service draait op poort 8090 en staat alleen achter de nginx-proxy van
mijnhuis.lab023.nl (met wachtwoord). Draait zelf dus niet los op internet.
"""

import json
import re
from pathlib import Path

from flask import Flask, request, jsonify, Response

SCHEMA = Path("/app/schema.json")
TIJD = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")  # HH:MM, 00:00 t/m 23:59

app = Flask(__name__)


def lees_schema():
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def valideer(data):
    """Controleert de binnengekomen gegevens. Geeft een fouttekst of None."""
    if not isinstance(data, dict) or not isinstance(data.get("stekkers"), list):
        return "Ongeldige structuur: 'stekkers' ontbreekt."
    if not data["stekkers"]:
        return "Geen stekkers opgegeven."
    for s in data["stekkers"]:
        if not isinstance(s, dict):
            return "Ongeldige stekker."
        if not isinstance(s.get("naam"), str) or not s["naam"].strip():
            return "Een stekker mist een naam."
        try:
            marge = int(s["aanlooptijd_minuten"])
        except (KeyError, ValueError, TypeError):
            return f"Aanlooptijd van {s.get('naam', '?')} is geen getal."
        if not 0 <= marge <= 600:
            return f"Aanlooptijd van {s['naam']} moet 0 t/m 600 minuten zijn."
        for veld in ("harde_uit", "ochtend_start"):
            if not TIJD.match(str(s.get(veld, ""))):
                return f"Tijd '{veld}' van {s['naam']} moet als UU:MM (bijv. 02:00)."
    return None


def schoon(data):
    """Bewaart alleen de bekende velden, in vaste volgorde."""
    return {"stekkers": [
        {
            "naam": s["naam"].strip(),
            "aanlooptijd_minuten": int(s["aanlooptijd_minuten"]),
            "harde_uit": s["harde_uit"],
            "ochtend_start": s["ochtend_start"],
        }
        for s in data["stekkers"]
    ]}


@app.get("/")
def pagina():
    return Response(HTML, mimetype="text/html; charset=utf-8")


@app.get("/api/schema")
def api_get():
    return jsonify(lees_schema())


@app.post("/api/schema")
def api_post():
    data = request.get_json(silent=True)
    fout = valideer(data)
    if fout:
        return jsonify({"ok": False, "fout": fout}), 400
    SCHEMA.write_text(
        json.dumps(schoon(data), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return jsonify({"ok": True})


HTML = """<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rooster - stekkers</title>
<style>
  :root { --accent: #4dabf7; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 24px; font-family: system-ui, sans-serif;
         background: #0b1622; color: #e6edf3; }
  h1 { font-weight: 600; font-size: 1.4rem; }
  h1 span { color: var(--accent); }
  p.uitleg { color: #9fb0c0; max-width: 46rem; }
  .stekker { background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08);
             border-radius: 14px; padding: 18px 20px; margin: 14px 0; max-width: 46rem; }
  .stekker h2 { font-size: 1.05rem; margin: 0 0 12px; }
  .rij { display: flex; flex-wrap: wrap; gap: 16px; }
  .veld { display: flex; flex-direction: column; gap: 4px; }
  .veld label { font-size: .82rem; color: #9fb0c0; }
  input { background: #0b1622; color: #e6edf3; border: 1px solid rgba(255,255,255,.15);
          border-radius: 8px; padding: 8px 10px; font-size: 1rem; }
  input:focus { outline: 2px solid var(--accent); border-color: var(--accent); }
  .knoppen { max-width: 46rem; margin-top: 16px; display: flex; align-items: center; gap: 14px; }
  button { background: var(--accent); color: #06121f; border: none; border-radius: 10px;
           padding: 10px 18px; font-size: 1rem; font-weight: 600; cursor: pointer; }
  button:disabled { opacity: .5; cursor: default; }
  #melding { font-size: .95rem; }
  .ok { color: #6ee7a8; } .fout { color: #ff9a9a; }
</style>
</head>
<body>
  <h1>Mijn<span>Huis</span> - rooster</h1>
  <p class="uitleg">Per stekker: de <em>aanlooptijd</em> is het aantal minuten
  voor zonsondergang dat de stekker aangaat. <em>Harde uit</em> is de tijd dat
  hij 's nachts uitgaat. <em>Ochtendstart</em> is de tijd waarop hij 's ochtends
  weer aangaat als het dan nog donker is, tot zonsopkomst. Wijzigingen werken
  binnen een minuut.</p>

  <div id="lijst"></div>

  <div class="knoppen">
    <button id="opslaan" disabled>Opslaan</button>
    <span id="melding"></span>
  </div>

<script>
  const lijst = document.getElementById("lijst");
  const knop = document.getElementById("opslaan");
  const melding = document.getElementById("melding");
  let huidig = null;

  function toonMelding(tekst, soort) {
    melding.textContent = tekst;
    melding.className = soort || "";
  }

  function bouw(schema) {
    huidig = schema;
    lijst.innerHTML = "";
    schema.stekkers.forEach((s, i) => {
      const kaart = document.createElement("div");
      kaart.className = "stekker";
      kaart.innerHTML = `
        <h2>${s.naam}</h2>
        <div class="rij">
          <div class="veld">
            <label>Aanlooptijd (minuten voor zonsondergang)</label>
            <input type="number" min="0" max="600" data-i="${i}" data-k="aanlooptijd_minuten" value="${s.aanlooptijd_minuten}">
          </div>
          <div class="veld">
            <label>Harde uit</label>
            <input type="time" data-i="${i}" data-k="harde_uit" value="${s.harde_uit}">
          </div>
          <div class="veld">
            <label>Ochtendstart</label>
            <input type="time" data-i="${i}" data-k="ochtend_start" value="${s.ochtend_start}">
          </div>
        </div>`;
      lijst.appendChild(kaart);
    });
    knop.disabled = false;
  }

  function verzamel() {
    const data = JSON.parse(JSON.stringify(huidig));
    lijst.querySelectorAll("input").forEach(inp => {
      const i = Number(inp.dataset.i), k = inp.dataset.k;
      data.stekkers[i][k] = (k === "aanlooptijd_minuten") ? Number(inp.value) : inp.value;
    });
    return data;
  }

  async function laden() {
    try {
      const r = await fetch("api/schema");
      bouw(await r.json());
    } catch (e) { toonMelding("Kon het rooster niet laden.", "fout"); }
  }

  knop.addEventListener("click", async () => {
    knop.disabled = true;
    toonMelding("Opslaan...", "");
    try {
      const r = await fetch("api/schema", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(verzamel())
      });
      const uit = await r.json();
      if (uit.ok) toonMelding("Opgeslagen. Werkt binnen een minuut.", "ok");
      else toonMelding(uit.fout || "Opslaan mislukt.", "fout");
    } catch (e) { toonMelding("Opslaan mislukt.", "fout"); }
    knop.disabled = false;
  });

  laden();
</script>
</body>
</html>"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090)
