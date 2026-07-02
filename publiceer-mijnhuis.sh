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

sudo mkdir -p "$DOEL/stekker" "$DOEL/mosquitto/config"

# Code en instellingen die wél gedeeld zijn:
sudo cp "$BRON/docker-compose.yml"               "$DOEL/"
sudo cp "$BRON/stekker.py"                        "$DOEL/"
sudo cp "$BRON/stekker/Dockerfile"                "$DOEL/stekker/"
sudo cp "$BRON/mosquitto/config/mosquitto.conf"   "$DOEL/mosquitto/config/"

# config.json alleen aanmaken bij de allereerste keer; daarna nooit overschrijven.
if [ ! -f "$DOEL/config.json" ]; then
  sudo cp "$BRON/config.example.json" "$DOEL/config.json"
  echo "LET OP: config.json aangemaakt uit voorbeeld. Vul de eigen waarden in"
  echo "        (stekkernaam en locatie) en draai dit script daarna opnieuw."
fi

# Alleen de stekker-container hoeft opnieuw gebouwd; broker en brug blijven staan.
cd "$DOEL"
sudo docker compose up -d --build stekker

echo "== klaar =="
echo "Controleer met: sudo docker compose logs --tail 5 stekker"
