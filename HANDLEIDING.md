# Home automation met de Sonoff ZBDongle-P

Doel: een Zigbee-stekker (`stekker_schuur`) die 's avonds en 's ochtends licht
schakelt op basis van de zon. De hele opzet draait als één zelfstandige
Docker-stack, los van de rest van de server. Eén commando start of stopt
het geheel.

De stack bevat drie containers:

- **mosquitto**: de MQTT-broker; het doorgeefluik tussen de onderdelen.
- **zigbee2mqtt**: leest de Sonoff-dongle uit en zet elk Zigbee-apparaat om
  in MQTT-berichten.
- **stekker**: draait `stekker.py`, bepaalt elke minuut op basis van de
  zonsondergang of de stekker aan of uit moet en stuurt dat door.

De containers praten onderling via een eigen Docker-netwerk (`huis`). De
broker is daardoor niet vanaf buiten bereikbaar; alleen de beheerpagina van
Zigbee2MQTT staat op poort 8080.

## Mapindeling

Zet de map `mijnhuis` als geheel op de server, bijvoorbeeld onder
`/opt/mijnhuis/`. De indeling:

```
mijnhuis/
├── docker-compose.yml
├── config.json                     # instellingen voor het stekkerscript
├── stekker.py                      # het script zelf
├── stekker/Dockerfile              # bouwt de stekker-container
└── mosquitto/config/mosquitto.conf # instellingen voor de broker
```

De mappen `mosquitto/data`, `mosquitto/log` en `zigbee2mqtt/data` maakt
Docker bij de eerste start vanzelf aan.

## Stap 1 — Het poortpad van de dongle vinden

De dongle is een ZBDongle-P (chip CC2652P). Deze variant gebruikt in
Zigbee2MQTT de adapter `zstack`. Steek de dongle in de server en draai:

```bash
ls -l /dev/serial/by-id/
```

De ZBDongle-P verschijnt als een regel met `Silicon_Labs` in de naam,
bijvoorbeeld `usb-Silicon_Labs_CP2102N_...`. Noteer dat volledige pad. Het
blijft gelijk, ook na het opnieuw inpluggen, en is daarom betrouwbaarder dan
`/dev/ttyUSB0`.

Vul dit pad in `docker-compose.yml` in bij de container `zigbee2mqtt`, op de
regel onder `devices`:

```yaml
    devices:
      - /dev/serial/by-id/usb-Silicon_Labs_CP2102N_...:/dev/ttyACM0
```

Het deel vóór de dubbele punt is het pad op de server; het deel erna
(`/dev/ttyACM0`) is hoe de dongle binnen de container heet.

## Stap 2 — Instellingen voor Zigbee2MQTT

Maak het bestand `zigbee2mqtt/data/configuration.yaml` in de map `mijnhuis`:

```yaml
homeassistant: false
permit_join: false

mqtt:
  base_topic: zigbee2mqtt
  server: mqtt://mosquitto:1883

serial:
  port: /dev/ttyACM0
  adapter: zstack

frontend:
  port: 8080

advanced:
  network_key: GENERATE
```

Let op twee dingen die bij de Docker-stack horen:

- `server` wijst naar `mosquitto`, de naam van de broker-container, niet naar
  een IP-adres.
- `port` is `/dev/ttyACM0`, het pad binnen de container uit stap 1.

## Stap 3 — De instellingen van het stekkerscript

Pas `config.json` aan:

- `mqtt_host`: laat dit op `mosquitto` staan (de naam van de broker-container).
- `stekker`: de naam die de stekker in stap 5 krijgt.
- `breedtegraad` en `lengtegraad`: de eigen locatie. De standaardwaarden
  wijzen naar Amsterdam. De juiste waarden voor de eigen plaats zijn al
  bekend uit mijnweer.
- `mqtt_gebruiker` en `mqtt_wachtwoord`: leeg laten; de broker draait voor de
  eenvoud zonder wachtwoord en is alleen binnen de stack bereikbaar.

## Stap 4 — De stack starten

Zorg dat Docker en de plug-in `docker compose` op de server staan. Start dan
vanuit de map `mijnhuis`:

```bash
cd /opt/mijnhuis
sudo docker compose up -d --build
```

Controleer of alles draait en bekijk de logregels:

```bash
sudo docker compose ps
sudo docker compose logs -f zigbee2mqtt
```

Bij de melding dat Zigbee2MQTT is gestart en met de broker verbonden is, is
de brug klaar. De beheerpagina staat op `http://SERVER-IP:8080`, alleen
binnen het eigen netwerk. Zie stap 7 voor toegang van buitenaf via
`zigbee2mqtt.lab023.nl`.

## Stap 5 — De stekker koppelen

1. Open de beheerpagina (`http://SERVER-IP:8080`).
2. Zet rechtsboven **Permit join** aan (kies een korte tijd, bijvoorbeeld
   vijf minuten).
3. Zet de Zigbee-stekker in de koppelstand. Bij de meeste stekkers gebeurt
   dat door de knop ongeveer vijf seconden ingedrukt te houden tot het
   lampje knippert.
4. De stekker verschijnt vanzelf in de lijst. Geef hem een herkenbare naam,
   bijvoorbeeld `stekker_schuur`, en vul diezelfde naam in `config.json`
   in bij `stekker`.
5. Zet **Permit join** daarna weer uit.

Na het wijzigen van `config.json` de stekker-container opnieuw starten:

```bash
sudo docker compose up -d stekker
```

Test de besturing handmatig via de broker-container:

```bash
sudo docker exec mosquitto mosquitto_pub -t "zigbee2mqtt/stekker_schuur/set" -m '{"state":"ON"}'
sudo docker exec mosquitto mosquitto_pub -t "zigbee2mqtt/stekker_schuur/set" -m '{"state":"OFF"}'
```

Klikt de stekker hoorbaar aan en uit, dan werkt de besturing.

## Stap 6 — De automatische schakeling controleren

De stekker-container draait `stekker.py --loop` en bepaalt elke minuut de
juiste stand volgens de schakelregeling (zie verderop). Volg het verloop met:

```bash
sudo docker compose logs -f stekker
```

Elke minuut komt er een regel bij met de tijd, de zonsopkomst en
zonsondergang van vandaag, het geldende venster (avond, nacht, ochtend of
uit) en de stand die is gestuurd.

## Stap 7 — Publieke toegang via zigbee2mqtt.lab023.nl

Optioneel: de beheerpagina ook van buiten het eigen netwerk bereikbaar maken,
op `zigbee2mqtt.lab023.nl`. Omdat deze pagina Zigbee-apparaten kan bedienen,
staat hij achter een wachtwoord, net als MijnServer, en gebruikt daarvoor
bewust hetzelfde wachtwoordbestand (`/etc/nginx/.htpasswd-mijnserver`): één
gebruikersnaam en wachtwoord voor beide pagina's, op één plek te wijzigen.

1. Wachtwoord instellen — alleen nodig als `/etc/nginx/.htpasswd-mijnserver`
   nog niet bestaat (bijvoorbeeld als MijnServer nog niet is ingericht):
   ```bash
   sudo apt install apache2-utils
   sudo htpasswd -c /etc/nginx/.htpasswd-mijnserver peter
   ```
   Bestaat het bestand al, dan is deze stap niet nodig.
2. `nginx-zigbee2mqtt.conf` plaatsen als `/etc/nginx/sites-available/zigbee2mqtt`,
   activeren met een symlink naar `sites-enabled` en HTTPS instellen met
   Certbot.
3. Nginx herladen: `sudo nginx -t && sudo systemctl reload nginx`.

De instelling stuurt het verkeer door naar `127.0.0.1:8080`, dezelfde poort
die de container al open zet in `docker-compose.yml`. Er is geen aparte
documentroot of publicatiescript nodig: de pagina komt rechtstreeks van de
container.

## Beheer van de stack

```bash
sudo docker compose up -d --build   # starten of na een wijziging herbouwen
sudo docker compose down            # alles stoppen
sudo docker compose restart stekker # alleen het script herstarten
sudo docker compose logs -f         # alle logregels volgen
```

## Hoe de tijdregeling werkt

Het script bepaalt de stand met drie vensters. De stekker staat AAN zodra
één venster geldt, anders UIT:

- **Avond:** vanaf `aanlooptijd_minuten` (standaard 30) voor zonsondergang.
  De stekker gaat dus een half uur voor zonsondergang aan en blijft de avond
  en de eerste nachturen aan.
- **Nacht/harde uit:** de stekker gaat uit op `harde_uit` (standaard 02:00)
  en blijft uit tot de ochtend.
- **Ochtend:** vanaf `ochtend_start` (standaard 06:00) weer aan, maar alleen
  als het dan nog donker is, tot zonsopkomst. Bij zonsopkomst gaat de stekker
  uit. Is het om 06:00 al licht (zomer), dan blijft hij uit.

Alle drie de tijden staan in `config.json` en zijn los aan te passen. De
grens tussen donker en licht is de zonsopkomst, die het script per dag
berekent voor de eigen locatie.

Kort samengevat over een etmaal: aan vanaf een half uur voor zonsondergang,
door tot 02:00, dan uit, 's ochtends van 06:00 tot zonsopkomst weer aan als
het donker is, daarna overdag uit.

## Latere uitbreidingen

- De schakeltijden aanpassen via `config.json` (`aanlooptijd_minuten`,
  `harde_uit`, `ochtend_start`).
- Meer apparaten door per stekker een vermelding in `config.json` toe te
  voegen.
- Verbruik per stekker meelezen, vergelijkbaar met mijnverbruik, als de
  stekker stroommeting ondersteunt.
- De broker beveiligen met een wachtwoord; vul dan `mqtt_gebruiker` en
  `mqtt_wachtwoord` in `config.json` in en zet `allow_anonymous false` in
  `mosquitto.conf`.
```
