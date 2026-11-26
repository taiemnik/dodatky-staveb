# -*- coding: utf-8 -*-
"""Jak přesná je „lehká metoda“ (jen pole registru) proti ceně přečtené z textu dodatků?

Otázka:  stačí na hledání anomálií metadata registru, nebo je nutné číst dodatky?
Měří se na smlouvách, kde cenu z textu známe jistě (řetěz bez „neurčeno“):
  - o kolik procentních bodů se lehká metoda liší,
  - jestli trefí pásmo (bez nárůstu / do 10 % / 10–20 % / 20–30 % / 30 %+),
  - kolik skutečných anomálií 20 %+ najde (záchyt) a kolik jejích hlášení je planých (přesnost).
Vstup:   python lehka_presnost.py <složka s retezy.csv> [vzorek.csv – pak jen smlouvy vzorku]
"""
import csv
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
S = Path(sys.argv[1])
VZOREK = sys.argv[2] if len(sys.argv) > 2 else ""


def nacti(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


R = nacti(S / "retezy.csv")
if VZOREK:
    ids = {r["id_hlidac"] for r in nacti(VZOREK)}
    R = [r for r in R if r["id"] in ids]
else:
    R = [r for r in R if r["stavba"] == "1"]
R = [r for r in R if int(r["n_neurcenych"]) == 0]


def pasmo(z):
    return "zlevnění" if z < -0.5 else "beze změny" if z < 0.5 else "do 10 %" if z < 10 else "10–20 %" if z < 20 else "20–30 %" if z < 30 else "30 %+"


radky = []
for r in R:
    B = float(r["cena_puvodni"])
    zt = float(r["zmena_pct"])
    zl = (float(r["cena_konecna_lehka"]) - B) / B * 100
    radky.append((zt, zl, int(r["n_dodatku"]), r))
n = len(radky)
sd = [x for x in radky if x[2] > 0]
shoda_pb = sum(1 for zt, zl, *_ in radky if abs(zt - zl) <= 1)
shoda_pasmo = sum(1 for zt, zl, *_ in radky if pasmo(zt) == pasmo(zl))
print(f"Smluv s jistou cenou: {n} (z toho s dodatkem {len(sd)})")
print(f"  lehká metoda se liší nejvýš o 1 procentní bod: {shoda_pb} z {n} = {shoda_pb/n*100:.0f} %"
      f" | jen smlouvy s dodatkem: {sum(1 for zt, zl, *_ in sd if abs(zt-zl)<=1)} z {len(sd)}")
print(f"  trefí pásmo změny: {shoda_pasmo} z {n} = {shoda_pasmo/n*100:.0f} %")
for prah in (20, 30):
    skut = [x for x in radky if x[0] >= prah]
    hlas = [x for x in radky if x[1] >= prah]
    oboji = [x for x in radky if x[0] >= prah and x[1] >= prah]
    print(f"  nárůst {prah} %+: skutečných {len(skut)} | lehká metoda jich najde {len(oboji)} | hlásí celkem {len(hlas)}"
          f" (planých {len(hlas)-len(oboji)})")
smer = Counter("lehká výš" if zl - zt > 1 else "lehká níž" if zt - zl > 1 else "shoda" for zt, zl, *_ in sd)
print("  u smluv s dodatkem:", dict(smer))
print("  největší omyly lehké metody:")
for zt, zl, nd, r in sorted(radky, key=lambda x: -abs(x[0] - x[1]))[:6]:
    print(f"    text {zt:+6.1f} % · lehká {zl:+6.1f} % | dodatků {nd} (přílohou {r['n_priloh_dodatek']}, navázaných {r['n_navazanych']})"
          f" | {r['predmet'].replace('Smlouva o dílo - ', '')[:60]}")
