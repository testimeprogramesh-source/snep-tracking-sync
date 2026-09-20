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
import re
import sys
import time
from datetime import datetime, timezone, timedelta

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementNotInteractableException,
    StaleElementReferenceException,
)


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
SELEKTOR_PAKO_DETAJE = "span.view-parcel-details"          # badge-i i barkodit -- hap detajet e pakos (AJAX, jo <a>)

# ------------------------------------------------------------------
# 2b) SKANIMI AUTOMATIK I TE GJITHA PAKOVE (pa listë manuale porosish) --
#     VERIFIKUAR nga HTML-i real i portalit (paging jQuery DataTables
#     standarde): #parcels_datatable_length (madhesia e faqes),
#     #parcels_datatable_next (faqja tjeter), #parcels_datatable tbody tr
#     (rreshtat). Butoni "Mbyll" u konfirmua nga nje foto ekrani reale.
# ------------------------------------------------------------------
SELEKTOR_GJATESIA_FAQES = "select[name='parcels_datatable_length']"
ID_BUTONI_FAQJA_TJETER = "parcels_datatable_next"
SELEKTOR_RRESHT_TABELE = "#parcels_datatable tbody tr"
SELEKTOR_BUTONI_MBYLL_DETAJET = (
    "//button[contains(normalize-space(.), 'Mbyll')] | //a[contains(normalize-space(.), 'Mbyll')]"
)
MAX_FAQE_SKANIM = 150       # kufi sigurie -- s'kapërcejmë kurrë kaq shumë faqe (mbrojtje kundër loop-esh të pafundme)
STREAK_NDALO_SKANIMIN = 50  # ne skanim JO te plote: ndalo pasi te hasesh kaq rreshta rradhazi tashme te njohur/te mbyllur/te pandryshuar

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


def _ruaj_debug(driver, tag: str):
    """
    Ruan nje foto ekrani (.png) dhe HTML-in e faqes (.html) ne dosjen
    'debug/', per t'u perdorur si diagnostikim kur nje hap deshton.
    Workflow-i i GitHub Actions i ngarkon keto si "artifact" te
    shkarkueshem, edhe kur i gjithe xhirimi "duket" i suksesshem.
    Kjo eshte "best-effort" -- nese vete ruajtja deshton, s'e rrezon
    procesin kryesor.
    """
    try:
        os.makedirs("debug", exist_ok=True)
        driver.save_screenshot(f"debug/{tag}.png")
        with open(f"debug/{tag}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"  (u ruajt diagnostikimi: debug/{tag}.png dhe debug/{tag}.html)")
    except Exception as e:
        print(f"  (s'u ruajt dot diagnostikimi: {e})")


def login_to_ultra(username: str, password: str, headless: bool = True):
    """Hap Chrome, logohet ne portalin e biznesit te Ultra Post. Kthen 'driver'."""
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,1000")
    driver = webdriver.Chrome(options=options)

    driver.get(URL_LOGIN)
    wait = WebDriverWait(driver, 20)
    try:
        wait.until(EC.presence_of_element_located((By.NAME, ID_FUSHA_PERDORUESI))).send_keys(username)
        driver.find_element(By.NAME, ID_FUSHA_FJALEKALIMI).send_keys(password)
        driver.find_element(By.CSS_SELECTOR, SELEKTOR_BUTONI_HYR).click()

        # prisni te mbarrojme ne /dashboard (shenje qe login-i funksionoi)
        wait.until(EC.url_contains("/businesses-portal/dashboard"))
    except TimeoutException:
        print("  -> DESHTOI: login-i s'perfundoi (fusha e login-it ose /dashboard).")
        _ruaj_debug(driver, "00_login_deshtoi")
        raise
    return driver


def find_and_open_parcel_by_order_number(driver, order_number: str):
    """
    Shkon tek lista e pakove, hap panelin "Filtër", kerkon numrin e
    porosise tek "Numri Faturës", dhe klikon rreshtin e vetem qe rezulton
    per te hapur faqen/modalin e pakos. Kthen barkodin SN te gjetur
    (per referencen tuaj -- ruhet ne kolonen "barcode", jo ne ate publike).

    Cdo hap kryesor eshte i ndare me try/except + print, qe nese dickafton
    (p.sh. TimeoutException), te dime SAKTESISHT ne cilin hap ka ndodhur --
    dhe ruhet nje "foto ekrani" + HTML per diagnostikim (shih _ruaj_debug).
    """
    wait = WebDriverWait(driver, 25)
    driver.get(URL_LISTA_PAKOVE)

    # --- Hapi 1: hap panelin "Filtër" (i mbyllur si default) -----------
    # Perdorim XPath qe kerkon tekstin "Filt" brenda butonit, jo thjesht
    # "button.accordion-button" (qe mund te kete disa te tilla ne faqe, dhe
    # klikimi i te parit te gjetur mund te mos jete ai i "Filtrit").
    try:
        accordion = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(@class,'accordion-button') and contains(., 'Filt')]")
        ))
        accordion.click()
    except TimeoutException:
        print("  -> DESHTOI: s'u gjet/klikua butoni 'Filtër' (accordion).")
        _ruaj_debug(driver, f"{order_number}_01_pa_filter")
        raise

    # --- Hapi 2: shkruaj numrin e porosise tek "Numri Faturës" ---------
    # panelli hapet me nje animacion (CSS transition) -- "presence" vetem
    # kontrollon qe eshte ne DOM, jo qe eshte i klikueshem/shkruajshem akoma,
    # prandaj presim "clickable" (dukshmeri + i aktivizuar), plus nje pauze
    # te vogel shtese per vete animacionin, me disa prova rezervë (retry).
    try:
        fusha = wait.until(EC.element_to_be_clickable((By.ID, ID_FUSHA_NUMER_POROSIE)))
        time.sleep(0.6)

        for perpjekje in range(4):
            try:
                fusha.clear()
                fusha.send_keys(order_number)
                break
            except (ElementNotInteractableException, StaleElementReferenceException):
                time.sleep(0.6)
                fusha = wait.until(EC.element_to_be_clickable((By.ID, ID_FUSHA_NUMER_POROSIE)))
        else:
            fusha.clear()
            fusha.send_keys(order_number)
    except TimeoutException:
        print("  -> DESHTOI: s'u gjet fusha 'Numri Faturës' (filter_invoice_number).")
        _ruaj_debug(driver, f"{order_number}_02_pa_fushe")
        raise

    # --- Hapi 3: kliko "Apliko filtrin" ---------------------------------
    try:
        driver.find_element(By.ID, ID_BUTONI_APLIKO_FILTER).click()
    except NoSuchElementException:
        print("  -> DESHTOI: s'u gjet butoni 'Apliko filtrin' (apply_filter_button).")
        _ruaj_debug(driver, f"{order_number}_03_pa_buton_filter")
        raise

    # --- Hapi 4: prit rezultatin (1 rresht, badge-i i barkodit) ---------
    # ZBULUAR nga diagnostikimi (20/09/2026): rreshti i rezultatit NUK ka
    # asnje <a> qe te "hape" pakon -- e vetmja <a> ne rresht eshte
    # "tel:+355..." (numri i telefonit te marresit)! Barkodi eshte nje
    # <span class="badge ... view-parcel-details" data-id="..."> qe hap
    # detajet e pakos permes nje click-handler JS (jQuery) + AJAX -- s'ka
    # fare navigim URL-je. Skripti i vjeter po klikonte gabimisht linkun
    # "tel:", qe s'ben asgje ne Chrome headless -- prandaj s'ngarkohej kurre
    # seksioni "Gjurmimi".
    def _gjej_pako(d):
        elems = d.find_elements(By.CSS_SELECTOR, SELEKTOR_PAKO_DETAJE)
        return elems[0] if elems else False

    try:
        pako_span = wait.until(_gjej_pako)
    except TimeoutException:
        print(f"  -> DESHTOI: filtri s'ktheu asnje rezultat per porosine {order_number}.")
        _ruaj_debug(driver, f"{order_number}_04_pa_rezultat")
        raise

    barcode_gjetur = pako_span.text.strip()
    pako_span.click()

    # --- Hapi 5: prit te ngarkohet seksioni "Gjurmimi" ------------------
    # Klikimi mesiper nis 1-2 thirrje AJAX (detajet e pakos, pastaj
    # historia/Gjurmimi) -- prandaj presim qe seksioni te mbushet me
    # te dhena reale (jo thjesht te ekzistoje bosh ne DOM).
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SEL_RRESHTAT)))
    except TimeoutException:
        print("  -> DESHTOI: pas klikimit te rezultatit, s'u shfaq seksioni 'Gjurmimi'.")
        _ruaj_debug(driver, f"{order_number}_05_pa_gjurmim")
        raise

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

    rows_by_kyc = {}
    for e in events:
        rresht = {
            "order_number": order_number,
            "barcode": barcode,
            "event_time": e["event_time"],
            "status_label": e["status_label"],
            "status_tag": e.get("status_tag"),
            "note": e.get("note"),
            "handled_by": e.get("handled_by"),
        }
        # Postgres hedh gabim ("ON CONFLICT DO UPDATE command cannot affect
        # row a second time" -> shfaqet si 500 nga PostgREST) nese i njejti
        # (order_number, event_time, status_label) shfaqet 2+ here NE TE
        # NJEJTIN xhirim upsert -- p.sh. nese Ultra Post kthen te njejtin
        # "history item" 2 here (faqosje/duplikim). Prandaj i shpertheme
        # rreshtat sipas ketij celesi PARA se t'i dergojme -- mbajme te
        # fundit, qe eshte praktikisht identik gjithsesi.
        kyc = (rresht["order_number"], rresht["event_time"], rresht["status_label"])
        rows_by_kyc[kyc] = rresht

    rows = list(rows_by_kyc.values())
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
    if not resp.ok:
        # Ruajme trupin e pergjigjes (mesazhi i sakte i gabimit nga Postgres/
        # PostgREST) qe te shfaqet ne log -- pa kete, "500 Internal Server
        # Error" vetem s'na thote pse.
        print(f"  -> Supabase ktheu {resp.status_code}: {resp.text}")
    resp.raise_for_status()


def _lexo_numrin_e_porosise(driver) -> str:
    """
    Lexon numrin e porosisë (Numri Faturës) nga paneli i HAPUR i detajeve
    të pakos -- perdoret VETEM ne skanimin automatik te te gjitha pakove,
    ku s'e dime paraprakisht numrin (ndryshe nga menyra me filter, ku e
    kerkojme vete).

    E VERIFIKUAR nga nje foto ekrani reale (20/09/2026): fusha "Numri
    Faturës" ndonjehere permban 2 numra te ndare me hapesire (p.sh.
    "3818985 227125581789661533") -- i pari eshte numri i vertete i
    porosise se SNEP. Per te qene te fortë ndaj ndryshimeve te vogla te
    HTML-it (s'kemi nje selektor CSS te konfirmuar per kete fushe), e
    nxjerrim me regex nga i gjithe teksti i faqes, jo nga nje element i
    caktuar. Rezervë: fusha "Shënimet" e formatit "Order #1234567".
    """
    teksti = driver.find_element(By.TAG_NAME, "body").text
    m = re.search(r"Numri\s+Fatur[ëe]s\s*:?\s*(\d+)", teksti, re.IGNORECASE)
    if not m:
        m = re.search(r"Order\s*#\s*(\d+)", teksti)
    return m.group(1) if m else ""


def _mbyll_detajet_pakos(driver):
    """Mbyll panelin e detajeve te pakos (buton 'Mbyll'), per t'u kthyer te lista."""
    try:
        mbyll = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.XPATH, SELEKTOR_BUTONI_MBYLL_DETAJET))
        )
        mbyll.click()
        time.sleep(0.4)
    except TimeoutException:
        print("  (kujdes: s'u gjet dot butoni 'Mbyll' -- vazhdoj gjithsesi)")
    _pastro_panelin_e_detajeve(driver)
    _detyro_mbylljen_e_sirtarit(driver)


def _detyro_mbylljen_e_sirtarit(driver):
    """
    RREGULLIM I RENDESISHEM (20/09/2026): "rrjete sigurie".

    ZBULUAR: paneli i detajeve eshte nje "sirtar" (drawer, Metronic) qe kur
    hapet shton nje mbivendosje `<div class="drawer-overlay">` mbi gjithe
    faqen. Kur butoni "Mbyll" DESHTON te klikohet (p.sh. pak sekonda vonese
    ne renderim), kjo mbivendosje MBETET aty -- e padukshme por PREK ende
    klikimet -- dhe klikimi i pakos TJETER deshton me
    "ElementClickInterceptedException: ... Other element would receive the
    click: <div class="drawer-overlay">".

    Prandaj, PAVARESISHT nese "Mbyll" u klikua apo jo, hjekim me force cdo
    mbivendosje `.drawer-overlay` dhe cdo klase "drawer-on" (qe e mban
    sirtarin te "hapur" ne CSS) permes JavaScript -- kjo garanton qe faqja
    kthehet gjithmone ne gjendje te klikueshme para se te vazhdojme.
    """
    try:
        driver.execute_script(
            "document.querySelectorAll('.drawer-overlay').forEach(function(e){e.remove();});"
            "document.querySelectorAll('.drawer-on').forEach(function(e){e.classList.remove('drawer-on');});"
        )
    except Exception:
        pass


def _prit_ngarkimin_e_listes(driver, wait, rresht_i_vjeter=None):
    """
    RREGULLIM I RENDESISHEM (20/09/2026): pret qe DataTables te perfundoje
    VERTET ngarkimin AJAX te rreshtave (pas ndryshimit te madhesise se
    faqes ose klikimit "faqja tjeter"), ne vend te nje `time.sleep()` fiks.

    ZBULUAR (20/09/2026): pauza fikse (1.2-1.5 sek) ishte SHUME e shkurter
    -- DataTables e ngarkon listen me AJAX, dhe skripti i lexonte rreshtat
    PARA se te mbaronte ngarkimi, duke "pare" 0 rreshta dhe duke raportuar
    "U sinkronizuan 0 pako" edhe pse ne fakt kishte qindra pako ne portal.

    Nese jepet `rresht_i_vjeter` (nje element <tr> nga PARA veprimit), presim
    FIRST qe te behet "stale" (d.m.th. DataTables e ka hequr/zevendesuar
    vertet DOM-in e vjeter) -- kjo shmang nje bug te ngjashem me ate te
    panelit te detajeve, ku nje kontroll "presence_of_element_located" mund
    te plotesohet menjehere nga rreshtat E VJETER qe ende s'jane zevendesuar.
    """
    if rresht_i_vjeter is not None:
        try:
            wait.until(EC.staleness_of(rresht_i_vjeter))
        except TimeoutException:
            pass
    try:
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, f"{SELEKTOR_RRESHT_TABELE} {SELEKTOR_PAKO_DETAJE}")
        ))
    except TimeoutException:
        pass  # normale nese s'ka fare pako ne kete faqe/filtrim
    time.sleep(0.3)  # nje pauze e vogel shtese, per stabilitet te DOM-it


def _pastro_panelin_e_detajeve(driver):
    """
    RREGULLIM I RENDESISHEM (20/09/2026): pastron plotesisht panelin e
    detajeve te pakos (#parcel-details-wrapper) PARA se te hapim nje pako
    te re.

    Pa kete, u zbulua nje bug real: nese permbajtja e VJETER (nga pakoja e
    kaluar) mbetet ende ne DOM kur klikojme pakon TJETER, `wait.until(...)`
    per seksionin "Gjurmimi" mund te PLOTESOHET MENJEHERE nga elementet e
    VJETRA (qe jane ende ne DOM, thjesht te fshehura), PARA se AJAX-i i ri
    te kete mbaruar -- duke shkaktuar qe numri i porosise/ngjarjet e nje
    pakoje t'i "ngjiten" gabimisht nje pakoje tjeter (rreshta te gabuar ne
    Supabase). Duke e zbrazur vete `innerHTML`-in ketu (permes JS), garantojme
    qe "wait.until" te mos plotesohet kurre nga permbajtja e vjeter.
    """
    try:
        driver.execute_script(
            "var w = document.getElementById('parcel-details-wrapper'); if (w) { w.innerHTML = ''; }"
        )
    except Exception:
        pass


def fetch_seen_parcels() -> dict:
    """
    Lexon nga Supabase tabelen 'ultra_parcels_seen' -- kthen nje dictionary
    {barcode: {"order_number":..., "list_updated_raw":..., "active":...}}
    per te ditur SHPEJT (pa hapur çdo pako) cilat pako i njohim tashme dhe
    s'kane ndryshuar qe nga hera e fundit.
    """
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    resp = requests.get(
        f"{supabase_url}/rest/v1/ultra_parcels_seen",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
        },
        params={"select": "barcode,order_number,list_updated_raw,active"},
        timeout=30,
    )
    resp.raise_for_status()
    return {row["barcode"]: row for row in resp.json()}


def upsert_seen_parcel(barcode: str, order_number: str, list_updated_raw: str, active: bool):
    """Upsert 1 rresht ne 'ultra_parcels_seen' (gjendja e brendshme e skanimit)."""
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    resp = requests.post(
        f"{supabase_url}/rest/v1/ultra_parcels_seen",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        params={"on_conflict": "barcode"},
        json=[{
            "barcode": barcode,
            "order_number": order_number,
            "list_updated_raw": list_updated_raw,
            "active": active,
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
        }],
        timeout=20,
    )
    if not resp.ok:
        print(f"  -> Supabase (ultra_parcels_seen) ktheu {resp.status_code}: {resp.text}")
    resp.raise_for_status()


def scan_all_parcels(driver, full_scan: bool = False) -> list:
    """
    Shkon te lista e PLOTE e pakove (pa filtruar me numer porosie te
    caktuar), e ven madhesine e faqes ne maksimum, dhe kalon faqe pas
    faqeje (nga me te rejat tek me te vjetrat, sipas renditjes se
    default-it te portalit). Per çdo pako:
      - Nese eshte E RE (s'e kemi pare kurre) OSE ka NDRYSHUAR ("Koha e
        Perditesimit" ndryshon nga hera e fundit qe e pame) -> hapim
        detajet, lexojme numrin e porosise, nxjerrim Gjurmimin e plote,
        dhe e ruajme (upsert) ne Supabase.
      - Perndryshe (tashme e njohur, e pandryshuar, dhe e "mbyllur" --
        d.m.th. tashme e dorezuar) -> e anashkalojme pa e hapur (kursen
        kohe -- s'ka nevoje ta rikontrollojme diçka qe s'ka ndryshuar).

    Ne menyren "full_scan=True" (skanim i plote, 1 here ne dite), s'ndalon
    kurre me pare per "streak" -- kalon te GJITHA faqet (deri ne kufirin
    e sigurise MAX_FAQE_SKANIM), per te kapur çdo pako qe menyra e shpejte
    mund ta kete "harruar" (p.sh. nje pako shume e vjeter qe befas ndryshon).

    Kthen listen e (order_number, barcode, events) per çdo pako qe u
    sinkronizua realisht kete here (jo ato qe u anashkaluan).
    """
    seen = fetch_seen_parcels()
    rezultatet = []
    wait = WebDriverWait(driver, 25)

    driver.get(URL_LISTA_PAKOVE)

    # vendos madhesine e faqes ne maksimum, per te reduktuar numrin e faqeve
    try:
        gjatesia = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELEKTOR_GJATESIA_FAQES)))
        rresht_i_vjeter = None
        try:
            rresht_i_vjeter = driver.find_element(By.CSS_SELECTOR, SELEKTOR_RRESHT_TABELE)
        except NoSuchElementException:
            pass
        Select(gjatesia).select_by_value("300")
        _prit_ngarkimin_e_listes(driver, wait, rresht_i_vjeter)
    except Exception as e:
        print(f"  (kujdes: s'u vendos dot madhesia maksimale e faqes -- {e})")

    streak_te_panevojshme = 0
    faqe_nr = 1

    while True:
        rreshtat = driver.find_elements(By.CSS_SELECTOR, SELEKTOR_RRESHT_TABELE)
        for rresht in rreshtat:
            try:
                badge = rresht.find_element(By.CSS_SELECTOR, SELEKTOR_PAKO_DETAJE)
            except NoSuchElementException:
                continue  # rresht placeholder ("Nuk u gjet asnje rezultat", etj.)

            barcode = badge.text.strip()
            if not barcode:
                continue

            try:
                badges_koha = rresht.find_elements(By.CSS_SELECTOR, "td:nth-child(6) .badge")
                koha_perditesuar = badges_koha[-1].text.strip() if badges_koha else ""
            except Exception:
                koha_perditesuar = ""

            e_njohur = seen.get(barcode)
            e_mbyllur_e_panryshuar = (
                e_njohur is not None
                and e_njohur.get("active") is False
                and e_njohur.get("list_updated_raw") == koha_perditesuar
            )

            if e_mbyllur_e_panryshuar:
                if not full_scan:
                    streak_te_panevojshme += 1
                continue

            streak_te_panevojshme = 0

            # duhet ta hapim -- pastro cdo permbajtje te vjeter TE MBETUR ne
            # panel PARA klikimit (shih shenimin te _pastro_panelin_e_detajeve),
            # pastaj klikojme badge-in dhe presim ngarkimin e Gjurmimit TE RI
            _pastro_panelin_e_detajeve(driver)
            _detyro_mbylljen_e_sirtarit(driver)
            try:
                badge.click()
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SEL_RRESHTAT)))
            except TimeoutException:
                print(f"  -> DESHTOI: pako {barcode} s'e shfaqi Gjurmimin pas klikimit.")
                _ruaj_debug(driver, f"skan_{barcode}_pa_gjurmim")
                _mbyll_detajet_pakos(driver)
                continue

            numer_porosie = _lexo_numrin_e_porosise(driver)
            if not numer_porosie:
                print(f"  -> KUJDES: pako {barcode} s'ka numer porosie te lexueshem -- anashkalohet.")
                _ruaj_debug(driver, f"skan_{barcode}_pa_numer_porosie")
                _mbyll_detajet_pakos(driver)
                continue

            ngjarjet = get_tracking_events(driver)
            eshte_dorezuar = _eshte_dorezuar(ngjarjet)

            push_to_supabase(numer_porosie, barcode, ngjarjet)
            upsert_seen_parcel(barcode, numer_porosie, koha_perditesuar, active=not eshte_dorezuar)
            seen[barcode] = {"order_number": numer_porosie, "list_updated_raw": koha_perditesuar, "active": not eshte_dorezuar}
            rezultatet.append((numer_porosie, barcode, ngjarjet))
            print(f"  Pako {barcode} (porosia {numer_porosie}): {len(ngjarjet)} ngjarje u sinkronizuan.")

            _mbyll_detajet_pakos(driver)

        if not full_scan and streak_te_panevojshme >= STREAK_NDALO_SKANIMIN:
            print(f"  (u ndal skanimi -- {streak_te_panevojshme} pako rradhazi tashme te sinkronizuara e te mbyllura)")
            break

        faqe_nr += 1
        if faqe_nr > MAX_FAQE_SKANIM:
            print(f"  (u arrit kufiri i sigurise prej {MAX_FAQE_SKANIM} faqesh -- ndalojme per kete here)")
            break

        try:
            next_li = driver.find_element(By.ID, ID_BUTONI_FAQJA_TJETER)
            if "disabled" in (next_li.get_attribute("class") or ""):
                break  # s'ka faqe tjeter -- arritem ne fund te listes
            rresht_i_vjeter = None
            try:
                rresht_i_vjeter = driver.find_element(By.CSS_SELECTOR, SELEKTOR_RRESHT_TABELE)
            except NoSuchElementException:
                pass
            next_li.find_element(By.TAG_NAME, "a").click()
            _prit_ngarkimin_e_listes(driver, wait, rresht_i_vjeter)
        except NoSuchElementException:
            break

    return rezultatet


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

    if numrat:
        # Menyra TEST MANUAL: xhiro "python ultra_portal_scrape.py 3797608 ..."
        # per te kontrolluar 1 (ose disa) porosi te caktuara, pa prekur
        # skanimin e plote. E dobishme per debugging.
        driver = login_to_ultra(
            username=os.environ["ULTRA_USERNAME"],
            password=os.environ["ULTRA_PASSWORD"],
        )
        try:
            for numer in numrat:
                try:
                    ngjarjet = sync_one_order(numer, driver=driver)
                    print(f"Porosia {numer}: {len(ngjarjet)} ngjarje u sinkronizuan.")
                except TimeoutException:
                    print(f"Porosia {numer}: NUK U GJET ose faqja nuk u ngarkua (timeout).")
        finally:
            driver.quit()

    else:
        # Menyra AUTOMATIKE (parazgjedhur, p.sh. GitHub Actions çdo 15 min):
        # SKANON VETE te gjitha pakot e portalit -- s'ka me nevoje per listen
        # manuale "orders_to_track". Nese ndryshorja FULL_SCAN eshte vendosur
        # (p.sh. nje here ne dite), behet nje skanim i PLOTE (pa u ndalur
        # heret); ndryshe, behet skanimi i SHPEJTE (ndalon pasi te hase nje
        # numer te madh pakosh rradhazi tashme te njohura e te pandryshuara).
        full_scan = bool(os.environ.get("FULL_SCAN"))
        print(f"Duke skanuar {'TE GJITHA' if full_scan else 'vetem ndryshimet e'} pakot te portali...")

        driver = login_to_ultra(
            username=os.environ["ULTRA_USERNAME"],
            password=os.environ["ULTRA_PASSWORD"],
        )
        try:
            rezultatet = scan_all_parcels(driver, full_scan=full_scan)
        finally:
            driver.quit()

        print(f"U sinkronizuan {len(rezultatet)} pako (te reja ose te ndryshuara).")
