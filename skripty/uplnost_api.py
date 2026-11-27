# -*- coding: utf-8 -*-
"""Kolik stavebních smluv sběr přes API Hlídače státu nenajde?

Proč:   sběr přes API se ptá na `oblast:stav`, tedy na třídění smluv, které dělá Hlídač státu.
        Kohorta z otevřených dat registru (pět měsíčních exportů) vybírá stavební smlouvy vlastními
        klíčovými slovy z předmětu. Obě cesty se dají porovnat na stejných smlouvách: co je v kohortě
        z exportů a v datech z API chybí, to API cesta přehlíží.
Vstup:  python -I skripty/uplnost_api.py [kohorta z exportů] [kohorta z API] [složka s daty z API]
Výstup: podíl nalezených smluv celkem, podle typu města a podle pásma ceny; seznam ukázek nenalezených.
"""
import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
KOREN = Path(__file__).resolve().parent.parent
EXPORTY = Path(sys.argv[1]) if len(sys.argv) > 1 else KOREN / "data/cr/kohorta_2023.csv"
API_KOHORTA = Path(sys.argv[2]) if len(sys.argv) > 2 else KOREN / "data/cr_api/kohorta_2022-2025.csv"
API_DATA = Path(sys.argv[3]) if len(sys.argv) > 3 else KOREN / "data/rs_api2"


def nacti(cesta):
    with open(cesta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def cislo(text):
    try:
        return float(str(text).replace(",", ".").replace(" ", ""))
    except ValueError:
        return 0.0


def pasmo(cena):
    for hranice, jmeno in ((2e6, "1–2 mil."), (5e6, "2–5 mil."), (20e6, "5–20 mil."), (50e6, "20–50 mil.")):
        if cena < hranice:
            return jmeno
    return "50 mil. a víc"


exporty = nacti(EXPORTY)
v_kohorte_api = {r["ids"] for r in nacti(API_KOHORTA)}

# všechny záznamy, které API vrátilo (i ty, které do kohorty neprošly – jiný rok, nižší cena, dodatek)
v_datech_api = set()
for soubor in API_DATA.glob("rs_*.jsonl.gz"):
    with gzip.open(soubor, "rt", encoding="utf-8") as f:
        for radek in f:
            v_datech_api.add(str(json.loads(radek)["ids"]))

stav = Counter()
po_kat = defaultdict(Counter)
po_pasmu = defaultdict(Counter)
chybi = []
for r in exporty:
    if r["ids"] in v_kohorte_api:
        s = "v kohortě z API"
    elif r["ids"] in v_datech_api:
        s = "API vrátilo, do kohorty neprošla"
    else:
        s = "API nevrátilo"
        chybi.append(r)
    stav[s] += 1
    po_kat[r["kategorie"]][s] += 1
    po_pasmu[pasmo(cislo(r["cena_puvodni"]))][s] += 1

n = len(exporty)
print(f"kohorta z exportů registru: {n} smluv ({EXPORTY.name})")
for s, k in stav.most_common():
    print(f"  {s}: {k} = {100 * k / n:.1f} %")
for nadpis, skupiny in (("podle typu města", po_kat), ("podle původní ceny", po_pasmu)):
    print(f"\n{nadpis}:")
    for jmeno, c in skupiny.items():
        celkem = sum(c.values())
        print(f"  {jmeno}: {celkem} smluv, v kohortě z API {c['v kohortě z API']} = {100 * c['v kohortě z API'] / celkem:.0f} %, "
              f"API nevrátilo {c['API nevrátilo']} = {100 * c['API nevrátilo'] / celkem:.0f} %")

print(f"\nukázky smluv, které API nevrátilo ({len(chybi)}):")
for r in sorted(chybi, key=lambda r: -cislo(r["cena_puvodni"]))[:15]:
    print(f"  {r['idv']} | {r['mesto']} | {cislo(r['cena_puvodni']) / 1e6:.1f} mil. | {r['predmet'][:95]}")
