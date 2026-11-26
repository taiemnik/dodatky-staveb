# -*- coding: utf-8 -*-
"""Počet obyvatel měst z otevřených dat ČSÚ -> data/obce.csv (sloupce obyvatel, obyvatel_rok).

Proč:   srovnávat má smysl města podobné velikosti. Převodník obcí měl počet obyvatel jen u sídel ORP,
        obce II. typu chyběly.
Zdroj:  ČSÚ, datová sada OBY02A, ukazatel 2406P „Počet obyvatel k 1. 1.“ (https://data.csu.gov.cz).
        Dotaz po dávkách vyjmenovaných kódů obcí – jde o stovky měst, ne o všech 6 254 obcí.
Vstup:  python -I skripty/csu_obyvatele.py [rok=2026]
"""
import csv
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
KOREN = Path(__file__).resolve().parent.parent
ROK = sys.argv[1] if len(sys.argv) > 1 else "2026"
API = "https://data.csu.gov.cz/api/dotaz/v1/data/sady/OBY02A/vlastni"
KATEGORIE = ("statutární město", "obec III. typu", "obec II. typu")
DAVKA = 50

obce_csv = KOREN / "data" / "obce.csv"
with open(obce_csv, encoding="utf-8-sig", newline="") as f:
    O = list(csv.DictReader(f, delimiter=";"))
mesta = [r for r in O if r.get("kategorie") in KATEGORIE]
(KOREN / "data" / "csu").mkdir(parents=True, exist_ok=True)

hodnoty = {}
for i in range(0, len(mesta), DAVKA):
    kody = ",".join(r["kod"] for r in mesta[i:i + DAVKA])
    url = (f"{API}?format=CSV&kodCiselniku=true&kodZvlast=true&Uz45B={kody}"
           f"&CasR.od={ROK}&CasR.do={ROK}&IndicatorType=2406P&POHL2=0")
    cil = KOREN / "data" / "csu" / f"obyvatele_{ROK}_{i // DAVKA + 1}.csv"
    subprocess.run(["curl", "-sS", "-m", "120", "-o", str(cil), url], check=False)
    time.sleep(1.0)                                        # ohleduplně: jedna dávka za sekundu
    with open(cil, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("Uz45B.OBEC") and r.get("Hodnota"):
                hodnoty[r["Uz45B.OBEC"]] = float(r["Hodnota"])

doplneno = 0
for r in mesta:
    if r["kod"] in hodnoty:
        r["obyvatel"], r["obyvatel_rok"] = hodnoty[r["kod"]], ROK
        doplneno += 1
with open(obce_csv, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(O[0].keys()), delimiter=";")
    w.writeheader()
    w.writerows(O)
bez = [r["nazev"] for r in mesta if not r["obyvatel"]]
print(f"měst {len(mesta)} | počet obyvatel k 1. 1. {ROK} doplněn u {doplneno} | bez údaje: {bez}")
for kat in KATEGORIE:
    v = sorted(float(r["obyvatel"]) for r in mesta if r["kategorie"] == kat and r["obyvatel"])
    print(f"  {kat}: {len(v)} měst, nejmenší {v[0]:,.0f}, medián {v[len(v)//2]:,.0f}, největší {v[-1]:,.0f}".replace(",", " "))
