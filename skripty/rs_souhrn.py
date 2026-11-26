# -*- coding: utf-8 -*-
"""Vrstvené souhrny nad kohortou stavebních smluv (výstup rs_kohorta.py).

Pohledy: celek · velikost zakázky · velikost města · kraj · rozdělení změn (hrany 15 / 30 / 50 %) · vybrané město.
U každé skupiny: počet smluv, podíl s dodatkem, a u smluv se zjistitelnou změnou ceny medián, průměr, kvartily.
Medián = typická zakázka; průměr táhnou výjimky; „korunově“ = součet konečných cen / součet původních − 1.
Vstup:  python rs_souhrn.py <kohorta.csv> [IČO města k vyznačení]
"""
import csv
import statistics as st
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
soubor = sys.argv[1]
MOJE = sys.argv[2] if len(sys.argv) > 2 else ""

with open(soubor, encoding="utf-8-sig", newline="") as f:
    R = list(csv.DictReader(f, delimiter=";"))
for r in R:
    r["B"] = float(r["cena_puvodni"])
    r["z"] = float(r["zmena_pct"]) if r["zmena_pct"] != "" else None
    r["F"] = float(r["cena_konecna"]) if r["cena_konecna"] != "" else None
    r["ob"] = float(r["obyvatel"]) if r["obyvatel"] else None


def kvantil(x, q):
    x = sorted(x)
    if not x:
        return None
    k = (len(x) - 1) * q
    a, b = int(k), min(int(k) + 1, len(x) - 1)
    return x[a] + (x[b] - x[a]) * (k - a)


def pasmo_ceny(B):
    for hran, nazev in ((2e6, "1–2 mil."), (5e6, "2–5 mil."), (10e6, "5–10 mil."), (20e6, "10–20 mil."),
                        (50e6, "20–50 mil."), (1e12, "50+ mil.")):
        if B < hran:
            return nazev


def pasmo_mesta(o):
    if o is None:
        return "?"
    for hran, nazev in ((10e3, "do 10 tis."), (20e3, "10–20 tis."), (30e3, "20–30 tis."), (50e3, "30–50 tis."),
                        (100e3, "50–100 tis."), (1e9, "100+ tis.")):
        if o < hran:
            return nazev


def fm(x, d=1):
    return "–" if x is None else f"{x:.{d}f}".replace(".", ",")


HLAV = ("| skupina | smluv | s dodatkem | % | se zjištěnou změnou ceny | medián změny % | průměr % | Q1 | Q3 | P90 "
        "| podíl zdražení | korunově % |\n|---|---|---|---|---|---|---|---|---|---|---|---|")


def radek(nazev, rr):
    n = len(rr)
    sd = [r for r in rr if r["ma_dodatek"] == "1"]
    sc = [r for r in rr if r["z"] is not None]
    z = [r["z"] for r in sc]
    kor = (sum(r["F"] for r in sc) / sum(r["B"] for r in sc) - 1) * 100 if sc else None
    zdr = sum(1 for x in z if x > 0.05) / len(z) * 100 if z else None
    return (f"| {nazev} | {n} | {len(sd)} | {fm(len(sd)/n*100 if n else None)} | {len(sc)} | {fm(kvantil(z,.5))} | "
            f"{fm(st.mean(z) if z else None)} | {fm(kvantil(z,.25))} | {fm(kvantil(z,.75))} | {fm(kvantil(z,.9))} | "
            f"{fm(zdr,0)} | {fm(kor)} |")


def tabulka(titul, klic, poradi=None, min_n=1):
    sk = defaultdict(list)
    for r in R:
        sk[klic(r)].append(r)
    print(f"\n### {titul}\n\n{HLAV}")
    for k in (poradi or sorted(sk, key=lambda k: -len(sk[k]))):
        if k in sk and len(sk[k]) >= min_n:
            print(radek(k, sk[k]))


print(f"## Kohorta: {len(R)} smluv, {len({r['mesto_ico'] for r in R})} měst\n\n{HLAV}")
print(radek("Celkem", R))
tabulka("Podle původní ceny (bez DPH)", lambda r: pasmo_ceny(r["B"]),
        ["1–2 mil.", "2–5 mil.", "5–10 mil.", "10–20 mil.", "20–50 mil.", "50+ mil."])
tabulka("Podle velikosti města (obyvatelé)", lambda r: pasmo_mesta(r["ob"]),
        ["do 10 tis.", "10–20 tis.", "20–30 tis.", "30–50 tis.", "50–100 tis.", "100+ tis."])
tabulka("Podle kraje", lambda r: r["kraj"])

# rozdělení změn: kde se zakázky hromadí vůči zákonným hranám (15 % de minimis, 30 % souhrnný limit)
z = [r["z"] for r in R if r["z"] is not None]
hrany = [(-1e9, -5, "pod −5 %"), (-5, -0.05, "−5 až 0 %"), (-0.05, 0.05, "beze změny"), (0.05, 5, "0 až 5 %"),
         (5, 10, "5 až 10 %"), (10, 15, "10 až 15 %"), (15, 20, "15 až 20 %"), (20, 30, "20 až 30 %"),
         (30, 50, "30 až 50 %"), (50, 1e9, "nad 50 %")]
print("\n### Rozdělení změny ceny (jen smlouvy se zjištěnou změnou)\n\n| pásmo | smluv | podíl % |\n|---|---|---|")
for a, b, nazev in hrany:
    k = sum(1 for x in z if a <= x < b)
    print(f"| {nazev} | {k} | {fm(k/len(z)*100 if z else None)} |")

# jak města dodatky zveřejňují (ovlivňuje, co jde zjistit bez čtení textů)
nav = sum(1 for r in R if int(r["n_dod_navazanych"]) > 0)
odh = sum(1 for r in R if int(r["n_dod_odhadnutych"]) > 0 and int(r["n_dod_navazanych"]) == 0)
pri = sum(1 for r in R if int(r["n_dod_prilohou"]) > 0 and int(r["n_dod_navazanych"]) == 0 and int(r["n_dod_odhadnutych"]) == 0)
print(f"\nZpůsob zveřejnění dodatku (smluv): navázaný záznam {nav} · samostatný bez vazby {odh} · jen příloha k původnímu záznamu {pri}"
      f" · více verzí bez rozpoznaného dodatku {sum(int(r['vice_verzi_bez_dodatku']) for r in R)}")

if MOJE:
    moje = [r for r in R if r["mesto_ico"] == MOJE]
    print(f"\n### Vybrané město ({moje[0]['mesto'] if moje else MOJE})\n\n{HLAV}")
    print(radek("město", moje))
    for r in sorted(moje, key=lambda r: -r["B"]):
        print(f"- {r['datum']} · {r['B']:,.0f} Kč · dodatků nav/odh/příl {r['n_dod_navazanych']}/{r['n_dod_odhadnutych']}/{r['n_dod_prilohou']}"
              f" · změna {fm(r['z'])} % · {r['predmet'][:80]}".replace(",", " "))
