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
     brendshme e portalit
