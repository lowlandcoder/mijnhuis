#!/usr/bin/env bash
# Publiceert mijnhuis op de server: haalt de laatste versie uit GitHub en
# zet de bestanden op hun plek, zonder geheimen of runtime aan te raken.
#
# Werkwijze (net als bij de andere onderdelen):
#   1. Lokaal wijzigingen pushen naar GitHub (git push origin main).
#   2. Op de server dit script draaien.
#
# Laat bewust ongemoeid: config.json (eigen locatie en instellingen),
# mosquitto/data, mosquitto/log en zigbee2mqtt/data (o.a. de netwerksleutel).

set -euo pipefail

# Bron (repository-kopie) en doel (draaiende stack). Pas DOEL zo nodig aan
# op de map waar het draaiende docker-compose.yml staat; te vinden met
# `sudo docker compose ls` (kolom met het configuratiepad).
BRON="$HOME/mijnhuis-repo"
DOEL="/opt/mijnhuis"

echo "== mijnhuis publiceren =="

cd "$BRON"
git pull origin main

sudo mkdir -p "$DOEL/stekker" "$DOEL/rooster" "$DOEL/mosquitto/config"

# Code en instellingen die wél gedeeld zijn:
sudo cp "$BRON/docker-compose.yml"               "$DOEL/"
sudo cp "$BRON/stekker.py"                        "$DOEL/"
sudo cp "$BRON/stekker/Dockerfile"                "$DOEL/stekker/"
sudo cp "$BRON/rooster/app.py"                    "$DOEL/rooster/"
sudo cp "$BRON/rooster/Dockerfile"                "$DOEL/rooster/"
sudo cp "$BRON/mosquitto/config/mosquitto.conf"   "$DOEL/mosquitto/config/"

# config.json alleen aanmaken bij de allereerste keer; daarna nooit overschrijven.
if [ ! -f "$DOEL/config.json" ]; then
  sudo cp "$BRON/config.example.json" "$DOEL/config.json"
  echo "LET OP: config.json aangemaakt uit voorbeeld. Vul de eigen waarden in"
  echo "        (stekkernaam en locatie) en draai dit script daarna opnieuw."
fi

# Docker maakt van een ontbrekende mount-bron per ongeluk een MAP; opruimen.
if [ -d "$DOEL/schema.json" ]; then
  sudo rm -rf "$DOEL/schema.json"
fi

# schema.json (de bewerkbare tijden) alleen bij de eerste keer aanmaken; daarna
# nooit overschrijven, want de rooster-pagina wijzigt dit bestand.
if [ ! -f "$DOEL/schema.json" ]; then
  sudo cp "$BRON/schema.example.json" "$DOEL/schema.json"
  echo "schema.json aangemaakt uit voorbeeld. Pas de tijden aan via de"
  echo "rooster-pagina of rechtstreeks in dit bestand."
fi

# Stekker- en rooster-container (opnieuw) bouwen; broker en brug blijven staan.
cd "$DOEL"
sudo docker compose up -d --build stekker rooster

echo "== klaar =="
echo "Controleer met: sudo docker compose logs --tail 8 stekker"
echo "Rooster-pagina: https://mijnhuis.lab023.nl/rooster/"
