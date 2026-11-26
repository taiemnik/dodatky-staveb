# -*- coding: utf-8 -*-
"""Odhad za ČR z náhodného vzorku: kolik stavebních smluv měst má dodatek a o kolik se mění cena.

Spojí vzorek (vzorek.csv z vzorek_priprav.py) s řetězy vytěženými z textů (retezy.csv z kop_retezy.py).
Celostátní odhad se počítá JEN z náhodně vylosovaných smluv; velké smlouvy přidané navíc se ukazují zvlášť.
U podílů uvádí 95% interval spolehlivosti (Wilson), u mediánu interval z převzorkování (bootstrap).
Vstup:  python vzorek_souhrn.py <složka vzorku>
"""
import csv
import math
import random
import statistics as st
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
S = Path(sys.argv[1])


def nacti(n):
    with open(S / n, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


V = {r["id_hlidac"]: r for r in nacti("vzorek.csv") if r["id_hlidac"]}
R = {r["id"]: r for r in nacti("retezy.csv")}
print(f"ve vzorku {len(V)} smluv, řetěz složen u {sum(1 for i in V if i in R)}")


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 2
    p = k / n
    d = 1 + z * z / n
    s = p + z * z / (2 * n)
    o = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (s - o) / d * 100, (s + o) / d * 100


def boot_median(x, B=4000):
    if len(x) < 5:
        return float("nan"), float("nan")
    random.seed(1)
    m = sorted(st.median(random.choices(x, k=len(x))) for _ in range(B))
    return m[int(0.025 * B)], m[int(0.975 * B)]


def popis(nazev, ids):
    rr = [R[i] for i in ids if i in R]
    n = len(rr)
    if not n:
        print(f"\n{nazev}: žádná data")
        return
    sd = [r for r in rr if int(r["n_dodatku"]) > 0]
    jiste = [r for r in rr if int(r["n_neurcenych"]) == 0]
    zm = [float(r["zmena_pct"]) for r in jiste if abs(float(r["zmena_pct"])) > 0.005]
    vse = [float(r["zmena_pct"]) for r in jiste]
    a, b = wilson(len(sd), n)
    c, d = wilson(len(zm), len(jiste))
    print(f"\n{nazev}: {n} smluv")
    print(f"  s aspoň jedním dodatkem: {len(sd)} = {len(sd)/n*100:.0f} % (95% interval {a:.0f}–{b:.0f} %)")
    print(f"  cena neurčena (dodatek nešel vyčíst): {n-len(jiste)}")
    print(f"  cena se změnila: {len(zm)} z {len(jiste)} = {len(zm)/max(len(jiste),1)*100:.0f} % (95% interval {c:.0f}–{d:.0f} %)")
    if zm:
        lo, hi = boot_median(zm)
        q = sorted(zm)
        print(f"  změna u změněných: medián {st.median(zm):+.1f} % (interval {lo:+.1f} až {hi:+.1f}), průměr {st.mean(zm):+.1f} %,"
              f" rozpětí {q[0]:+.1f} až {q[-1]:+.1f} %, zdražilo {sum(1 for x in zm if x>0)} / zlevnilo {sum(1 for x in zm if x<0)}")
    print(f"  změna přes všechny smlouvy: medián {st.median(vse):+.1f} %, průměr {st.mean(vse):+.1f} %")
    kor = sum(float(r["cena_konecna"]) for r in jiste) / sum(float(r["cena_puvodni"]) for r in jiste) - 1
    print(f"  korunově (součet konečných / součet původních cen): {kor*100:+.1f} %")
    print("  způsob zveřejnění dodatku:", dict(Counter(
        "navazany zaznam" if int(r["n_navazanych"]) else "priloha k puvodnimu zaznamu" for r in sd)))
    # kolik z toho by viděla lehká metoda (jen metadata z exportu)
    leh = sum(1 for i in ids if i in R and V[i]["ma_dodatek"] == "1")
    print(f"  dodatek viděla i lehká metoda nad staženými měsíci: {leh} z {len(sd)}")


nah = [i for i, r in V.items() if r["vyber"] == "nahodny"]
popis("NÁHODNÝ VZOREK (odhad za města-sídla ORP, smlouvy z roku 2023 nad 1 mil. Kč bez DPH)", nah)
popis("Z toho do 5 mil. Kč", [i for i in nah if float(V[i]["cena_puvodni"]) < 5e6])
popis("Z toho 5 mil. Kč a víc", [i for i in nah if float(V[i]["cena_puvodni"]) >= 5e6])
popis("VELKÉ SMLOUVY (50+ mil. Kč, všechny z kohorty)", [i for i, r in V.items() if float(r["cena_puvodni"]) >= 5e7])
