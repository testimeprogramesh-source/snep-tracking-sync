# -*- coding: utf-8 -*-
"""
supabase_helpers.py
-------------------
Funksionet e PERBASHKETA te dy skripteve (ultra_portal_scrape.py dhe
postman_portal_scrape.py). Me pare çdo skript kishte kopjen e vet te ketyre
funksioneve, dhe ato kishin filluar te ndryshonin nga njera-tjetra (p.sh.
vetem Postman riprovonte kur lidhja me Supabase ngecte). Tani jane ne NJE
vend te vetem.

Keto funksione lexojne SUPABASE_URL dhe SUPABASE_SERVICE_ROLE_KEY nga
environment variables (te vendosura nga GitHub Actions).
"""

import os
import time
from datetime import timezone, timedelta

import requests

# Ora lokale e Shqiperise/Kosoves (te dy vendet kane te njejtat rregulla:
# +02:00 ne vere, +01:00 ne dimer). Me pare ora vendosej gjithmone +02:00,
# gje qe nga fundi i tetorit deri ne fund te marsit do ta zhvendoste çdo
# ngjarje 1 ore me vone ne faqen e klientit.
try:
    from zoneinfo import ZoneInfo
    ZONA_LOKALE = ZoneInfo("Europe/Tirane")
except Exception:  # sistem pa baze te dhenash per zonat kohore
    ZONA_LOKALE = timezone(timedelta(hours=2))


def ne_iso_lokale(dt_pa_zone) -> str:
    """datetime pa zone (ora siç shfaqet ne portal) -> tekst ISO 8601 me offset-in e sakte."""
    return dt_pa_zone.replace(tzinfo=ZONA_LOKALE).isoformat()


def _supabase():
    return (
        os.environ["SUPABASE_URL"].rstrip("/"),
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def koka_http(me_json: bool = True, prefer: str = None) -> dict:
    """Header-at standarde per çdo kerkese drejt Supabase (me service_role key)."""
    _, celesi = _supabase()
    koka = {"apikey": celesi, "Authorization": f"Bearer {celesi}"}
    if me_json:
        koka["Content-Type"] = "application/json"
    if prefer:
        koka["Prefer"] = prefer
    return koka


def url_rest(rruga: str) -> str:
    url, _ = _supabase()
    return f"{url}/rest/v1/{rruga}"


def kerko_me_rikthim(metoda, url, tentativa_max: int = 3, **kwargs):
    """
    Njesoj si requests.get/post(...), por RIPROVON (deri 3 here, me pauze qe
    rritet) kur lidhja me Supabase deshton perkohesisht (timeout, gabim
    rrjeti). Pa kete, nje lidhje e vetme qe ngec per pak sekonda e rrezonte
    GJITHE skanimin.
    """
    gabimi_fundit = None
    for tentativa in range(1, tentativa_max + 1):
        try:
            return metoda(url, **kwargs)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            gabimi_fundit = e
            if tentativa < tentativa_max:
                print(f"  (kujdes: lidhja me Supabase deshtoi perkohesisht, tentativa {tentativa}/{tentativa_max} -- riprovojme...)")
                time.sleep(3 * tentativa)
    raise gabimi_fundit


def push_to_supabase(order_number: str, barcode: str, events: list, courier: str):
    """Upsert i ngjarjeve ne public.tracking_events (tabele e perbashket, e dalluar nga 'courier')."""
    rreshtat_sipas_celesit = {}
    for e in events:
        rresht = {
            "order_number": order_number,
            "courier": courier,
            "barcode": barcode,
            "event_time": e["event_time"],
            "status_label": e["status_label"],
            "status_tag": e.get("status_tag"),
            "note": e.get("note"),
            "handled_by": e.get("handled_by"),
        }
        # Postgres refuzon nje upsert qe prek te njejtin rresht 2 here ne te
        # njejten kerkese ("ON CONFLICT DO UPDATE command cannot affect row a
        # second time") -- prandaj heqim dublikatat PARA dergimit.
        celesi = (rresht["order_number"], rresht["event_time"], rresht["status_label"])
        rreshtat_sipas_celesit[celesi] = rresht

    rreshtat = list(rreshtat_sipas_celesit.values())
    if not rreshtat:
        return

    resp = kerko_me_rikthim(
        requests.post,
        url_rest("tracking_events"),
        headers=koka_http(prefer="resolution=merge-duplicates,return=minimal"),
        params={"on_conflict": "order_number,event_time,status_label"},
        json=rreshtat,
        timeout=30,
    )
    if not resp.ok:
        print(f"  -> Supabase ktheu {resp.status_code}: {resp.text}")
    resp.raise_for_status()


def cleanup_old_events():
    """
    Thirr funksionin SQL 'cleanup_old_tracking_events' (i perbashket per te
    dy kurjeret) qe fshin porosite e vjetra nga tracking_events. Tabelat
    "*_parcels_seen" NUK preken -- qe skanimi te mos i rizbuloje si te reja.
    """
    resp = kerko_me_rikthim(
        requests.post,
        url_rest("rpc/cleanup_old_tracking_events"),
        headers=koka_http(),
        json={},
        timeout=30,
    )
    if not resp.ok:
        print(f"  -> (kujdes: pastrimi i te dhenave te vjetra deshtoi -- {resp.status_code}: {resp.text})")
    else:
        print("Pastrimi i porosive te vjetra u krye.")
