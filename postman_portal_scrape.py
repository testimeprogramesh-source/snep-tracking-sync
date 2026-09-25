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

MAX_FAQE_SKANIM = 150
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

        # Butoni i login-it -- ZBULUAR (25/09/2026, nga log-u i ri i
        # diagnostikimit): faqja ka DY elemente qe permbajne tekstin "Kyçu"
        # -- njeri eshte nje buton/link NE KRYE te faqes (thjesht navigim
        # drejt /login, PA lidhje me formularin), dhe VETEM tjetri (poshte
        # fushave, pas "Rikthe fjalëkalimin") eshte butoni i VERTETE qe
        # dorezon formularin. Kerkimi sipas TEKSTIT ("contains(., 'Kyçu')")
        # gjente GABIMISHT te parin (Selenium kthen gjithnje elementin e
        # PARE ne renditjen e dokumentit qe perputhet), e klikonte, dhe
        # s'ndodhte asgje -- pikerisht simptoma qe verejtem ne log (klikimi
        # "suksesshem", pa gabim, por URL-ja s'ndryshonte kurre). Zgjidhja:
        # gjejme butonin e VERTETE nga atributi i tij "type='submit'" (i
        # konfirmuar UNIK ne faqe permes inspektimit direkt te DOM-it), jo
        # nga teksti.
        butoni_kycu = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button[type='submit']")
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
        resp = requests.get(
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

    resp = requests.post(
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
        timeout=20,
    )
    if not resp.ok:
        print(f"  -> Supabase (postman_parcels_seen) ktheu {resp.status_code}: {resp.text}")
    resp.raise_for_status()


def cleanup_old_events():
    """Thirret 1 here ne dite (full_scan) -- e njejta pastrimi si Ultra Post (funksioni SQL eshte i perbashket)."""
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    resp = requests.post(
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


def _vendos_madhesine_maksimale_faqes(driver, wait):
    """Provon te vendose madhesine e faqes ne 500 (maksimumi i mundshem, i verifikuar live)."""
    try:
        selektori = driver.find_element(
            By.XPATH, "//*[contains(@class,'ant-select') and .//text()[contains(.,'/ page') or contains(.,'/page')]]"
        )
        selektori.click()
        opsioni = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//div[contains(@class,'ant-select-item-option') and contains(., '500')]")
        ))
        opsioni.click()
        time.sleep(1)
    except Exception as e:
        print(f"  (kujdes: s'u vendos dot madhesia maksimale e faqes -- {e})")


def _kliko_faqen_tjeter(driver) -> bool:
    """Kliko shigjeten 'faqja tjeter' te pagination-it Ant Design. Kthen False nese jemi ne faqen e fundit."""
    try:
        next_li = driver.find_element(By.CSS_SELECTOR, "li.ant-pagination-next")
        klasa = next_li.get_attribute("class") or ""
        if "ant-pagination-disabled" in klasa:
            return False
        next_li.find_element(By.CSS_SELECTOR, "button").click()
        time.sleep(1.2)
        return True
    except NoSuchElementException:
        return False


def scan_all_parcels(driver, full_scan: bool = False) -> list:
    """
    Skanon te GJITHA porosite e portalit te Postman (njesoj si
    scan_all_parcels() ne ultra_portal_scrape.py). Per çdo porosi:
      - Nese eshte E RE (s'e kemi pare kurre) OSE STATUSI ka ndryshuar qe nga
        hera e fundit -> hap detajet, nxjerr historikun, ruaj ne Supabase.
      - Perndryshe -> anashkalohet (kursen kohe).
    Ne "full_scan=True" (1 here ne dite), kalon te GJITHA faqet pa ndalur me
    pare per "streak", per te kapur çdo porosi qe skanimi i shpejte mund ta
    kete "harruar".
    """
    seen = fetch_seen_parcels()
    rezultatet = []
    wait = WebDriverWait(driver, 20)

    driver.get(URL_LISTA_POROSIVE)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELEKTOR_RRESHT_GRID)))
    _vendos_madhesine_maksimale_faqes(driver, wait)

    streak_te_panevojshme = 0
    faqe_nr = 1

    while True:
        rreshtat = driver.find_elements(By.CSS_SELECTOR, SELEKTOR_RRESHT_GRID)
        for rresht in rreshtat:
            try:
                qelizat = _lexo_qelizat_rreshtit(rresht)
            except StaleElementReferenceException:
                continue

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
