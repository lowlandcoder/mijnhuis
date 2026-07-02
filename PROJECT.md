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
server. Drie containers op een eigen netwerk `huis`:

- **mosquitto** — MQTT-broker, alleen binnen de stack bereikbaar, zonder
  wachtwoord (`allow_anonymous true`).
- **zigbee2mqtt** — leest de dongle uit; beheerpagina op poort 8080, ook
  bereikbaar via `zigbee2mqtt.lab023.nl` (nginx reverse proxy, wachtwoord
  gedeeld met MijnServer via `/etc/nginx/.htpasswd-mijnserver`, zie
  `nginx-zigbee2mqtt.conf` en HANDLEIDING stap 7).
- **stekker** — draait `stekker.py --loop`, bepaalt elke minuut de stand.

## Bestanden

| Bestand | Functie |
|---|---|
| `docker-compose.yml` | Definieert de drie containers; hierin het dongle-pad invullen |
| `stekker.py` | Schakelscript met avond-, nacht- en ochtendvenster (zie Tijdregeling) |
| `config.json` | Instellingen script: `mqtt_host` (=`mosquitto`), `stekker` (=`stekker_schuur`), locatie, tijdzone, `aanlooptijd_minuten`, `harde_uit`, `ochtend_start`. Staat in `.gitignore`, nooit naar GitHub |
| `config.example.json` | Voorbeeld van `config.json` zonder echte waarden; wel gedeeld |
| `stekker/Dockerfile` | Bouwt de stekker-container (python + astral + paho-mqtt) |
| `mosquitto/config/mosquitto.conf` | Broker-instellingen |
| `zigbee2mqtt/data/configuration.yaml` | Z2M-instellingen; handmatig aanmaken (zie HANDLEIDING stap 2) |
| `nginx-zigbee2mqtt.conf` | Reverse proxy met wachtwoord voor `zigbee2mqtt.lab023.nl` (HANDLEIDING stap 7) |
| `publiceer-mijnhuis.sh` | Publicatiescript op de server: `git pull` + bestanden naar `/opt/mijnhuis`, daarna rebuild van de stekker-container. Laat config.json en data-mappen ongemoeid |
| `HANDLEIDING.md` | Volledige installatie- en beheeruitleg |

## Tijdregeling

`stekker.py` bepaalt de stand met drie vensters; AAN zodra één venster geldt:

- **avond**: vanaf `aanlooptijd_minuten` (30) voor zonsondergang;
- **nacht**: door tot `harde_uit` (02:00), dan uit;
- **ochtend**: vanaf `ochtend_start` (06:00) tot zonsopkomst, maar alleen als
  het dan nog donker is (in de zomer dus niet).

Zonsopkomst en zonsondergang worden per dag met `astral` berekend uit de
breedte- en lengtegraad in `config.json`. De drie tijden staan ook in
`config.json` en zijn los aan te passen.

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
- Nog te doen: dongle-pad invullen, `configuration.yaml` aanmaken, locatie en
  stekkernaam in `config.json` zetten, stekker koppelen.
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
- Belangrijk: `config.json` is gitignored en gaat niet mee. De nieuwe
  schakeltijden werken toch, want het script vult ontbrekende sleutels met de
  standaardwaarden (30 min, 02:00, 06:00). De naam `stekker_schuur` in de
  lokale `config.json` komt dus niet vanzelf op de server; de servernaam blijft
  ongewijzigd tot het apparaat in Zigbee2MQTT én de server-`config.json` samen
  worden hernoemd.

## Mogelijke uitbreidingen

Schakeltijden aanpassen via `config.json`; meer apparaten; verbruik per
stekker meelezen (vergelijkbaar met mijnverbruik); broker beveiligen met
wachtwoord.
