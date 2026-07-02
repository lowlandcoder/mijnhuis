#!/usr/bin/env python3
"""
stekker.py - schakelt een Zigbee-stekker via Zigbee2MQTT.

Schakelregel (drie vensters, de stekker staat AAN als een venster geldt):
- Avond: vanaf een aantal minuten voor zonsondergang (standaard 30) tot
  de harde uit-tijd. De stekker blijft dus de avond en de eerste nachturen
  aan.
- Harde uit: op de ingestelde tijd (standaard 02:00) gaat de stekker uit.
- Ochtend: vanaf de ochtendstart (standaard 06:00) weer aan, maar alleen
  als het dan nog donker is, tot zonsopkomst. Bij zonsopkomst gaat de
  stekker uit. Is het om 06:00 al licht (zomer), dan blijft hij uit.

Het script bepaalt elke keer dat het draait de gewenste stand en stuurt
die naar de stekker. Hetzelfde commando nogmaals sturen is ongevaarlijk.

Twee manieren van draaien:
- Zonder argument: één keer bepalen en sturen.
- Met --loop: blijft draaien en bepaalt elke minuut opnieuw de stand
  (zo draait de losse container in de Docker-stack).

Benodigd: pip3 install astral paho-mqtt
"""

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from astral import LocationInfo
from astral.sun import sun
import paho.mqtt.publish as publish

CONFIG = Path(__file__).with_name("config.json")


def laad_config():
    with open(CONFIG, "r", encoding="utf-8") as bestand:
        return json.load(bestand)


def _op_tijd(nu, tekst):
    """Maakt van 'HH:MM' een tijd op dezelfde dag als nu."""
    uur, minuut = (int(deel) for deel in tekst.split(":"))
    return nu.replace(hour=uur, minute=minuut, second=0, microsecond=0)


def gewenste_stand(cfg, nu):
    """Bepaalt AAN of UIT op basis van de avond-, nacht- en ochtendvensters.

    Geeft terug: (stand, info) met info over zonsopkomst, zonsondergang en
    het venster dat de stand bepaalt.
    """
    locatie = LocationInfo(
        latitude=cfg["breedtegraad"],
        longitude=cfg["lengtegraad"],
    )
    tz = ZoneInfo(cfg["tijdzone"])
    zon = sun(locatie.observer, date=nu.date(), tzinfo=tz)
    zon_op = zon["sunrise"]
    zon_onder = zon["sunset"]

    marge = timedelta(minutes=cfg.get("aanlooptijd_minuten", 30))
    harde_uit = _op_tijd(nu, cfg.get("harde_uit", "02:00"))
    ochtend_start = _op_tijd(nu, cfg.get("ochtend_start", "06:00"))

    avond = nu >= (zon_onder - marge)
    nacht = nu < harde_uit
    ochtend = ochtend_start <= nu < zon_op  # alleen zolang het nog donker is

    if avond:
        reden = "avond"
    elif nacht:
        reden = "nacht"
    elif ochtend:
        reden = "ochtend"
    else:
        reden = "uit"

    stand = "ON" if (avond or nacht or ochtend) else "OFF"
    return stand, {"zon_op": zon_op, "zon_onder": zon_onder, "reden": reden}


def stuur_stand(cfg, stand):
    onderwerp = f"zigbee2mqtt/{cfg['stekker']}/set"
    payload = json.dumps({"state": stand})
    auth = None
    if cfg.get("mqtt_gebruiker"):
        auth = {
            "username": cfg["mqtt_gebruiker"],
            "password": cfg.get("mqtt_wachtwoord", ""),
        }
    publish.single(
        onderwerp,
        payload=payload,
        hostname=cfg.get("mqtt_host", "127.0.0.1"),
        port=cfg.get("mqtt_poort", 1883),
        auth=auth,
    )


def een_keer(cfg):
    tz = ZoneInfo(cfg["tijdzone"])
    nu = datetime.now(tz)
    stand, info = gewenste_stand(cfg, nu)
    stuur_stand(cfg, stand)
    print(
        f"{nu:%Y-%m-%d %H:%M} | zon op {info['zon_op']:%H:%M} "
        f"| zon onder {info['zon_onder']:%H:%M} "
        f"| venster {info['reden']} | stand naar {stand}",
        flush=True,
    )


def loop(cfg):
    """Blijft draaien en bepaalt elke minuut de stand."""
    while True:
        try:
            een_keer(cfg)
        except Exception as fout:
            print(f"Fout: {fout}", file=sys.stderr, flush=True)
        time.sleep(60)


def main():
    cfg = laad_config()
    if "--loop" in sys.argv:
        loop(cfg)
    else:
        een_keer(cfg)


if __name__ == "__main__":
    try:
        main()
    except Exception as fout:
        print(f"Fout: {fout}", file=sys.stderr)
        sys.exit(1)
