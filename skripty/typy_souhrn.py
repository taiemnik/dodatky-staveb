# -*- coding: utf-8 -*-
"""Standard a extrémy podle typu stavby: medián, průměr, směrodatná odchylka, běžné pásmo a odlehlé smlouvy.

Standard  = běžné pásmo změny ceny ve skupině (dolní a horní čtvrtina, medián) – počítá se přes VŠECHNY
            smlouvy skupiny včetně těch beze změny, protože i „nic se nezměnilo“ je výsledek.
Extrém    = smlouva nad horní hradbou své skupiny: horní čtvrtina + 1,5násobek rozpětí čtvrtin (Tukey).
            U skupiny pod 8 smluv se použije hradba celého souboru. Hradba je nejméně +10 %,
            aby se u skupin, kde se skoro nic nemění, nestal extrémem každý drobný dodatek.
Vstup:    python typy_souhrn.py <složka s retezy.csv> [rok do=2024] [práh ceny=0] [jen_nahodne: cesta k vzorek.csv]
"""
import csv
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))      # typy.py leží vedle (režim -I složku skriptu nepřidá)
from typy import SEZNAM_DRUHU, SEZNAM_POVAH, druh, povaha     # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
S = Path(sys.argv[1])
ROK_DO = sys.argv[2] if len(sys.argv) > 2 else "2024"
PRAH = float(sys.argv[3]) if len(sys.argv) > 3 else 0
VZOREK = sys.argv[4] if len(sys.argv) > 4 else ""
MIN_HRADBA = 10.0


def nacti(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


R = [r for r in nacti(S / "retezy.csv") if r["podpis"][:4] <= ROK_DO and float(r["cena_puvodni"]) >= PRAH]
if VZOREK:                                                    # jen náhodně vylosované smlouvy (bez velkých přidaných navíc);
    nah = {r["id_hlidac"] for r in nacti(VZOREK) if r["vyber"] == "nahodny"}   # stavební jsou všechny – vzorek je z kohorty
    R = [r for r in R if r["id"] in nah]
else:
    R = [r for r in R if r["stavba"] == "1"]
uniq = {}
for r in R:                                                   # tatáž smlouva zveřejněná dvakrát -> jednou
    k = (r["dodavatel"], r["podpis"], round(float(r["cena_puvodni"])))
    if k not in uniq or int(r["n_dodatku"]) > int(uniq[k]["n_dodatku"]):
        uniq[k] = r
R = [r for r in uniq.values() if int(r["n_neurcenych"]) == 0]  # jen smlouvy s jistou cenou
for r in R:
    r["z"], r["druh"], r["povaha"] = float(r["zmena_pct"]), druh(r["predmet"]), povaha(r["predmet"])


def kv(x, q):
    x = sorted(x)
    k = (len(x) - 1) * q
    a, b = int(k), min(int(k) + 1, len(x) - 1)
    return x[a] + (x[b] - x[a]) * (k - a)


def hradba(z):
    return max(kv(z, .75) + 1.5 * (kv(z, .75) - kv(z, .25)), MIN_HRADBA)


H_VSE = hradba([r["z"] for r in R])
HL = ("| skupina | smluv | cena se změnila | medián | průměr | směr. odchylka | běžné pásmo (čtvrtiny) | medián změněných | nejvíc | hradba | extrémů |\n"
      "|---|---|---|---|---|---|---|---|---|---|---|")


def radek(nazev, rr):
    z = [r["z"] for r in rr]
    if len(z) < 3:
        return f"| {nazev} | {len(z)} | – | – | – | – | – | – | – | – | – |"
    zm = [x for x in z if abs(x) > 0.005]
    h = hradba(z) if len(z) >= 8 else H_VSE
    for r in rr:
        r["hradba"], r["extrem"] = h, r["z"] > h
    f = lambda x: f"{x:+.1f}".replace(".", ",")
    return (f"| {nazev} | {len(z)} | {len(zm)/len(z)*100:.0f} % | {f(st.median(z))} | {f(st.mean(z))} | {st.pstdev(z):.1f} | "
            f"{f(kv(z,.25))} až {f(kv(z,.75))} | {f(st.median(zm)) if zm else '–'} | {f(max(z))} | {f(h)}{'' if len(z)>=8 else '*'} | "
            f"{sum(1 for r in rr if r['extrem'])} |").replace(".", ",")


print(f"Smluv s jistou cenou: {len(R)} | hradba celého souboru {H_VSE:+.1f} %\n")
print(HL)
print(radek("Celkem", R))
for nazev, klic, poradi in (("DRUH STAVBY", "druh", SEZNAM_DRUHU), ("POVAHA PRACÍ", "povaha", SEZNAM_POVAH)):
    print(f"\n{nazev}\n{HL}")
    sk = defaultdict(list)
    for r in R:
        sk[r[klic]].append(r)
    for k in poradi:
        if sk[k]:
            print(radek(k, sk[k]))
print("\n(* skupina pod 8 smluv: použita hradba celého souboru)")

# extrémy podle hradby DRUHU (druhé kolo výše přepsalo hradbu povahou -> spočítat znovu podle druhu)
sk = defaultdict(list)
for r in R:
    sk[r["druh"]].append(r)
for k, rr in sk.items():
    h = hradba([r["z"] for r in rr]) if len(rr) >= 8 else H_VSE
    for r in rr:
        r["hradba"], r["extrem"] = h, r["z"] > h
ex = sorted([r for r in R if r["extrem"]], key=lambda r: -r["z"])
print(f"\nEXTRÉMY nad hradbou svého druhu stavby: {len(ex)} z {len(R)} smluv")
for r in ex:
    print(f"  {r['z']:+6.1f} % (hradba {r['hradba']:+.1f}) | {r['druh']} · {r['povaha']} | {float(r['cena_puvodni'])/1e6:.2f} -> {float(r['cena_konecna'])/1e6:.2f} mil. | "
          f"dodatků {r['n_dodatku']} | {r['podpis'][:4]} | {r['predmet'].replace('Smlouva o dílo - ','')[:62]} | {r['odkaz']}".replace(".", ",", 0))
