# -*- coding: utf-8 -*-
"""
ultra_portal_scrape.py
-----------------------
KY SKEDAR DUHET PERSHTATUR NGA JU (ose me ndihmen time, nese me sillni
detaje konkrete te portalit te biznesit te Ultra Post - shiko fund te
skedarit). Eshte i ndertuar ne te njejtin stil si merge_config.py qe e
keni tashme ne projekt.

Pse? Sepse une nuk kam pare kurre faqen reale te portalit te biznesit te
Ultra Post (u-cep.com/businesses-portal) - kerkon login qe une NUK mund ta
bej vete (rregull sigurie: nuk fus fjalekalime askund). Duhet te logoheni
JU vete ne Chrome, te hapni nje pako konkrete, dhe te me tregoni si duket
HTML-i i seksionit "Gjurmimi" (View Page Source, ose me thoni ID/class e
elementeve pas Inspect).

QELLIMI I KETIJ SKEDARI:
  1) login_to_ultra(...)        -> hap Chrome, ben login ne portalin e
                                    biznesit, kthen "driver"
  2) get_tracking_events(...)   -> per nje kod gjurmimi, shkon tek pako
                                    perkatese dhe nxjerr VETEM linjen
                                    kohore (data, status, shenim, agjenci) -
                                    KURRE emrin, telefonin, apo vleren e
                                    klientit.
  3) push_to_supabase(...)      -> shkruan ngjarjet e nxjerra ne tabelen
                                    public.tracking_events ne Supabase
                                    (shiko supabase_schema.sql).

SI TA PLOTESONI (hap pas hapi):
  1. Instaloni varesite:
       pip install selenium webdriver-manager requests python-dotenv
  2. Hapni Chrome, shkoni tek https://u-cep.com/businesses-portal/login,
     hyni me llogarine e biznesit te SNEP.
  3. Shkoni tek nje pako konkrete (nje qe e keni testuar dhe e njihni
     statusin), dhe gjeni faqen qe shfaq "Gjurmimi" (screenshot qe me
     dhate ka fusha: date/ore, status, badge, shenim, agjenci).
  4. Shtypni F12 -> Elements -> gjeni kontejnerin qe permban gjithe
     listen e ngjarjeve (zakonisht nje <div> ose <ul> qe perseritet per
     çdo rresht). Kliku djathtas -> Copy -> Copy element (ose me thoni
     thjesht ID/class-in qe shihni).
  5. Plotesoni URL_LOGIN, URL_PAKETE (me nje placeholder per kodin), dhe
     selektoret CSS/XPath poshte.
  6. Vendosni kredencialet DHE çelesat e Supabase si environment
     variables (ASNJEHERE direkt ne kod / ne git):
       export ULTRA_USERNAME="..."
       export ULTRA_PASSWORD="..."
       export SUPABASE_URL="https://xxxx.supabase.co"
       export SUPABASE_SERVICE_ROLE_KEY="..."   # jo "anon" key! kjo eshte
                                                  # çelesi i fshehte i backend-it

Nese doni qe une ta plotesoj plotesisht kete skedar, me sillni ne bisede:
(a) URL-ne e sakte te faqes se nje pakoje ne portal, (b) HTML-in e
seksionit "Gjurmimi" (View Page Source ose Copy element), ose (c) thjesht
ID/class-et e elementeve pasi te beni Inspect. Pa keto, do te mbetet
vetem si skelet (template) - ashtu si eshte edhe merge_config.py sot.
"""

import os
import sys
from datetime import datetime, timezone

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ------------------------------------------------------------------
# 1) PERSHTATNI KETU: emrat/ID-te e fushave ne faqen e LOGIN-IT
# ------------------------------------------------------------------
URL_LOGIN = "https://u-cep.com/businesses-portal/login"
ID_FUSHA_PERDORUESI = "VENDOSNI_KETU_id_ose_name_te_fushes_username"
ID_FUSHA_FJALEKALIMI = "VENDOSNI_KETU_id_ose_name_te_fushes_password"
ID_BUTONI_HYR = "VENDOSNI_KETU_id_ose_name_te_butonit_login"

# ------------------------------------------------------------------
# 2) PERSHTATNI KETU: faqja e nje pakoje konkrete + selektoret e
#    seksionit "Gjurmimi" (linja kohore me ngjarje)
# ------------------------------------------------------------------
# Perdorni {code} si placeholder per kodin e gjurmimit, p.sh.:
#   "https://u-cep.com/businesses-portal/shipments/{code}"
URL_PAKETE_TEMPLATE = "VENDOSNI_KETU_URL_shabllon_me_{code}"

# Selektori qe permban TE GJITHA rreshtat e "Gjurmimit" (nje per çdo
# ngjarje: date/ore, status, badge, shenim, agjenci)
SELEKTOR_RRESHTAT_GJURMIMI = "VENDOSNI_KETU_selektor_css_te_rreshtave"
# Brenda çdo rreshti, selektoret relative per fushat individuale:
SELEKTOR_DATE_ORE = "VENDOSNI_KETU"
SELEKTOR_STATUS = "VENDOSNI_KETU"
SELEKTOR_BADGE = "VENDOSNI_KETU"          # p.sh. "Dorezimi Deshtoi" - mund te mos ekzistoje gjithmone
SELEKTOR_SHENIM = "VENDOSNI_KETU"          # p.sh. "Nuk i shkon thirrja" - mund te mos ekzistoje
SELEKTOR_AGJENCIA = "VENDOSNI_KETU"        # p.sh. "Agjencia Ultra Elbasan - Korrier Agjencie"


def login_to_ultra(username: str, password: str):
    """
    Hap Chrome, shkon tek URL_LOGIN, plotson username/password, kliko hyr.
    Kthen 'driver'-in, per t'u perdorur pastaj per çdo pako.
    """
    if "VENDOSNI_KETU" in ID_FUSHA_PERDORUESI:
        raise RuntimeError(
            "ultra_portal_scrape.py nuk eshte plotesuar ende. Shikoni "
            "udhezimet ne krye te skedarit."
        )

    options = webdriver.ChromeOptions()
    # Per te punuar pa dritare (p.sh. ne server): options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)
    driver.get(URL_LOGIN)

    wait = WebDriverWait(driver, 15)
    wait.until(EC.presence_of_element_located((By.ID, ID_FUSHA_PERDORUESI))).send_keys(username)
    driver.find_element(By.ID, ID_FUSHA_FJALEKALIMI).send_keys(password)
    driver.find_element(By.ID, ID_BUTONI_HYR).click()

    return driver


def get_tracking_events(driver, order_code: str):
    """
    Shkon tek faqja e pakos me kodin 'order_code' dhe nxjerr VETEM linjen
    kohore te gjurmimit. Kthen nje liste fjalorësh, p.sh.:

      [
        {
          "event_time": "2026-08-31T10:10:48+02:00",
          "status_label": "Ne Pritje",
          "status_tag": "Dorezimi Deshtoi",
          "note": "Nuk i shkon thirrja",
          "handled_by": "Agjencia Ultra Elbasan - Korrier Agjencie",
        },
        ...
      ]

    KURRE nuk nxjerr emrin e klientit, telefonin, apo vleren e pakos -
    ato fusha nuk duhet as te lexohen nga kjo funksion.
    """
    if "VENDOSNI_KETU" in URL_PAKETE_TEMPLATE:
        raise RuntimeError("Faqja e pakos nuk eshte konfiguruar ne ultra_portal_scrape.py")

    wait = WebDriverWait(driver, 15)
    driver.get(URL_PAKETE_TEMPLATE.format(code=order_code))

    rreshtat = wait.until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, SELEKTOR_RRESHTAT_GJURMIMI))
    )

    ngjarjet = []
    for rresht in rreshtat:
        def _text_or_none(selector):
            try:
                return rresht.find_element(By.CSS_SELECTOR, selector).text.strip() or None
            except Exception:
                return None

        date_ore_raw = _text_or_none(SELEKTOR_DATE_ORE)
        status_label = _text_or_none(SELEKTOR_STATUS)
        if not date_ore_raw or not status_label:
            continue  # rresht bosh/pa kuptim, kapërce

        ngjarjet.append({
            # PERSHTATNI parsimin e dates sipas formatit real (p.sh. "31/08/2026 10:10:48")
            "event_time": _parse_data_ore(date_ore_raw),
            "status_label": status_label,
            "status_tag": _text_or_none(SELEKTOR_BADGE),
            "note": _text_or_none(SELEKTOR_SHENIM),
            "handled_by": _text_or_none(SELEKTOR_AGJENCIA),
        })

    return ngjarjet


def _parse_data_ore(raw: str) -> str:
    """Kthen nje string date/ore ne format ISO 8601. PERSHTATNI formatin
    sipas asaj qe shfaq portali (shembulli ketu supozon 'dd/mm/YYYY HH:MM:SS')."""
    dt = datetime.strptime(raw, "%d/%m/%Y %H:%M:%S")
    # Ultra Post shfaq oren lokale (Europe/Tirane, UTC+2 ne vere).
    # Pershtateni offset-in nese e nevojshme, ose perdorni nje libreri
    # si 'zoneinfo' per DST te sakte.
    from datetime import timedelta
    dt = dt.replace(tzinfo=timezone(timedelta(hours=2)))
    return dt.isoformat()


def push_to_supabase(order_code: str, events: list):
    """
    Shkruan (upsert) ngjarjet e nxjerra ne tabelen public.tracking_events
    ne Supabase, permes REST API-t (PostgREST). Perdor SUPABASE_SERVICE_ROLE_KEY
    (jo "anon" key) sepse RLS e tabeles nuk lejon shkrim nga anon.
    """
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    rows = [
        {
            "order_code": order_code,
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
        params={"on_conflict": "order_code,event_time,status_label"},
        json=rows,
        timeout=20,
    )
    resp.raise_for_status()


def sync_one_order(order_code: str, driver=None):
    """Rrugëz e shkurtër: login (nese s'ka driver gati) -> nxjerr -> ruaj ne Supabase."""
    own_driver = driver is None
    if own_driver:
        driver = login_to_ultra(
            username=os.environ["ULTRA_USERNAME"],
            password=os.environ["ULTRA_PASSWORD"],
        )
    try:
        events = get_tracking_events(driver, order_code)
        push_to_supabase(order_code, events)
        return events
    finally:
        if own_driver:
            driver.quit()


if __name__ == "__main__":
    # Perdorim: python ultra_portal_scrape.py UP2026000451 [kod2 kod3 ...]
    kodet = sys.argv[1:]
    if not kodet:
        print("Perdorim: python ultra_portal_scrape.py KOD1 [KOD2 ...]")
        sys.exit(1)

    driver = login_to_ultra(
        username=os.environ["ULTRA_USERNAME"],
        password=os.environ["ULTRA_PASSWORD"],
    )
    try:
        for kod in kodet:
            ngjarjet = sync_one_order(kod, driver=driver)
            print(f"{kod}: {len(ngjarjet)} ngjarje u sinkronizuan.")
    finally:
        driver.quit()
