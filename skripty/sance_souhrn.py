# -*- coding: utf-8 -*-
"""Šance na nárůst ceny – tři měřítka vedle sebe: procenta, koruny, velikost zakázky.

Proč tři:  u zakázky za 1 mil. Kč je +300 tis. Kč „abnormálních“ 30 %, ale může jít jen o rozšířený chodník.
           U zakázky za 50 mil. Kč je 30 % patnáct milionů – tam bylo něco špatně. A naopak: +8 % na
           stomilionové stavbě procentem nevyčnívá, a přitom je to osm milionů.
Měřítka:   % ............ podíl smluv s nárůstem 10 % / 20 % (anomálie) / 30 % a víc (abnormální)
           Kč ........... podíl smluv s nárůstem o PRAH_KC a víc (výchozí 1 mil. Kč bez DPH)
           obojí ........ čtyři pole: běžné · velké % a málo korun („drobné rozšíření“) ·
                          málo % a hodně korun („tichý nárůst“) · velké % i koruny („zásadní“)
Vstup:     python sance_souhrn.py <složka s retezy.csv> [rok do=2024] [práh ceny=0] [vzorek.csv] [obce.csv] [nahodne|vse]
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from typy import SEZNAM_DRUHU, SEZNAM_POVAH, druh, povaha     # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
S = Path(sys.argv[1])
ROK_DO = sys.argv[2] if len(sys.argv) > 2 else "2024"
PRAH = float(sys.argv[3]) if len(sys.argv) > 3 else 0
VZOREK = sys.argv[4] if len(sys.argv) > 4 else ""
OBCE_CSV = sys.argv[5] if len(sys.argv) > 5 else ""
VYBER = sys.argv[6] if len(sys.argv) > 6 else "nahodne"
PRAH_PCT, PRAH_KC = 20.0, 1_000_000


def nacti(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


R = [r for r in nacti(S / "retezy.csv") if r["podpis"][:4] <= ROK_DO and float(r["cena_puvodni"]) >= PRAH]
kat = {}
if VZOREK:
    V = {r["id_hlidac"]: r for r in nacti(VZOREK)}
    obce = {r["ico"]: r for r in nacti(OBCE_CSV)} if OBCE_CSV else {}
    R = [r for r in R if r["id"] in V and (VYBER == "vse" or V[r["id"]]["vyber"] == "nahodny")]
    kat = {i: obce.get(v["mesto_ico"], {}).get("kategorie", "?") for i, v in V.items()}
else:
    R = [r for r in R if r["stavba"] == "1"]
uniq = {}
for r in R:
    k = (r["dodavatel"], r["podpis"], round(float(r["cena_puvodni"])))
    if k not in uniq or int(r["n_dodatku"]) > int(uniq[k]["n_dodatku"]):
        uniq[k] = r
R = [r for r in uniq.values() if int(r["n_neurcenych"]) == 0]
for r in R:
    r["b"], r["z"] = float(r["cena_puvodni"]), float(r["zmena_pct"])
    r["kc"] = float(r["cena_konecna"]) - r["b"]


def pasmo(b):
    for h, n in ((2e6, "do 2 mil. Kč"), (5e6, "2–5 mil. Kč"), (20e6, "5–20 mil. Kč"), (1e15, "20 mil. Kč a víc")):
        if b < h:
            return n


HL = ("| skupina | smluv | nárůst 10 %+ | 20 %+ (anomálie) | 30 %+ (abnormální) | nárůst 1 mil. Kč+ | drobné rozšíření | tichý nárůst | zásadní |\n"
      "|---|---|---|---|---|---|---|---|---|")


def radek(nazev, rr):
    n = len(rr)
    if n < 3:
        return f"| {nazev} | {n} | málo smluv | | | | | | |"
    p = lambda k: f"{k} ({k/n*100:.0f} %)"
    velke_pct = lambda r: r["z"] >= PRAH_PCT
    velke_kc = lambda r: r["kc"] >= PRAH_KC
    return (f"| {nazev} | {n} | {p(sum(r['z']>=10 for r in rr))} | {p(sum(r['z']>=20 for r in rr))} | {p(sum(r['z']>=30 for r in rr))} | "
            f"{p(sum(velke_kc(r) for r in rr))} | {p(sum(velke_pct(r) and not velke_kc(r) for r in rr))} | "
            f"{p(sum(velke_kc(r) and not velke_pct(r) for r in rr))} | {p(sum(velke_pct(r) and velke_kc(r) for r in rr))} |")


def tabulka(titul, klic, poradi):
    sk = defaultdict(list)
    for r in R:
        sk[klic(r)].append(r)
    print(f"\n{titul}\n{HL}")
    for k in poradi:
        if sk.get(k):
            print(radek(k, sk[k]))


print(f"Smluv s jistou cenou: {len(R)} | anomálie = nárůst {PRAH_PCT:.0f} % a víc | korunový práh {PRAH_KC/1e6:.0f} mil. Kč bez DPH")
print(HL)
print(radek("Celkem", R))
tabulka("VELIKOST ZAKÁZKY (původní cena bez DPH)", lambda r: pasmo(r["b"]), ["do 2 mil. Kč", "2–5 mil. Kč", "5–20 mil. Kč", "20 mil. Kč a víc"])
if kat:
    tabulka("TYP MĚSTA", lambda r: kat.get(r["id"], "?"), ["statutární město", "obec III. typu", "obec II. typu"])
tabulka("POVAHA PRACÍ", lambda r: povaha(r["predmet"]), SEZNAM_POVAH)
tabulka("DRUH STAVBY", lambda r: druh(r["predmet"]), SEZNAM_DRUHU)
print("\nSloupce „drobné rozšíření“ = 20 %+ a pod 1 mil. Kč · „tichý nárůst“ = pod 20 % a 1 mil. Kč+ · „zásadní“ = 20 %+ i 1 mil. Kč+")
