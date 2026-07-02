#!/usr/bin/env python3
"""
stekker.py - schakelt een of meer Zigbee-stekkers via Zigbee2MQTT.

Schakelregel per stekker (drie vensters, de stekker staat AAN als een
venster geldt):
- Avond: vanaf een aantal minuten voor zonsondergang (aanlooptijd_minuten)
  tot de harde uit-tijd. De stekker blijft dus de avond en de eerste
  nachturen aan.
- Harde uit: op de ingestelde tijd (harde_uit) gaat de stekker uit.
- Ochtend: vanaf de ochtendstart (ochtend_start) weer aan, maar alleen als
  het dan nog donker is, tot zonsopkomst. Bij zonsopkomst gaat de stekker
  uit. Is het om die tijd al licht (zomer), dan blijft hij uit.

De stekkers en hun tijden staan in schema.json en zijn per stekker apart in
te stellen (via de rooster-pagina). Het script leest schema.json elke minuut
opnieuw, zodat wijzigingen binnen een minuut werken zonder herstart.

config.json bevat de gedeelde instellingen: MQTT-verbinding, locatie en
tijdzone. Staat schema.json er niet, dan valt het script terug op één stekker
uit config.json.

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
SCHEMA = Path(__file__).with_name("schema.json")


def laad_json(pad):
    with open(pad, "r", encoding="utf-8") as bestand:
        return json.load(bestand)


def laad_config():
    return laad_json(CONFIG)


def lees_stekkers(cfg):
    """Geeft de lijst stekkers met hun tijden uit schema.json.

    Ontbreekt schema.json, dan valt het terug op één stekker uit config.json,
    zodat de oude opzet blijft werken.
    """
    if SCHEMA.exists():
        data = laad_json(SCHEMA)
        return data.get("stekkers", [])
    return [{
        "naam": cfg["stekker"],
        "aanlooptijd_minuten": cfg.get("aanlooptijd_minuten", 30),
        "harde_uit": cfg.get("harde_uit", "02:00"),
        "ochtend_start": cfg.get("ochtend_start", "06:00"),
    }]


def _tijd_op_datum(datum, tz, tekst):
    """Maakt een datetime op 'datum' om HH:MM in de gegeven tijdzone."""
    uur, minuut = (int(deel) for deel in tekst.split(":"))
    return datetime(datum.year, datum.month, datum.day, uur, minuut, tzinfo=tz)


def _avond_nacht_aan(nu, locatie, tz, marge, harde_uit):
    """Waar als nu in het avond-/nachtvenster valt: van 'marge' voor
    zonsondergang tot de harde uit-tijd. Dit venster kan over middernacht
    lopen, dus zowel de zonsondergang van vandaag als die van gisteren telt.
    """
    for dagoffset in (0, -1):
        datum = (nu + timedelta(days=dagoffset)).date()
        zon = sun(locatie.observer, date=datum, tzinfo=tz)
        start = zon["sunset"] - marge
        eind = _tijd_op_datum(start.date(), tz, harde_uit)
        if eind <= start:               # harde uit valt de volgende ochtend
            eind += timedelta(days=1)
        if start <= nu < eind:
            return True
    return False


def gewenste_stand(stekker, locatie, tz, nu):
    """Bepaalt AAN of UIT voor één stekker op basis van zijn eigen tijden.

    Geeft terug: (stand, info) met zonsopkomst, zonsondergang en het venster
    dat de stand bepaalt.
    """
    zon = sun(locatie.observer, date=nu.date(), tzinfo=tz)
    zon_op = zon["sunrise"]
    zon_onder = zon["sunset"]

    marge = timedelta(minutes=stekker.get("aanlooptijd_minuten", 60))
    ochtend_start = _tijd_op_datum(nu.date(), tz, stekker.get("ochtend_start", "06:00"))
    naloop = timedelta(minutes=stekker.get("ochtend_naloop_minuten", 30))

    avond_nacht = _avond_nacht_aan(
        nu, locatie, tz, marge, stekker.get("harde_uit", "02:00")
    )
    # Ochtend alleen als het om ochtend_start nog donker is (zon nog niet op).
    # Dan aan van ochtend_start tot zonsopkomst plus de naloop.
    donker_om_start = zon_op > ochtend_start
    ochtend = donker_om_start and (ochtend_start <= nu < (zon_op + naloop))

    if avond_nacht:
        reden = "avond" if nu >= (zon_onder - marge) else "nacht"
    elif ochtend:
        reden = "ochtend"
    else:
        reden = "uit"

    stand = "ON" if (avond_nacht or ochtend) else "OFF"
    return stand, {"zon_op": zon_op, "zon_onder": zon_onder, "reden": reden}


def stuur_stand(cfg, naam, stand):
    onderwerp = f"zigbee2mqtt/{naam}/set"
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


def een_keer(cfg, locatie, tz):
    nu = datetime.now(tz)
    for stekker in lees_stekkers(cfg):
        naam = stekker["naam"]
        stand, info = gewenste_stand(stekker, locatie, tz, nu)
        stuur_stand(cfg, naam, stand)
        print(
            f"{nu:%Y-%m-%d %H:%M} | {naam} | zon op {info['zon_op']:%H:%M} "
            f"| zon onder {info['zon_onder']:%H:%M} "
            f"| venster {info['reden']} | stand naar {stand}",
            flush=True,
        )


def maak_locatie(cfg):
    return LocationInfo(
        latitude=cfg["breedtegraad"],
        longitude=cfg["lengtegraad"],
    )


def loop(cfg, locatie, tz):
    """Blijft draaien en bepaalt elke minuut de stand voor alle stekkers."""
    while True:
        try:
            een_keer(cfg, locatie, tz)
        except Exception as fout:
            print(f"Fout: {fout}", file=sys.stderr, flush=True)
        time.sleep(60)


def main():
    cfg = laad_config()
    locatie = maak_locatie(cfg)
    tz = ZoneInfo(cfg["tijdzone"])
    if "--loop" in sys.argv:
        loop(cfg, locatie, tz)
    else:
        een_keer(cfg, locatie, tz)


if __name__ == "__main__":
    try:
        main()
    except Exception as fout:
        print(f"Fout: {fout}", file=sys.stderr)
        sys.exit(1)
