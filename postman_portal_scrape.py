# -*- coding: utf-8 -*-
"""
postman_portal_scrape.py
-------------------------
Skript qe lidhet me portalin e biznesit te Postman (postman-ks.com, Kosove),
kerkon nje porosi sipas "Referencës" (numri i porosise se SNEP, i njejti qe
perdoret edhe per Ultra Post), dhe nxjerr VETEM "HISTORIKUN E POROSISE"
(linja kohore: date/ore, pershkrimi i statusit, agjenti/agjencia qe e ka
trajtuar) -- KURRE emrin e blerësit, telefonin, adresen, apo vleren e pakos.

STATUSI: STRUKTURA E FAQES E VERIFIKUAR LIVE (25/09/2026), permes inspektimit
te DOM-it real ndersa perdoruesi ishte i loguar -- shih shenimet ne çdo
seksion me poshte per detaje. FUSHAT E LOGIN-IT JANE HAMENDESIM (s'mund te
shihen pa dalë nga sesioni) -- DUHET KONFIRMUAR me nje test te vetem, real,
PARA se te aktivizohet skanimi automatik i plote.

PERSE TE NJEJTIN "order_number" SI ULTRA POST:
  SNEP fut vete numrin e vet te porosise si "Referencë" kur krijon nje
  dergese te Postman -- konfirmuar nga vete perdoruesi (25/09/2026). Kjo do
  te thote qe "order_number" mbetet UNIK ne gjithe sistemin (Ultra Post +
  Postman se bashku), dhe te dyja skriptet mund te shkruajne ne TE NJEJTEN
  tabele 'tracking_events' te Supabase, thjesht te dalluara nga kolona
  "courier" ('ultra' / 'postman'). Shih supabase_schema.sql.

STRUKTURA E VERIFIKUAR E LISTES SE POROSIVE (https://postman-ks.com/order):
  - Eshte nje "grid" (AG Grid), jo nje <table> e thjeshte -- rreshtat kane
    klase "ag-row", qelizat "ag-cell" me atribut "col-id".
  - Fusha e kerkimit "Kërko tekstin" (input me placeholder te njejtin tekst)
    filtron PIKERISHT te kolona "Referenca" -- e testuar live me nje numer
    porosie real, ktheu sakte 1 rezultat.
  - Kolonat (col-id) qe na interesojne:
      "displayId"  -> Kodi i Postman-it, p.sh. "#2PD3-4385237" (numri pas
                      vizes eshte "id"-ja per URL-ne e detajeve)
      "refid"      -> Referenca / numri i porosise se SNEP (order_number)
      "statusDescription" -> statusi + emri i agjentit, te ngjitur pa
                      hapesire (p.sh. "•Në transportArdian Roka") -- shih
                      _nxirr_statusin_nga_rreshti() per shpjegim si ndahen.
  - "Kodi" (displayId) NUK eshte link/<a> -- eshte tekst i thjeshte (<p>) me
    click-handler JS te AG Grid. NE VEND TE KLIKIMIT te rreshtit, e nxjerrim
    numrin (pjesa pas vizes se "#2PD3-...") dhe SHKOJME DIREKT ne URL:
    https://postman-ks.com/order-details?id=<numri> -- shume me e qendrueshme
    se klikimi i nje rreshti brenda nje grid-i te virtualizuar.

STRUKTURA E VERIFIKUAR E FAQES SE DETAJEVE (order-details?id=...):
  - Seksioni "HISTORIKU I POROSISE" ka klase container ".orderHistory" ->
    ".orderHistoryLines", me nje <div class="... flex flex-row items-start
    gap-6..."> per çdo ngjarje.
  - Brenda çdo ngjarje: SAKTESISHT 3 elemente <p> (leaf, pa femije), ne kete
    renditje: [0]=data/ora ("24.09.2026 16:25"), [1]=pershkrimi ("Porosia u
    regjistrua"), [2]=agjenti/agjencia ("Snep ks" / "Postman KS" / emer
    korrieri). E nxjerrim me pozicion (nth), JO me klase (klasat jane
    "utility classes" te gjata/te paqendrueshme, Tailwind-style).
  - DISA ngjarje jane thjesht "log" teknik (p.sh. "Pesha u ndryshua nga 0.50
    ne 0.35...") -- s'jane te dobishme per klientin, filtrohen (shih
    _eshte_ngjarje_teknike me poshte).

SI TA PERDORNI (manualisht, per teste):
  1. pip install selenium webdriver-manager requests
  2. Vendosni si environment variables:
       export POSTMAN_USERNAME="..."
       export POSTMAN_PASSWORD="..."
       export SUPABASE_URL="https://xxxx.supabase.co"
       export SUPABASE_SERVICE_ROLE_KEY="..."
  3. Xhironi PER NJE TEST TE VETEM (rekomandohet PARA se te aktivizoni
     skanimin e plote automatik): python postman_portal_scrape.py 3828131
     (numer porosie/referencë real, per te konfirmuar qe login-i dhe
     nxjerrja e historikut funksionojne sakte).

SI XHIRON AUTOMATIKISHT (p.sh. nga GitHub Actions):
  Xhironi PA asnje argument: python postman_portal_scrape.py
  Skanon VETE te gjitha porosite e portalit (njesoj si ultra_portal_scrape.py),
  duke perdorur "postman_parcels_seen" per te anashkaluar porosi tashme te
  njohura e te pandryshuara (krahasim me STATUSIN, jo me nje date
  "Perditesuar Me" -- Postman s'e ka ate kolone ne liste).
"""

import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)


# ------------------------------------------------------------------
# 1) FAQJA E LOGIN-IT -- HAMENDESIM, DUHET KONFIRMUAR me nje test te
#    vetem real PARA se te aktivizohet skanimi automatik. S'mund te
#    shihej formulari sepse perdoruesi ishte tashme i loguar (dhe s'duam
#    ta nxjerrim nga sesioni per ta pare).
# ------------------------------------------------------------------
URL_LOGIN = "https://postman-ks.com/login"
URL_DASHBOARD_PJESE = "/dashboard"   # shenje qe login-i funksionoi

# ------------------------------------------------------------------
# 2) FAQJA E LISTES SE POROSIVE + FILTRI -- VERIFIKUAR LIVE
# ------------------------------------------------------------------
URL_LISTA_POROSIVE = "https://postman-ks.com/order"
XPATH_FUSHA_KERKIMI = "//input[@placeholder='Kërko tekstin']"
XPATH_BUTONI_FILTRO = "//button[contains(., 'Filtro')]"
SELEKTOR_RRESHT_GRID = "div.ag-row"
SELEKTOR_QELIZA = "div.ag-cell"

# ZBULUAR (25/09/2026, inspektuar live ne Chrome): faqja e listes KA nje
# filter te vertete date -- "Prej datës:" / "Deri me:" -- jo thjesht nje
# shfaqje dekorative. E testuam direkt: nga 9834 porosi GJITHSEJ (qe nga
# fillimi i sistemit), filtri i reduktoi ne VETEM 721 (per periudhen
# gusht-shtator 2026). Perdorim kete filter qe skanimi TE MOS kaloje
# gjithe historikun (9800+ porosi, shumica krejtesisht te panevojshme),
# por VETEM porosite e fundit -- shume me shpejte, dhe pikerisht ajo qe
# duhet (klienti konfirmoi: "nuk me duhen te gjitha, dua vetem gusht e
# shtator").
XPATH_FUSHAT_DATE = "//input[@placeholder='Select date']"
SEL_KALENDAR_PARA = "button.ant-picker-header-prev-btn"
DITE_PRAPA_PARAZGJEDHUR = 60  # ~2 muaj mbrapa -- kap rehat "muajin e kaluar + ky muaj";
                              # mund te ndryshohet me environment variable DITE_PRAPA_SKANIM

# ZBULUAR (25/09/2026, inspektuar live me JavaScript ne DOM-in real): AG
# Grid e VIRTUALIZON listen -- edhe kur "faqja" ka 500 rreshta (madhesia
# maksimale), ne DOM ne çdo moment gjenden VETEM rreshtat afer pjeses
# aktualisht te dukshme ne ekran (rreth 20-70 rreshta, JO te gjithe 500).
# Kjo eshte arsyeja e VERTETE PERSE nje skanim i plote kapi vetem 128
# porosi ne vend te ~721 -- shumica e rreshtave thjesht s'ishin ne DOM
# per t'u lexuar fare. Zgjidhja eshte te "scroll"-ojme VETE kontejnerin
# e grid-it (shih _mblidh_rreshtat_e_faqes_me_scroll me poshte).
SEL_GRID_VIEWPORT = "div.ag-body-viewport"

MAX_FAQE_SKANIM = 300  # (25/09/2026) rritur nga 150 -- rezerve sigurie NESE
# madhesia e faqes deshton perseri e mbetet 20 (shih shenimin tek
# _vendos_madhesine_maksimale_faqes): 300 faqe x 20 = 6000 rreshta ne vend
# te 3000. Kur madhesia eshte 500 (rasti normal), 300 faqe s'arrihen kurre
# (9834 / 500 = ~20 faqe mjaftojne), keshtu qe s'kushton kohe shtese.
STREAK_NDALO_SKANIMIN = 50
DITE_MAX_SINKRONIZIM = 30

# Statuset e MUNDSHME (te verifikuara live nga dropdown-i "Statusi") --
# perdoren per te ndare "statusDescription" (statusi + emri i agjentit, te
# ngjitur pa hapesire) ne 2 pjese te qarta.
STATUSET_E_MUNDSHME = [
    "Regjistruar",
    "Gati për grumbullim",
    "Grumbulluar",
    "Në depo",
    "Në transport",
    "Dorëzuar",
    "Refuzuar",
    "Në pritje për tërheqje",
    "Në pritje",
    "Kthyer",
]
# Statuset "PERFUNDIMTARE" -- porosia s'ka pse te rikontrollohet me pas.
STATUSET_PERFUNDIMTARE = {"Dorëzuar", "Refuzuar", "Kthyer"}

# ------------------------------------------------------------------
# 3) FAQJA E DETAJEVE -- VERIFIKUAR LIVE
# ------------------------------------------------------------------
SEL_HISTORIKU_RRESHTAT = ".orderHistoryLines > div"

# Ngjarje "teknike" (log automatik i sistemit, jo status i vertete dergese)
# -- filtrohen, s'i shfaqim klientit.
RREGULLAT_NGJARJE_TEKNIKE = [
    re.compile(r"pesha u ndryshua", re.IGNORECASE),
    re.compile(r"gjatesia u ndryshua", re.IGNORECASE),
    re.compile(r"gjeresia u ndryshua", re.IGNORECASE),
    re.compile(r"lartesia u ndryshua", re.IGNORECASE),
]


def _eshte_ngjarje_teknike(pershkrimi: str) -> bool:
    return any(r.search(pershkrimi or "") for r in RREGULLAT_NGJARJE_TEKNIKE)


def _ruaj_debug(driver, tag: str):
    """Njesoj si tek ultra_portal_scrape.py -- ruan screenshot + HTML per diagnostikim.
    PLUS (25/09/2026): printon URL-in aktual dhe nje pjese te shkurter te tekstit te
    dukshem te faqes DIREKT ne log-un e vete workflow-it (skeda "Actions" -> run-i ->
    hapi "Xhiro sinkronizimin"), qe te mos duhet gjithmone te shkarkohet artifact-i
    .zip per te kuptuar CFARE ka ndodhur ne fakt (p.sh. mesazh "kredenciale te
    gabuara", faqe verifikimi/"jam njeri", apo thjesht faqja ende ne /login)."""
    try:
        print(f"  (URL aktual ne momentin e deshtimit: {driver.current_url})")
        try:
            teksti = driver.execute_script("return document.body.innerText || '';")
            teksti = " ".join(teksti.split())[:600]
            if teksti:
                print(f"  (tekst i shkurter i dukshem ne faqe: {teksti})")
        except Exception:
            pass
        os.makedirs("debug", exist_ok=True)
        driver.save_screenshot(f"debug/postman_{tag}.png")
        with open(f"debug/postman_{tag}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"  (u ruajt diagnostikimi: debug/postman_{tag}.png dhe .html)")
    except Exception as e:
        print(f"  (s'u ruajt dot diagnostikimi: {e})")


def login_to_postman(username: str, password: str, headless: bool = True):
    """
    Hap Chrome, logohet ne portalin e biznesit te Postman. Kthen 'driver'.

    HAMENDESIM (duhet konfirmuar): faqja e login-it ka VETEM 2 fusha input
    te dukshme -- nje fushe teksti ("Username ose E-mail Adresa") dhe nje
    fushe fjalekalimi (type="password"). Ne vend qe te hamendesojme nje "id"
    apo "name" (qe s'i pame, s'kishin klase te qendrueshme ne pjesen tjeter
    te faqes), i gjejme fushat NGA VETE TIPI I TYRE (input[type=password] eshte
    gjithnje i sigurte per fjalekalimin; fusha e pare qe s'eshte password
    eshte username/email) -- kjo eshte e qendrueshme edhe nese faqja s'ka
    "id"/"name" te dukshem.
    """
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,1000")
    driver = webdriver.Chrome(options=options)

    driver.get(URL_LOGIN)
    # 35s (jo 20s si me pare, 25/09/2026): dhame pak me shume kohe per rastin
    # kur serveri i GitHub Actions eshte me i ngadalte se kompjuteri lokal.
    wait = WebDriverWait(driver, 35)
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']")))

        te_gjitha_fushat = driver.find_elements(By.TAG_NAME, "input")
        fusha_fjalekalim = next(
            (f for f in te_gjitha_fushat if f.get_attribute("type") == "password"), None
        )
        fusha_username = next(
            (
                f for f in te_gjitha_fushat
                if f.get_attribute("type") in (None, "", "text", "email")
                and f.is_displayed()
            ),
            None,
        )
        if fusha_fjalekalim is None or fusha_username is None:
            raise TimeoutException("s'u gjeten te dyja fushat e login-it")

        fusha_username.send_keys(username)
        fusha_fjalekalim.send_keys(password)

        # Butoni i login-it -- ZBULUAR (25/09/2026, nga 2 raunde inspektimi
        # direkt te DOM-i): faqja ka DY elemente qe permbajne tekstin "Kyçu"
        # -- njeri eshte nje buton/link NE KRYE te faqes, class="ant-dropdown-
        # link" (thjesht navigim drejt /login, PA lidhje me formularin), dhe
        # VETEM tjetri (poshte fushave, pas "Rikthe fjalëkalimin") eshte
        # butoni i VERTETE qe dorezon formularin, class permban "loginButton".
        # DY GABIME te renditura qe i hasem:
        #   1) Kerkimi sipas TEKSTIT ("contains(., 'Kyçu')") gjente GABIMISHT
        #      te parin (elementi i pare ne renditjen e dokumentit).
        #   2) Kerkimi sipas "type='submit'" DUKEJ i sigurt (e pame nje here
        #      keshtu ne inspektim), por atributi "type" i butonit te
        #      vertete NDRYSHON mes "button"/"submit" varesisht momentit te
        #      "hidratimit" te faqes (sjellje e vete Ant Design) -- pra s'eshte
        #      i qendrueshem per Selenium.
        # Zgjidhja PERFUNDIMTARE: identifikojme butonin nga KLASA e tij
        # "loginButton", qe eshte konstante dhe UNIKE ne faqe (e konfirmuar
        # 2 here permes inspektimit live te DOM-it).
        butoni_kycu = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button.loginButton")
        ))
        butoni_kycu.click()

        wait.until(EC.url_contains(URL_DASHBOARD_PJESE))
    except TimeoutException:
        print("  -> DESHTOI: login-i s'perfundoi (fushat e login-it, butoni, ose /dashboard).")
        _ruaj_debug(driver, "00_login_deshtoi")
        raise
    return driver


def _nxirr_statusin_nga_rreshti(statusi_raw: str) -> str:
    """
    Kolona "statusDescription" e rreshtit permban statusin dhe emrin e
    agjentit TE NGJITUR pa hapesire (p.sh. "•Në transportArdian Roka") --
    e ndajme duke kerkuar CILI status i njohur (nga STATUSET_E_MUNDSHME)
    eshte "prefiks" i tekstit (pas heqjes se "•" fillestare).
    Kthen statusin e njohur, ose gjithe tekstin e paster nese asnje s'perputhet.
    """
    i_paster = (statusi_raw or "").lstrip("•").strip()
    for status in STATUSET_E_MUNDSHME:
        if i_paster.startswith(status):
            return status
    return i_paster


def _lexo_qelizat_rreshtit(rresht) -> dict:
    """Kthen {col_id: tekst} per te gjitha qelizat e nje rreshti te grid-it."""
    rezultati = {}
    for qeliza in rresht.find_elements(By.CSS_SELECTOR, SELEKTOR_QELIZA):
        col_id = qeliza.get_attribute("col-id")
        if col_id:
            rezultati[col_id] = qeliza.text.strip()
    return rezultati


def _id_numerik_nga_kodi(kodi: str) -> str:
    """'#2PD3-4385237' -> '4385237' (pjesa pas vizes se fundit)."""
    m = re.search(r"-(\d+)\s*$", kodi or "")
    return m.group(1) if m else ""


def _parse_data_ore(raw: str):
    """'24.09.2026 16:25' -> ISO 8601 me offset Europe/Prishtine (+02:00 ne vere, njesoj si Shqiperia)."""
    dt = datetime.strptime(raw.strip(), "%d.%m.%Y %H:%M")
    dt = dt.replace(tzinfo=timezone(timedelta(hours=2)))
    return dt.isoformat()


def get_order_history(driver, postman_id: str) -> list:
    """
    Shkon direkt ne URL-ne e detajeve (order-details?id=...) dhe nxjerr
    "HISTORIKUN E POROSISE" -- filtron ngjarjet "teknike" (ndryshim peshe/
    dimensioni), qe s'jane te dobishme per klientin.
    """
    wait = WebDriverWait(driver, 20)

    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SEL_HISTORIKU_RRESHTAT)))
    except TimeoutException:
        print(f"  -> DESHTOI: postman_id {postman_id} s'e shfaqi historikun.")
        _ruaj_debug(driver, f"{postman_id}_pa_histori")
        return []

    ngjarjet = []
    for rresht in driver.find_elements(By.CSS_SELECTOR, SEL_HISTORIKU_RRESHTAT):
        leafs = [
            el for el in rresht.find_elements(By.XPATH, ".//*")
            if not el.find_elements(By.XPATH, "./*") and el.text.strip()
        ]
        if len(leafs) < 2:
            continue
        data_ore_raw = leafs[0].text.strip()
        pershkrimi = leafs[1].text.strip()
        agjenti = leafs[2].text.strip() if len(leafs) > 2 else None

        if _eshte_ngjarje_teknike(pershkrimi):
            continue

        try:
            koha_iso = _parse_data_ore(data_ore_raw)
        except ValueError:
            continue

        ngjarjet.append({
            "event_time": koha_iso,
            "status_label": pershkrimi,
            "status_tag": None,
            "note": None,
            "handled_by": agjenti,
        })

    return ngjarjet


def get_order_history_ne_tab_te_re(driver, postman_id: str) -> list:
    """
    RENDESISHME: hap detajet e pakos NE NJE TAB TE RE te browser-it (jo duke
    navigare larg listes ne te njejtin tab), qe faqja/pagination-i i listes
    (ku mund te jemi thelle, p.sh. faqja 30 nga 50) TE MOS PRISHET fare --
    kthehemi thjesht duke mbyllur tab-in e ri, pa pasur nevoje te riklikojme
    "faqja tjeter" perseri e perseri (qe do te ishte i ngadalte dhe i
    brishte per skanime te medha).
    """
    tab_kryesor = driver.current_window_handle
    driver.execute_script("window.open('about:blank', '_blank');")
    driver.switch_to.window(driver.window_handles[-1])
    try:
        driver.get(f"https://postman-ks.com/order-details?id={postman_id}")
        return get_order_history(driver, postman_id)
    finally:
        driver.close()
        driver.switch_to.window(tab_kryesor)


def _kerko_me_rikthim(metoda, url, tentativa_max=3, **kwargs):
    """
    Njesoj si requests.post(...)/requests.get(...), por RIPROVON automatikisht
    (deri "tentativa_max" here, me nje pauze qe rritet mes tentativave) nese
    lidhja me Supabase-in DESHTON PERKOHESISHT (timeout, gabim rrjeti).
    ZBULUAR (26/09/2026, run i deshtuar ne GitHub Actions): nje skanim i
    gjate (qindra thirrje HTTP rradhazi drejt Supabase) here pas here has
    NJE lidhje qe ngec per pak sekonda (ReadTimeoutError) -- pa riprovim,
    kjo e ndalonte GJITHE skanimin, çka eshte humbje e panevojshme, sepse
    ngjarjet tashme ishin lexuar nga faqja e Postman-it (pjesa e ngadalte
    dhe e brishte), thjesht SHKRIMI ne Supabase deshtoi per nje moment.
    """
    fundit_gabim = None
    for tentativa in range(1, tentativa_max + 1):
        try:
            return metoda(url, **kwargs)
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            fundit_gabim = e
            if tentativa < tentativa_max:
                print(f"  (kujdes: lidhja me Supabase deshtoi perkohesisht, tentativa {tentativa}/{tentativa_max} -- riprovojme...)")
                time.sleep(3 * tentativa)
    raise fundit_gabim


def push_to_supabase(order_number: str, barcode: str, events: list, courier: str = "postman"):
    """Upsert ne public.tracking_events (e njejta tabele qe perdor Ultra Post, e dalluar nga 'courier')."""
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    rows_by_kyc = {}
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
        kyc = (rresht["order_number"], rresht["event_time"], rresht["status_label"])
        rows_by_kyc[kyc] = rresht

    rows = list(rows_by_kyc.values())
    if not rows:
        return

    resp = _kerko_me_rikthim(
        requests.post,
        f"{supabase_url}/rest/v1/tracking_events",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        params={"on_conflict": "order_number,event_time,status_label"},
        json=rows,
        timeout=30,
    )
    if not resp.ok:
        print(f"  -> Supabase ktheu {resp.status_code}: {resp.text}")
    resp.raise_for_status()


def fetch_seen_parcels() -> dict:
    """
    Lexon TE GJITHE tabelen 'postman_parcels_seen' (ne faqe, per te shmangur
    kufirin e 1000 rreshtave te Supabase -- gabimi qe e zbuluam dhe e
    rregulluam tek ultra_portal_scrape.py; ketu e kemi drejt qe nga fillimi).
    """
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    rezultati = {}
    madhesia_faqes = 1000
    fillimi = 0
    while True:
        resp = _kerko_me_rikthim(
            requests.get,
            f"{supabase_url}/rest/v1/postman_parcels_seen",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Range-Unit": "items",
                "Range": f"{fillimi}-{fillimi + madhesia_faqes - 1}",
            },
            params={"select": "postman_id,order_number,list_status_raw,active"},
            timeout=30,
        )
        resp.raise_for_status()
        rreshtat = resp.json()
        for rresht in rreshtat:
            rezultati[rresht["postman_id"]] = rresht
        if len(rreshtat) < madhesia_faqes:
            break
        fillimi += madhesia_faqes

    return rezultati


def upsert_seen_parcel(postman_id: str, order_number: str, status_raw: str, active: bool):
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    resp = _kerko_me_rikthim(
        requests.post,
        f"{supabase_url}/rest/v1/postman_parcels_seen",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        params={"on_conflict": "postman_id"},
        json=[{
            "postman_id": postman_id,
            "order_number": order_number,
            "list_status_raw": status_raw,
            "active": active,
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
        }],
        timeout=30,
    )
    if not resp.ok:
        print(f"  -> Supabase (postman_parcels_seen) ktheu {resp.status_code}: {resp.text}")
    resp.raise_for_status()


def cleanup_old_events():
    """Thirret 1 here ne dite (full_scan) -- e njejta pastrimi si Ultra Post (funksioni SQL eshte i perbashket)."""
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    resp = _kerko_me_rikthim(
        requests.post,
        f"{supabase_url}/rest/v1/rpc/cleanup_old_tracking_events",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        },
        json={},
        timeout=30,
    )
    if not resp.ok:
        print(f"  -> (kujdes: pastrimi i te dhenave te vjetra deshtoi -- {resp.status_code}: {resp.text})")
    else:
        print("Pastrimi i porosive mbi 30 dite u krye (i perbashket per Ultra Post + Postman).")


def _kliko_diten_ne_kalendar(driver, wait, data_target):
    """
    Brenda kalendarit TASHME TE HAPUR (Ant Design DatePicker), lundron
    mbrapa muaj-pas-muaji (kalendari hapet gjithmone ne MUAJIN AKTUAL) dhe
    kliko diten e sakte.
    ZBULUAR (25/09/2026, testuar live): te shkruarit e tekstit direkt ne
    fushe (p.sh. "2026-08-01") pati sjellje jo te qendrueshme -- "Escape"
    e ANULON ndryshimin (kthehet te vlera e meparshme), "Enter" ndonjehere
    le kalendarin te hapur. Klikimi i vertete i dites ne kalendar eshte
    METODA E QENDRUESHME, e konfirmuar live.
    """
    sot = datetime.now(timezone(timedelta(hours=2))).date()
    muaj_mbrapa = (sot.year - data_target.year) * 12 + (sot.month - data_target.month)
    if muaj_mbrapa > 0:
        butoni_mbrapa = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_KALENDAR_PARA)))
        for _ in range(muaj_mbrapa):
            butoni_mbrapa.click()
            time.sleep(0.15)

    # "ant-picker-cell-in-view" dallon diten e MUAJIT TE SHFAQUR nga ditet
    # gri te muajit fqinj (qe mund te kene te njejtin numer, p.sh. "30" ne
    # fund te nje muaji 31-ditor) -- konfirmuar live ne DOM.
    # ZBULUAR (run i deshtuar ne GitHub Actions): duhet klikuar VETE div-i
    # ".ant-picker-cell-inner" (brenda <td>), JO vete <td>-ja -- Selenium
    # merr "element click intercepted" nese klikojme <td>-ne, sepse pika e
    # klikimit "kapet" ne fakt nga div-i i saj i brendshem.
    dita_xpath = (
        "//td[contains(@class,'ant-picker-cell-in-view')]"
        f"/div[contains(@class,'ant-picker-cell-inner')][normalize-space(text())='{data_target.day}']"
    )
    dita_el = wait.until(EC.element_to_be_clickable((By.XPATH, dita_xpath)))
    try:
        dita_el.click()
    except ElementClickInterceptedException:
        # ZBULUAR (run i deshtuar ne GitHub Actions): nese e para fushe
        # ("Prej datës") sapo u mbyll, kalendari i saj mund te jete ende
        # ne "animacion mbylljeje" (fade-out) teksa hapim te dytin ("Deri
        # me") -- per nje çast te dy kalendaret jane ne DOM, njeri sipas
        # tjetrit, dhe klikimi normal "kapet" nga qeliza e kalendarit te
        # VJETER (te njejtin lloj elementi -- "ant-picker-cell-inner").
        # Klikimi permes JavaScript-it anashkalon kete, sepse s'i intereson
        # cili element eshte "sipër" vizualisht.
        driver.execute_script("arguments[0].click();", dita_el)

    # Presim qe VETE paneli i kalendarit te zhduket krejtesisht nga DOM-i
    # PARA se te vazhdojme te fusha tjeter -- kjo eshte zgjidhja rrenjesore
    # per problemin e mesiperm (jo vetem nje "patch" per simptomen).
    try:
        WebDriverWait(driver, 5).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, ".ant-picker-dropdown"))
        )
    except TimeoutException:
        pass


def _vendos_filtrin_e_dates(driver, wait, dite_prapa: int) -> bool:
    """
    Vendos filtrin "Prej datës" / "Deri me" ne faqen e listes se porosive
    te Postman-it, qe skanimi TE MOS kaloje krejt historikun (9800+ porosi
    qe nga fillimi i sistemit), por VETEM porosite e "dite_prapa" diteve te
    fundit. Shih shenimin tek XPATH_FUSHAT_DATE me siper per detaje.
    Kthen True nese filtri u vendos me sukses, False nese jo (rast i
    rralle -- p.sh. faqja e ka ndryshuar dizajnin) -- ne ate rast vazhdojme
    GJITHESI (thjesht do te skanoje me shume porosi se sa duhet).
    """
    sot = datetime.now(timezone(timedelta(hours=2))).date()
    nga = sot - timedelta(days=dite_prapa)

    try:
        fushat = driver.find_elements(By.XPATH, XPATH_FUSHAT_DATE)
        if len(fushat) < 2:
            print("  (kujdes: s'u gjeten fushat e filtrit te dates -- vazhdojme PA filter, do te skanohet gjithe historiku)")
            return False

        fushat[0].click()
        _kliko_diten_ne_kalendar(driver, wait, nga)

        # rilexo fushat -- DOM-i mund te jete rifreskuar pas klikimit te dites
        fushat = driver.find_elements(By.XPATH, XPATH_FUSHAT_DATE)
        fushat[1].click()
        _kliko_diten_ne_kalendar(driver, wait, sot)

        btn_filtro = wait.until(EC.element_to_be_clickable((By.XPATH, XPATH_BUTONI_FILTRO)))
        btn_filtro.click()
        time.sleep(1.5)
        print(f"  (filtri i dates u vendos: nga {nga.isoformat()} deri {sot.isoformat()})")
        return True
    except Exception as e:
        print(f"  (kujdes: s'u vendos dot filtri i dates -- {e} -- vazhdojme PA filter)")
        # SIGURI: nese diçka deshtoi ne MES te vendosjes se filtrit (p.sh.
        # fusha e pare u vendos, e dyta jo), rifreskojme faqen nga e para,
        # qe te mos mbetemi ne nje gjendje "gjysem-filtruar" te papritur --
        # me mire pa filter fare (skanon me shume, por sakte) se sa filter
        # i gabuar (mund te humbase porosi pa e kuptuar).
        try:
            driver.get(URL_LISTA_POROSIVE)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELEKTOR_RRESHT_GRID)))
        except Exception:
            pass
        return False


def _mblidh_rreshtat_e_faqes_me_scroll(driver) -> list:
    """
    Lexon TE GJITHE rreshtat e "faqes" aktuale te grid-it (p.sh. 500
    porosi), duke lëvizur (scroll) VETE brenda kontejnerit -- shih
    shenimin tek SEL_GRID_VIEWPORT me siper per PSE kjo eshte e nevojshme
    (AG Grid virtualizon, s'i mban te GJITHA ne DOM njekohesisht).
    Kthen nje liste fjalorësh {col_id: tekst}, nje per çdo rresht UNIK
    (identifikuar nga atributi "row-index", jo nga teksti -- qendrueshem
    edhe kur DOM-i i nje rreshti rikrijohet gjate scroll-imit).
    """
    rezultati = {}  # row_index (string) -> {col_id: tekst}
    try:
        viewport = driver.find_element(By.CSS_SELECTOR, SEL_GRID_VIEWPORT)
    except NoSuchElementException:
        return []

    lartesia_totale = driver.execute_script("return arguments[0].scrollHeight;", viewport) or 0
    lartesia_dukshme = driver.execute_script("return arguments[0].clientHeight;", viewport) or 1
    hapi = max(int(lartesia_dukshme * 0.85), 200)  # mbivendosje e vogel, per te mos humbur rreshta

    pozicioni = 0
    while True:
        driver.execute_script("arguments[0].scrollTop = arguments[1];", viewport, pozicioni)
        time.sleep(0.2)
        for rresht in driver.find_elements(By.CSS_SELECTOR, SELEKTOR_RRESHT_GRID):
            # ZBULUAR (run i deshtuar ne GitHub Actions): edhe VETE leximi i
            # atributit "row-index" mund te deshtoje me
            # StaleElementReferenceException -- AG Grid mund ta rikrijoje
            # rreshtin (per shkak te scroll-it) SAKTESISHT mes momentit kur e
            # gjejme (find_elements) dhe momentit kur e lexojme. E gjithe
            # pjesa qe prek "rresht"-in duhet te jete brenda te NJEJTIT
            # try/except, jo vetem _lexo_qelizat_rreshtit().
            try:
                row_index = rresht.get_attribute("row-index")
                if not row_index or row_index in rezultati:
                    continue
                qelizat = _lexo_qelizat_rreshtit(rresht)
            except StaleElementReferenceException:
                continue
            if qelizat.get("displayId"):
                rezultati[row_index] = qelizat

        if pozicioni >= lartesia_totale - lartesia_dukshme:
            break
        pozicioni += hapi

    driver.execute_script("arguments[0].scrollTop = 0;", viewport)  # thjesht per pastërti vizuale
    return list(rezultati.values())


def _vendos_madhesine_maksimale_faqes(driver, wait):
    """Provon te vendose madhesine e faqes ne 500 (maksimumi i mundshem, i verifikuar live).

    ZBULUAR (25/09/2026, run live): njesoj si "faqja tjeter" (shih
    _kliko_faqen_tjeter), edhe ky klikim mund te merret nga overlay-i
    "duke ngarkuar" qe mbulon gjithe faqen -- kur ndodh kjo, PERPARA
    kishim vetem nje `except` te gjere qe printonte paralajmerimin dhe
    VAZHDONTE me madhesine PARAZGJEDHUR te faqes (20 rreshta), jo 500.
    Pasoja ne praktike: nje skanim i plote (150 faqe x 20 = 3000 rreshta)
    mbulonte VETEM ~30% te 9834 porosive gjithsej, ne vend te ~100% (150
    faqe x 500 = 75000 rreshta, shume me shume se sa nevojitet). Tani
    presim overlay-in te zhduket dhe kemi rezerve klikim me JavaScript,
    njesoj si per pagination-in.
    """
    try:
        try:
            WebDriverWait(driver, 15).until(
                EC.invisibility_of_element_located(
                    (By.CSS_SELECTOR, "div.fixed.top-0.left-0.w-screen.h-screen.z-50")
                )
            )
        except TimeoutException:
            pass

        selektori = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//*[contains(@class,'ant-select') and .//text()[contains(.,'/ page') or contains(.,'/page')]]")
        ))
        try:
            selektori.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", selektori)

        opsioni = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//div[contains(@class,'ant-select-item-option') and contains(., '500')]")
        ))
        try:
            opsioni.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", opsioni)

        time.sleep(1)

        # KONTROLL: verifikojme qe VERTET u vendos 500 -- nese jo (p.sh.
        # klikimi "kaloi" por dropdown-i eshte mbyllur nga diçka tjeter
        # ne kohen e gabuar), e provojme edhe 1 here para se te heqim dore.
        try:
            teksti_tanishem = driver.find_element(
                By.XPATH, "//*[contains(@class,'ant-select') and .//text()[contains(.,'/ page') or contains(.,'/page')]]"
            ).text
            if "500" not in teksti_tanishem:
                raise Exception(f"dropdown-i mbeti '{teksti_tanishem}' ne vend te '500 / page'")
        except Exception as e_verifikim:
            print(f"  (kujdes: madhesia e faqes mund te mos jete 500 -- {e_verifikim})")
    except Exception as e:
        print(f"  (kujdes: s'u vendos dot madhesia maksimale e faqes -- {e})")


def _kliko_faqen_tjeter(driver) -> bool:
    """Kliko shigjeten 'faqja tjeter' te pagination-it Ant Design. Kthen False nese jemi ne faqen e fundit."""
    try:
        next_li = driver.find_element(By.CSS_SELECTOR, "li.ant-pagination-next")
        klasa = next_li.get_attribute("class") or ""
        if "ant-pagination-disabled" in klasa:
            return False

        # ZBULUAR (25/09/2026, run i deshtuar ne GitHub Actions): ndonjehere
        # nje overlay "duke ngarkuar" (div gjysem-transparent qe mbulon
        # GJITHE faqen, "fixed top-0 left-0 w-screen h-screen ... z-50")
        # mbetet ende i dukshem nga veprimi i fundit (p.sh. hapja/mbyllja
        # e tab-it te ri me detajet e porosise se fundit ne kete faqe) --
        # nese klikojme "faqja tjeter" TEKSA ai eshte ende aty, Selenium
        # merr ElementClickInterceptedException (klikon mbi overlay, jo
        # mbi buton). Zgjidhja: presim qe overlay-i te zhduket PARA se te
        # klikojme; nese s'zhduket brenda 15 sek (rast i rralle), vazhdojme
        # gjithsesi dhe, nese na e pengon prap, klikojme direkt permes
        # JavaScript-it, qe anashkalon çdo overlay mbi te.
        try:
            WebDriverWait(driver, 15).until(
                EC.invisibility_of_element_located(
                    (By.CSS_SELECTOR, "div.fixed.top-0.left-0.w-screen.h-screen.z-50")
                )
            )
        except TimeoutException:
            pass

        butoni = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "li.ant-pagination-next button"))
        )
        try:
            butoni.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", butoni)

        time.sleep(1.2)
        return True
    except NoSuchElementException:
        return False


def scan_all_parcels(driver, full_scan: bool = False, dite_prapa: int = None) -> list:
    """
    Skanon porosite e portalit te Postman (njesoj si scan_all_parcels() ne
    ultra_portal_scrape.py), por VETEM ato te "dite_prapa" diteve te fundit
    (shih _vendos_filtrin_e_dates me siper -- ndryshe do te kalonim
    krejt historikun, 9800+ porosi, shumica krejtesisht te panevojshme).
    Per çdo porosi:
      - Nese eshte E RE (s'e kemi pare kurre) OSE STATUSI ka ndryshuar qe nga
        hera e fundit -> hap detajet, nxjerr historikun, ruaj ne Supabase.
      - Perndryshe -> anashkalohet (kursen kohe).
    Ne "full_scan=True" (1 here ne dite), kalon te GJITHA faqet pa ndalur me
    pare per "streak", per te kapur çdo porosi qe skanimi i shpejte mund ta
    kete "harruar".
    """
    if dite_prapa is None:
        dite_prapa = int(os.environ.get("DITE_PRAPA_SKANIM", DITE_PRAPA_PARAZGJEDHUR))

    seen = fetch_seen_parcels()
    rezultatet = []
    wait = WebDriverWait(driver, 20)

    driver.get(URL_LISTA_POROSIVE)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELEKTOR_RRESHT_GRID)))
    # RENDESISHME: filtri i dates PARA madhesise se faqes -- ne kete renditje
    # e testuam live dhe funksionoi sakte (klikimi i "Filtro" e rifreskon
    # listen, dhe madhesia e faqes mbetet e vendosur nga hapi tjeter).
    _vendos_filtrin_e_dates(driver, wait, dite_prapa)
    _vendos_madhesine_maksimale_faqes(driver, wait)

    streak_te_panevojshme = 0
    faqe_nr = 1

    while True:
        rreshtat_te_dhena = _mblidh_rreshtat_e_faqes_me_scroll(driver)
        print(f"  (faqja {faqe_nr}: {len(rreshtat_te_dhena)} rreshta u lexuan nga grid-i)")
        for qelizat in rreshtat_te_dhena:
            kodi = qelizat.get("displayId", "")
            postman_id = _id_numerik_nga_kodi(kodi)
            order_number = qelizat.get("refid", "").strip()
            statusi_raw = qelizat.get("statusDescription", "")

            if not postman_id or not order_number:
                continue

            statusi = _nxirr_statusin_nga_rreshti(statusi_raw)

            e_njohur = seen.get(postman_id)
            e_panryshuar = (
                e_njohur is not None
                and e_njohur.get("list_status_raw") == statusi
            )

            if e_panryshuar:
                if not full_scan:
                    streak_te_panevojshme += 1
                continue

            streak_te_panevojshme = 0

            ngjarjet = get_order_history_ne_tab_te_re(driver, postman_id)
            eshte_perfundimtar = statusi in STATUSET_PERFUNDIMTARE

            # NDRYSHUAR (26/09/2026, me kerkese te perdoruesit): PARA kishim
            # ketu nje kontroll qe anashkalonte (s'i shkruante ne
            # tracking_events) porosite "shume te vjetra", per te mbrojtur
            # bazen e te dhenave nga mbingarkesa. HEQUR sepse: (1) eshte
            # burim shtese potencial gabimesh (nje porosi krejt e RE u gjet
            # qe NUK ishte ruajtur -- ende s'e dime nese ky kontroll ishte
            # shkaku, por eshte i vetmi vend qe do e kishte anashkaluar), dhe
          # (2) njesoj si ultra_portal_scrape.py (qe s'e ka pasur KURRE kete
            # kontroll dhe punon mire), tani BESOJME TERESISHT te pastrimi i
            # perbashket ne baze te te dhenave (cleanup_old_tracking_events(),
            # thirrur me poshte nga cleanup_old_events()) per te hequr te
            # dhenat e vjetra -- shih supabase_schema.sql per shpjegimin e
            # plote dhe periudhen e "graces" qe u shtua pikerisht per kete
            # ndryshim (qe nje backfill i sapo-bere te mos qendroje 30 dite
            # te plota ne baze para se te fshihet).
            push_to_supabase(order_number, kodi, ngjarjet, courier="postman")
            upsert_seen_parcel(postman_id, order_number, statusi, active=not eshte_perfundimtar)
            seen[postman_id] = {"order_number": order_number, "list_status_raw": statusi, "active": not eshte_perfundimtar}
            rezultatet.append((order_number, postman_id, ngjarjet))
            print(f"  Porosia {kodi} (referenca {order_number}): {len(ngjarjet)} ngjarje u sinkronizuan ({statusi}).")
            # SHENIM: falë tab-it te ri (get_order_history_ne_tab_te_re), lista
            # dhe faqja/pagination-i i saj NUK preken fare -- s'ka nevoje te
            # rikthehemi ose te riklikojme asgje ketu.

        if not full_scan and streak_te_panevojshme >= STREAK_NDALO_SKANIMIN:
            print(f"  (u ndal skanimi -- {streak_te_panevojshme} porosi rradhazi tashme te sinkronizuara e te pandryshuara)")
            break

        faqe_nr += 1
        if faqe_nr > MAX_FAQE_SKANIM:
            print(f"  (u arrit kufiri i sigurise prej {MAX_FAQE_SKANIM} faqesh -- ndalojme per kete here)")
            break

        if not _kliko_faqen_tjeter(driver):
            break

    return rezultatet


def sync_one_order(order_number: str, driver=None):
    """
    Menyra TEST MANUAL: kerkon 1 porosi te caktuar permes filtrit "Kërko
    tekstin" (Referenca), hap detajet, dhe printon historikun -- pa prekur
    skanimin e plote. E dobishme per te konfirmuar qe login-i dhe nxjerrja e
    historikut funksionojne SAKTE, PARA se te aktivizohet skanimi automatik.
    """
    own_driver = driver is None
    if own_driver:
        driver = login_to_postman(
            username=os.environ["POSTMAN_USERNAME"].strip(),
            password=os.environ["POSTMAN_PASSWORD"].strip(),
        )
    try:
        wait = WebDriverWait(driver, 20)
        driver.get(URL_LISTA_POROSIVE)

        fusha = wait.until(EC.element_to_be_clickable((By.XPATH, XPATH_FUSHA_KERKIMI)))
        fusha.clear()
        fusha.send_keys(order_number)
        driver.find_element(By.XPATH, XPATH_BUTONI_FILTRO).click()

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELEKTOR_RRESHT_GRID)))
        time.sleep(0.8)  # nje pauze e vogel per t'u siguruar qe grid-i eshte rifreskuar

        rreshtat = driver.find_elements(By.CSS_SELECTOR, SELEKTOR_RRESHT_GRID)
        if not rreshtat:
            print(f"Porosia {order_number}: NUK U GJET asnje rezultat.")
            return []

        qelizat = _lexo_qelizat_rreshtit(rreshtat[0])
        kodi = qelizat.get("displayId", "")
        postman_id = _id_numerik_nga_kodi(kodi)
        statusi = _nxirr_statusin_nga_rreshti(qelizat.get("statusDescription", ""))
        print(f"U gjet: {kodi} (id={postman_id}), statusi: {statusi}")

        ngjarjet = get_order_history(driver, postman_id)
        for e in ngjarjet:
            print(f"  {e['event_time']}: {e['status_label']} ({e.get('handled_by')})")

        push_to_supabase(order_number, kodi, ngjarjet, courier="postman")
        print(f"Porosia {order_number}: {len(ngjarjet)} ngjarje u sinkronizuan ne Supabase.")
        return ngjarjet
    finally:
        if own_driver:
            driver.quit()


if __name__ == "__main__":
    numrat = sys.argv[1:]

    if numrat:
        # Menyra TEST MANUAL: xhiro "python postman_portal_scrape.py 3828131 ..."
        driver = login_to_postman(
            username=os.environ["POSTMAN_USERNAME"].strip(),
            password=os.environ["POSTMAN_PASSWORD"].strip(),
        )
        try:
            for numer in numrat:
                try:
                    sync_one_order(numer, driver=driver)
                except TimeoutException:
                    print(f"Porosia {numer}: NUK U GJET ose faqja nuk u ngarkua (timeout).")
        finally:
            driver.quit()

    else:
        # Menyra AUTOMATIKE (p.sh. GitHub Actions): skanon vete te gjitha
        # porosite e portalit te Postman.
        full_scan = bool(os.environ.get("FULL_SCAN"))
        print(f"Duke skanuar {'TE GJITHA' if full_scan else 'vetem ndryshimet e'} porosite te Postman...")

        driver = login_to_postman(
            username=os.environ["POSTMAN_USERNAME"].strip(),
            password=os.environ["POSTMAN_PASSWORD"].strip(),
        )
        try:
            rezultatet = scan_all_parcels(driver, full_scan=full_scan)
        finally:
            driver.quit()

        print(f"U sinkronizuan {len(rezultatet)} porosi (te reja ose te ndryshuara).")

        if full_scan:
            cleanup_old_events()
