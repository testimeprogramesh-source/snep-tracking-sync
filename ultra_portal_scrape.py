# -*- coding: utf-8 -*-
"""
ultra_portal_scrape.py
-----------------------
Skript qe lidhet me portalin e biznesit te Ultra Post (u-cep.com), kerkon
nje pako sipas NUMRIT TE POROSISE (fusha "Numri Fatures" ne portal, p.sh.
"3797608" -- JO barkodi SN, sepse klienti nuk e njeh/ka barkodin SN, vetem
numrin e porosise se tij), dhe nxjerr VETEM seksionin "Gjurmimi" (linja
kohore: date/ore, status, badge, shenim, agjenci qe e trajtoi) -- KURRE
emrin e klientit, telefonin, apo vleren e pakos.

STATUSI: E GJITHA E VERIFIKUAR LIVE ne portalin real te SNEP (03/09/2026),
me 3 pako te ndryshme (nje "Ne Pritje/Deshtoi", nje "Per Shperndarje", nje
"Dorezuar") -- perfshire kerkimin me "Numri Fatures":
  - SN9128109  <->  Numer Porosie 3796633
  - SN9134225  <->  Numer Porosie 3797608
  - SN9127105  <->  Numer Porosie 3795461

Pjesa e vetme qe MBETET PER T'U KONFIRMUAR: fushat e faqes se LOGIN-it
(ID_FUSHA_PERDORUESI / ID_FUSHA_FJALEKALIMI / SELEKTOR_BUTONI_HYR) -- nuk
munda t'i shoh sepse ju ishit tashme te loguar (dhe nuk deshiruam t'ju
nxirrnim nga sesioni). Vlerat poshte jane nje HAMENDESIM i arsyeshem
(portali perdor Laravel + Metronic, qe zakonisht perdorin "email" /
"password"), por DUHET KONFIRMUAR: hapni nje faqe "incognito" (ose dilni
per 10 sekonda), shikoni F12 -> Elements tek fusha e email/password, dhe
me konfirmoni ose korrigjoni.

SI FUNKSIONON KERKIMI ME NUMER POROSIE (verifikuar live):
  1. Shkon tek https://u-cep.com/businesses-portal/parcels
  2. Hap panelin "Filtër" (eshte i mbyllur si default -- kerkon nje klik
     tek "accordion-button" qe permban tekstin "Filtër")
  3. Shkruan numrin e porosise tek fusha id="filter_invoice_number"
     ("Numri Faturës" ne UI)
  4. Klikon butonin id="apply_filter_button" (nje <a class="btn btn-primary">,
     JO <button>)
  5. Pret qe tabela e rezultateve te filtrohet ne 1 rresht, gjen linkun e
     barkodit brenda atij rreshti, e klikon (kjo hap faqen/modalin e pakos
     -- URL ndryshon vete, s'ka nevoje te ndertojme URL-ne, sepse ID-ja e
     brendshme e portalit NUK korrespondon 1-me-1 me barkodin e dukshem)
  6. Nxjerr te gjithe rreshtat brenda #history-preview .timeline-item

  SHENIM: faqja PUBLIKE e gjurmimit (u-cep.com/tracking?barcode=...) PRANON
  VETEM barkodin SN, JO numrin e porosise -- e testuar live, jep "Pako
  nuk ekziston". Prandaj s'ka "fallback" publik per klientet qe kerkojne
  me numer porosie -- Supabase eshte e vetmja rruge.

STRUKTURA E VERIFIKUAR E NJE RRESHTI GJURMIMI (shembull real):
  <div class="timeline-item">
    <div class="timeline-label fw-bolder text-gray-800 fs-6">03/09/2026 12:43:55</div>
    <div class="timeline-badge"><i class="fa fa-genderless text-warning fs-1"></i></div>
    <div class="timeline-content">
      <div class="row">
        <div class="col-12 col-md-8">
          <h4>
            Ne Pritje
            <span class="badge badge-xs badge-light-danger">Dorezimi Deshtoi</span>
          </h4>
          <p class="text-danger fw-bold fs-4">Kerkon ta marre ne agjensi</p>
        </div>
        <div class="col-12 col-md-4 text-md-end">
          <h6>Agjencia Ultra Durres - Perpunues Agjensie</h6>
          <p class="text-muted fs-5 m-1">Agjensia Agjencia Ultra Durres</p>
        </div>
      </div>
    </div>
  </div>

  Rreshta pa "shenim" real e shfaqin placeholder-in "Nuk ka komente..." --
  script-i e trajton kete si "s'ka shenim" (None), jo si tekst i vertete.

SI TA PERDORNI (manualisht, per teste):
  1. pip install selenium webdriver-manager requests
  2. Konfirmoni/korrigjoni ID_FUSHA_PERDORUESI etj (shiko shenimin siper).
  3. Vendosni si environment variables:
       export ULTRA_USERNAME="..."
       export ULTRA_PASSWORD="..."
       export SUPABASE_URL="https://xxxx.supabase.co"
       export SUPABASE_SERVICE_ROLE_KEY="..."   # "service_role", jo "anon"
  4. Xhironi: python ultra_portal_scrape.py 3797608 3796633 ...
     (numra porosie, JO barkode SN)

SI XHIRON AUTOMATIKISHT (p.sh. nga GitHub Actions, cdo 15 min):
  Xhironi PA asnje argument: python ultra_portal_scrape.py
  Ne kete rast, skripti VETE lexon nga tabela Supabase "orders_to_track"
  (kolona order_number, ku active = true) dhe kontrollon vetem ato porosi
  -- nuk ka nevoje t'i jepni numrat ne linjen e komandes. Pasi nje porosi
  del "Dorezuar", skripti e vendos vete active=false ne ate tabele, qe te
  mos vazhdoje ta kontrolloje pa nevoje.

  SHTIMI I POROSIVE NE "orders_to_track": per momentin behet manualisht
  (Supabase -> Table Editor -> orders_to_track -> Insert row, vetem fusha
  order_number nevojitet). Nese sistemi juaj i postes mund te therrase nje
  API me vone, kjo mund te automatizohet (shih supabase_schema.sql).

KU DUHET TE XHIROJE KY SKRIPT: jo brenda bisedes me Claude (s'jam sherbim
i qendrueshem 24/7) -- duhet nje vend qe ju kontrolloni: nje server i
vogel (VPS), nje "scheduled job" (cron), ose nje "Github Actions" i
planifikuar (shiko .github/workflows/sync.yml). Rekomandohet ta xhironi
periodikisht (p.sh. 1 here ne 10-15 minuta) per porosite AKTIVE, jo ne cdo
klikim te klientit -- keshtu shmang mbingarkimin/flamimin e llogarise se
biznesit te SNEP ne portal.
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException


# ------------------------------------------------------------------
# 1) FAQJA E LOGIN-IT -- HAMENDESIM, DUHET KONFIRMUAR (shiko shenimin
#    ne krye te skedarit). Nese s'punon, na thoni ID/name e sakte.
# ------------------------------------------------------------------
URL_LOGIN = "https://u-cep.com/businesses-portal/login"
ID_FUSHA_PERDORUESI = "email"          # HAMENDESIM -- konfirmoni
ID_FUSHA_FJALEKALIMI = "password"      # HAMENDESIM -- konfirmoni
SELEKTOR_BUTONI_HYR = "button[type=submit]"   # HAMENDESIM -- konfirmoni

# ------------------------------------------------------------------
# 2) FAQJA E LISTES SE PAKOVE + FILTRI "NUMRI FATURES" -- VERIFIKUAR LIVE
# ------------------------------------------------------------------
URL_LISTA_PAKOVE = "https://u-cep.com/businesses-portal/parcels"
SELEKTOR_FILTER_ACCORDION = "button.accordion-button"     # hap panelin "Filtër"
ID_FUSHA_NUMER_POROSIE = "filter_invoice_number"           # "Numri Faturës"
ID_BUTONI_APLIKO_FILTER = "apply_filter_button"             # <a>, jo <button>

# ------------------------------------------------------------------
# 3) SELEKTORET E SEKSIONIT "GJURMIMI" -- VERIFIKUAR LIVE (3 pako te
#    ndryshme, statuse te ndryshme)
# ------------------------------------------------------------------
SEL_RRESHTAT = "#history-preview .timeline-item"
SEL_DATE_ORE = ".timeline-label.fw-bolder"          # brenda nje rreshti
SEL_STATUS_H4 = ".timeline-content h4"
SEL_BADGE = ".timeline-content h4 .badge"
SEL_SHENIM = ".timeline-content .col-12.col-md-8 > p"
SEL_AGJENCIA = ".col-md-4 h6"

SHENIM_PLACEHOLDER_BOSH = "nuk ka komente"   # e shperfillim si "s'ka shenim"


def login_to_ultra(username: str, password: str, headless: bool = True):
    """Hap Chrome, logohet ne portalin e biznesit te Ultra Post. Kthen 'driver'."""
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,1000")
    driver = webdriver.Chrome(options=options)

    driver.get(URL_LOGIN)
    wait = WebDriverWait(driver, 15)
    wait.until(EC.presence_of_element_located((By.NAME, ID_FUSHA_PERDORUESI))).send_keys(username)
    driver.find_element(By.NAME, ID_FUSHA_FJALEKALIMI).send_keys(password)
    driver.find_element(By.CSS_SELECTOR, SELEKTOR_BUTONI_HYR).click()

    # prisni te mbarrojme ne /dashboard (shenje qe login-i funksionoi)
    wait.until(EC.url_contains("/businesses-portal/dashboard"))
    return driver


def find_and_open_parcel_by_order_number(driver, order_number: str):
    """
    Shkon tek lista e pakove, hap panelin "Filtër", kerkon numrin e
    porosise tek "Numri Faturës", dhe klikon rreshtin e vetem qe rezulton
    per te hapur faqen/modalin e pakos. Kthen barkodin SN te gjetur
    (per referencen tuaj -- ruhet ne kolonen "barcode", jo ne ate publike).
    """
    wait = WebDriverWait(driver, 15)
    driver.get(URL_LISTA_PAKOVE)

    # hap panelin "Filtër" (i mbyllur si default)
    accordion = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELEKTOR_FILTER_ACCORDION)))
    accordion.click()

    fusha = wait.until(EC.presence_of_element_located((By.ID, ID_FUSHA_NUMER_POROSIE)))
    fusha.clear()
    fusha.send_keys(order_number)

    driver.find_element(By.ID, ID_BUTONI_APLIKO_FILTER).click()

    # pas filtrit duhet te mbetet 1 rresht, me nje link brenda kolones BARKODI
    def _gjej_link(d):
        links = d.find_elements(By.CSS_SELECTOR, "table a")
        return links[0] if links else False

    link = wait.until(_gjej_link)
    barcode_gjetur = link.text.strip()
    link.click()

    # prisni te ngarkohet seksioni i gjurmimit
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SEL_RRESHTAT)))
    return barcode_gjetur


def get_tracking_events(driver):
    """
    Supozon qe jemi TASHME tek faqja/modali i pakos (thirrni
    find_and_open_parcel_by_order_number me pare). Nxjerr VETEM linjen
    kohore te gjurmimit -- kurre emrin, telefonin, apo vleren e klientit.
    """
    rreshtat = driver.find_elements(By.CSS_SELECTOR, SEL_RRESHTAT)

    ngjarjet = []
    for rresht in rreshtat:
        def _text(selector):
            try:
                return rresht.find_element(By.CSS_SELECTOR, selector).text.strip() or None
            except NoSuchElementException:
                return None

        date_ore_raw = _text(SEL_DATE_ORE)
        if not date_ore_raw:
            continue

        h4_full = _text(SEL_STATUS_H4) or ""
        badge_text = _text(SEL_BADGE)
        status_label = h4_full.replace(badge_text, "").strip() if badge_text else h4_full

        note = _text(SEL_SHENIM)
        if note and SHENIM_PLACEHOLDER_BOSH in note.lower():
            note = None

        handled_by = _text(SEL_AGJENCIA)

        ngjarjet.append({
            "event_time": _parse_data_ore(date_ore_raw),
            "status_label": status_label,
            "status_tag": badge_text,
            "note": note,
            "handled_by": handled_by,
        })

    return ngjarjet


def _parse_data_ore(raw: str) -> str:
    """'03/09/2026 12:43:55' -> ISO 8601 me offset Europe/Tirane (+02:00 ne vere)."""
    dt = datetime.strptime(raw, "%d/%m/%Y %H:%M:%S")
    dt = dt.replace(tzinfo=timezone(timedelta(hours=2)))  # DST: +1 dimer, +2 vere
    return dt.isoformat()


def push_to_supabase(order_number: str, barcode: str, events: list):
    """Upsert ne public.tracking_events permes REST API-t (service_role key)."""
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    rows = [
        {
            "order_number": order_number,
            "barcode": barcode,
            "event_time": e["event_time"],
            "status_label": e["status_label"],
            "status_tag": e.get("status_tag"),
            "note": e.get("note"),
            "handled_by": e.get("handled_by"),
        }
        for e in events
    ]
    if not rows:
        return

    resp = requests.post(
        f"{supabase_url}/rest/v1/tracking_events",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        params={"on_conflict": "order_number,event_time,status_label"},
        json=rows,
        timeout=20,
    )
    resp.raise_for_status()


def fetch_orders_to_sync() -> list:
    """
    Lexon nga Supabase tabelen 'orders_to_track' -- kthen numrat e porosive
    ende AKTIVE (active = true), qe skripti duhet t'i kontrolloje kete here.
    Perdoret vetem kur skripti xhirohet PA argumente (mënyra automatike,
    p.sh. GitHub Actions).
    """
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    resp = requests.get(
        f"{supabase_url}/rest/v1/orders_to_track",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
        },
        params={"active": "is.true", "select": "order_number"},
        timeout=20,
    )
    resp.raise_for_status()
    return [row["order_number"] for row in resp.json()]


def mark_order_status(order_number: str, *, delivered: bool):
    """
    Perditeson 'orders_to_track' pas nje sync-i te suksesshem: gjithnje
    ruan last_synced_at, dhe nese porosia eshte "Dorezuar" e vendos
    active=false, qe skripti te mos e rikontrolloje me pas kot.
    """
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    body = {"last_synced_at": datetime.now(timezone.utc).isoformat()}
    if delivered:
        body["active"] = False

    resp = requests.patch(
        f"{supabase_url}/rest/v1/orders_to_track",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        params={"order_number": f"eq.{order_number}"},
        json=body,
        timeout=20,
    )
    resp.raise_for_status()


def _eshte_dorezuar(events: list) -> bool:
    """Ngjarja me e fundit (kronologjikisht) tregon 'Dorezuar'?"""
    if not events:
        return False
    fundit = max(events, key=lambda e: e["event_time"])
    return "dorëzuar" in (fundit["status_label"] or "").lower() or \
           "dorezuar" in (fundit["status_label"] or "").lower()


def sync_one_order(order_number: str, driver=None):
    """Login (nese s'ka driver gati) -> gjen porosine -> nxjerr -> ruaj ne Supabase."""
    own_driver = driver is None
    if own_driver:
        driver = login_to_ultra(
            username=os.environ["ULTRA_USERNAME"],
            password=os.environ["ULTRA_PASSWORD"],
        )
    try:
        barcode = find_and_open_parcel_by_order_number(driver, order_number)
        events = get_tracking_events(driver)
        push_to_supabase(order_number, barcode, events)
        return events
    finally:
        if own_driver:
            driver.quit()


if __name__ == "__main__":
    numrat = sys.argv[1:]

    if not numrat:
        # Menyra AUTOMATIKE (p.sh. GitHub Actions): lexo vete listen e
        # porosive aktive nga Supabase, ne vend qe te priten argumente.
        print("Pa argumente -- duke lexuar porosite aktive nga 'orders_to_track'...")
        numrat = fetch_orders_to_sync()
        if not numrat:
            print("Asnje porosi aktive per t'u sinkronizuar. Mbarova.")
            sys.exit(0)
        print(f"U gjeten {len(numrat)} porosi aktive: {', '.join(numrat)}")
        auto_mode = True
    else:
        auto_mode = False

    driver = login_to_ultra(
        username=os.environ["ULTRA_USERNAME"],
        password=os.environ["ULTRA_PASSWORD"],
    )
    try:
        for numer in numrat:
            try:
                ngjarjet = sync_one_order(numer, driver=driver)
                print(f"Porosia {numer}: {len(ngjarjet)} ngjarje u sinkronizuan.")
                if auto_mode:
                    mark_order_status(numer, delivered=_eshte_dorezuar(ngjarjet))
            except TimeoutException:
                print(f"Porosia {numer}: NUK U GJET ose faqja nuk u ngarkua (timeout).")
    finally:
        driver.quit()
