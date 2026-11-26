# -*- coding: utf-8 -*-
"""Křížová kontrola: změna ceny vyčtená z TEXTU dodatku proti hodnotě téhož dodatku v REGISTRU.

Dva nezávislé zdroje téhož čísla. Kde se shodnou, je nález ověřený. Kde ne, vypíše se k ruční kontrole
(může být špatně skript, ale i údaj v registru – např. hodnota s DPH nebo nová celková cena místo rozdílu).
Vstup:  python retezy_kontrola.py <složka s retezy.csv a dodatky.csv> [kolik neshod vypsat=15]
"""
import csv
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
S = Path(sys.argv[1])
KOLIK = int(sys.argv[2]) if len(sys.argv) > 2 else 15
R = {r["id"]: r for r in csv.DictReader(open(S / "retezy.csv", encoding="utf-8-sig"), delimiter=";")}
D = [d for d in csv.DictReader(open(S / "dodatky.csv", encoding="utf-8-sig"), delimiter=";")
     if R.get(d["id_smlouvy"], {}).get("stavba") == "1"]

vysl = Counter()
neshody = []
for d in D:
    if d["stav"] != "zmena_ceny" or not d["hodnota_v_registru"]:
        continue
    z, po, h = float(d["zmena"]), float(d["cena_po"]), float(d["hodnota_v_registru"])
    if abs(abs(z) - h) <= max(2, 0.001 * h):
        vysl["shoda: registr = rozdíl bez DPH"] += 1
    elif abs(po - h) <= max(2, 0.0001 * h):
        vysl["shoda: registr = nová celková cena"] += 1
    elif any(abs(abs(z) * (1 + s) - h) <= max(2, 0.001 * h) for s in (0.21, 0.15, 0.12)):
        vysl["shoda: registr = rozdíl s DPH"] += 1
    else:
        vysl["NESHODA"] += 1
        neshody.append(d)
bez = sum(1 for d in D if d["stav"] == "zmena_ceny" and not d["hodnota_v_registru"])
print("Dodatky se změnou ceny vyčtenou z textu a s hodnotou v registru:", sum(vysl.values()))
for k, v in vysl.most_common():
    print(f"  {k}: {v}")
print(f"(dalších {bez} dodatků má cenu z textu, ale v registru hodnotu nemá – typicky dodatek přiložený k původnímu záznamu)")
print("\nNeshody k ruční kontrole:")
for d in neshody[:KOLIK]:
    print(f"  dodatek {d['id_dodatku']} (smlouva {d['id_smlouvy']}) č. {d['cislo_dodatku']} | před {float(d['cena_pred']):,.2f} po {float(d['cena_po']):,.2f} "
          f"| změna z textu {float(d['zmena']):+,.2f} | registr {float(d['hodnota_v_registru']):,.2f} | body {d['body']} | {d['dukaz'][:70]}".replace(",", " "))
