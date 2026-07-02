# mijnhuis — projectcontext

Vaste context voor het onderdeel `mijnhuis` van het Lab023-platform. Dit
bestand kort houden en bij elke sessie als eerste laten lezen, zodat de opzet
niet telkens opnieuw hoeft te worden uitgezocht. Voor de uitgebreide
installatie-uitleg: zie `HANDLEIDING.md` in deze map.

## Doel

Home automation op de Lab023-server. Eerste functie: een Zigbee-stekker
(`stekker_schuur`) die 's avonds en 's ochtends licht schakelt op basis van
de zon.

## Hardware

- Coördinator: Sonoff Zigbee 3.0 USB Dongle Plus, variant **ZBDongle-P**
  (chip CC2652P). Adapter in Zigbee2MQTT: **zstack**.
- Dongle-pad opzoeken met `ls -l /dev/serial/by-id/` (regel met
  `Silicon_Labs`). Dit pad invullen in `docker-compose.yml`.

## Opzet

Eén zelfstandige Docker-stack (`docker compose`), los van de rest van de
server. Vier containers op een eigen netwerk `huis`:

- **mosquitto** — MQTT-broker, alleen binnen de stack bereikbaar, zonder
  wachtwoord (`allow_anonymous true`).
- **zigbee2mqtt** — leest de dongle uit; beheerpagina op poort 8080, achter
  wachtwoord bereikbaar via `mijnhuis.lab023.nl` (nginx reverse proxy in het
  `default`-serverblok, wachtwoord gedeeld met MijnServer via
  `/etc/nginx/.htpasswd-mijnserver`). Tweede ingang: `zigbee2mqtt.lab023.nl`.
- **stekker** — draait `stekker.py --loop`, schakelt elke minuut alle stekkers
  uit `schema.json`.
- **rooster** — kleine Flask-service (poort 8090) met de bewerkpagina voor de
  tijden, bereikbaar via `mijnhuis.lab023.nl/rooster/`. Schrijft `schema.json`.

## Bestanden

| Bestand | Functie |
|---|---|
| `docker-compose.yml` | Definieert de vier containers; hierin het dongle-pad invullen |
| `stekker.py` | Schakelscript; loopt alle stekkers uit `schema.json` af (zie Tijdregeling) |
| `config.json` | Gedeelde instellingen: `mqtt_host` (=`mosquitto`), locatie, tijdzone. Staat in `.gitignore`, nooit naar GitHub |
| `config.example.json` | Voorbeeld van `config.json` zonder echte waarden; wel gedeeld |
| `schema.json` | Bewerkbare tijden per stekker (naam, `aanlooptijd_minuten`, `harde_uit`, `ochtend_start`). Wordt door de rooster-pagina geschreven en door `stekker.py` elke minuut gelezen. Staat in `.gitignore` |
| `schema.example.json` | Voorbeeld van `schema.json`; wel gedeeld |
| `rooster/app.py` + `rooster/Dockerfile` | Flask-bewerkpagina en API die `schema.json` valideert en opslaat |
| `stekker/Dockerfile` | Bouwt de stekker-container (python + astral + paho-mqtt) |
| `mosquitto/config/mosquitto.conf` | Broker-instellingen |
| `zigbee2mqtt/data/configuration.yaml` | Z2M-instellingen; handmatig aanmaken (zie HANDLEIDING stap 2) |
| `nginx-zigbee2mqtt.conf` | Reverse proxy met wachtwoord voor `zigbee2mqtt.lab023.nl` (HANDLEIDING stap 7) |
| `publiceer-mijnhuis.sh` | Publicatiescript op de server: `git pull` + bestanden naar `/opt/mijnhuis`, daarna rebuild van de stekker-container. Laat config.json en data-mappen ongemoeid |
| `HANDLEIDING.md` | Volledige installatie- en beheeruitleg |

## Tijdregeling

`stekker.py` bepaalt per stekker de stand met twee vensters; AAN zodra één
venster geldt:

- **avond/nacht**: een tijdsinterval van `aanlooptijd_minuten` (standaard 60)
  voor zonsondergang tot `harde_uit`. Dit interval kan over middernacht lopen
  (bijv. aan om 21:04, uit om 02:00 de volgende ochtend). Het script kijkt
  daarom naar de zonsondergang van vandaag én van gisteren.
- **ochtend**: alleen als het om `ochtend_start` (06:00) nog donker is (zon nog
  niet op). Dan aan van `ochtend_start` tot zonsopkomst plus
  `ochtend_naloop_minuten` (standaard 30). In de zomer is het om 06:00 al licht,
  dus dan geen ochtendvenster.

Elke stekker heeft eigen waarden voor `aanlooptijd_minuten`, `harde_uit`,
`ochtend_start` en `ochtend_naloop_minuten` in `schema.json`, te wijzigen via de
rooster-pagina. Zonsopkomst en zonsondergang worden per dag met `astral`
berekend uit de breedte- en lengtegraad in `config.json`. `stekker.py` leest
`schema.json` elke minuut, dus wijzigingen werken binnen een minuut zonder
herstart.

## Veelgebruikte commando's

```bash
cd /opt/mijnhuis
sudo docker compose up -d --build      # starten / herbouwen
sudo docker compose logs -f stekker    # verloop volgen
sudo docker compose down               # stoppen
```

Stekker testen via de broker-container:

```bash
sudo docker exec mosquitto mosquitto_pub -t "zigbee2mqtt/<naam>/set" -m '{"state":"ON"}'
```

## Conventies en stand van zaken

- Lokale werkmap: `C:\Lab023\mijnhuis`. Doel op de server: `/opt/mijnhuis/`.
- MQTT-onderwerp van een apparaat: `zigbee2mqtt/<naam>/set` met payload
  `{"state":"ON"}` of `{"state":"OFF"}`.
- Stand: live op de server. De stack draait, de nieuwe schakelregeling
  (avond/nacht/ochtend) is uitgerold en het apparaat heet `stekker_schuur`
  in zowel Zigbee2MQTT als de server-`config.json`.
- De beheerpagina staat als kaart op de startpagina (`start.lab023.nl`),
  wijzend naar `zigbee2mqtt.lab023.nl`.
- `.gitignore` sluit `config.json`, `__pycache__/`, `mosquitto/data/`,
  `mosquitto/log/` en `zigbee2mqtt/data/` uit: hierin staan het wachtwoord,
  de eigen locatie en de gegenereerde Zigbee-netwerksleutel. `config.example.json`
  is wel gedeeld.
- Publiceren: lokaal `git push origin main`, daarna op de server
  `~/publiceer-mijnhuis.sh`. Bron `~/mijnhuis-repo`, doel `/opt/mijnhuis`.
- GitHub-repository: `lowlandcoder/mijnhuis`. Vermelding in de hoofd-
  `OVERZICHT.md` staat er al in.
- Belangrijk: `config.json` is gitignored en gaat niet mee naar GitHub of de
  server. De schakeltijden werken toch, want het script vult ontbrekende
  sleutels met de standaardwaarden (30 min, 02:00, 06:00). Wijzigingen aan de
  server-`config.json` (zoals de apparaatnaam) worden daar handmatig gedaan,
  gevolgd door `docker compose restart stekker` om ze in te lezen.
- Apparaat hernoemen: doe dit altijd op twee plekken tegelijk, anders komt het
  schakelbericht niet aan. In Zigbee2MQTT via
  `zigbee2mqtt/bridge/request/device/rename` en in de server-`config.json`.

## Mogelijke uitbreidingen

Schakeltijden aanpassen via `config.json`; meer apparaten; verbruik per
stekker meelezen (vergelijkbaar met mijnverbruik); broker beveiligen met
wachtwoord.
