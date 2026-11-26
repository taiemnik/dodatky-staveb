# -*- coding: utf-8 -*-
"""Náhodný vzorek smluv z celostátní kohorty -> seznam pro pilot_mesto.py (úplné dohledání dodatků přes Hlídače).

Proč:  z měsíčních exportů vidíme jen dodatky zveřejněné ve stažených měsících. Hlídač vidí všechny do dneška.
       Na náhodném vzorku tak zjistíme, kolik smluv dodatek opravdu má a o kolik se cena změnila.
Co dělá: 1) vylosuje N smluv (pevné semínko = losování jde zopakovat) + přidá všechny nad zadaný práh ceny,
         2) k ID smlouvy dohledá aktuální verzi záznamu (dotaz idSmlouvy:<ID>), protože Hlídač čísluje verze,
         3) zapíše zaklad.csv ve tvaru pro pilot_mesto.py a vzorek.csv s údaji z kohorty.
Vstup:   python vzorek_priprav.py <kohorta.csv> <výstupní složka> [N=100] [práh „vzít všechny“ = 50000000]
"""
import csv
import html
import random
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
kohorta, slozka = sys.argv[1], Path(sys.argv[2])
N = int(sys.argv[3]) if len(sys.argv) > 3 else 100
VSE_NAD = float(sys.argv[4]) if len(sys.argv) > 4 else 50_000_000
WEB = "https://www.hlidacstatu.cz"
UA = "dodatky-staveb-pilot/0.1"          # poctivé označení klienta; Hlídač na něj odpovídá normálně
H = slozka / "html"
H.mkdir(parents=True, exist_ok=True)

with open(kohorta, encoding="utf-8-sig", newline="") as f:
    K = list(csv.DictReader(f, delimiter=";"))
random.seed(20261125)                                   # pevné semínko: stejný vzorek při každém spuštění
nahodne = random.sample(K, min(N, len(K)))
velke = [r for r in K if float(r["cena_puvodni"]) >= VSE_NAD]
vybrane = {r["ids"]: dict(r, vyber="nahodny") for r in nahodne}
for r in velke:
    vybrane.setdefault(r["ids"], dict(r, vyber="velka_navic"))
print(f"kohorta {len(K)} | náhodně {len(nahodne)} | velké navíc {sum(1 for r in vybrane.values() if r['vyber']=='velka_navic')}")

# 2) aktuální verze záznamu: jedna dávka curl
pary = [(f"{WEB}/HledatSmlouvy?" + urllib.parse.urlencode({"Q": f"idSmlouvy:{ids}"}), H / f"i_{ids}.html")
        for ids in vybrane]
chybi = [(u, c) for u, c in pary if not (c.exists() and c.stat().st_size > 2000)]
if chybi:
    cfg = slozka / "_curl_vzorek.cfg"
    with open(cfg, "w", encoding="utf-8") as f:
        for u, c in chybi:
            f.write(f'url = "{u}"\noutput = "{c.as_posix()}"\n')
    subprocess.run(["curl", "-sS", "-L", "--max-time", "120", "--retry", "2", "--rate", "40/m", "-A", UA, "-K", str(cfg)])
    print("staženo stránek:", len(chybi))

nenalezeno = 0
with open(slozka / "zaklad.csv", "w", newline="", encoding="utf-8-sig") as fz, \
        open(slozka / "vzorek.csv", "w", newline="", encoding="utf-8-sig") as fv:
    wz = csv.writer(fz, delimiter=";")
    wz.writerow(["id", "ids"])
    pole = list(next(iter(vybrane.values())).keys()) + ["id_hlidac"]
    wv = csv.DictWriter(fv, fieldnames=pole, delimiter=";")
    wv.writeheader()
    for ids, r in vybrane.items():
        c = H / f"i_{ids}.html"
        s = html.unescape(c.read_text(encoding="utf-8", errors="replace")) if c.exists() else ""
        m = re.search(r'<tr class="bg first">.*?/Detail/(\d+)', s[s.find("hs-results"):], flags=re.S)
        r["id_hlidac"] = m.group(1) if m else ""
        if not m:
            nenalezeno += 1
        else:
            wz.writerow([m.group(1), ids])
        wv.writerow(r)
print("vzorek:", len(vybrane), "| nenalezeno na Hlídači:", nenalezeno)
