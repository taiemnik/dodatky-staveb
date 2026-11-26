# -*- coding: utf-8 -*-
"""Jak města zveřejňují dodatky ke stavebním smlouvám – struktura záznamů ve stažených měsících.

Odpovídá na otázku „kolik se dá zjistit bez čtení textů“: kolik záznamů-dodatků má vazbu na původní
smlouvu (navazanyZaznam) a kolik má vyplněnou hodnotu. Počítá jen platné záznamy měst se sídlem ORP.
Vstup:  python rs_struktura.py <složka s rs_*.jsonl> <obce.csv>
"""
import csv
import glob
import html
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")
slozka, obce_csv = sys.argv[1], sys.argv[2]


def bezdia(s):
    s = unicodedata.normalize("NFD", html.unescape(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


with open(obce_csv, encoding="utf-8-sig", newline="") as fh:
    OBCE = {r["ico"]: r for r in csv.DictReader(fh, delimiter=";")}
ORP = {i for i, r in OBCE.items() if r["sidlo_orp"] == "1"}
# dodatek ke smlouvě o dílo / stavbě: „dodatek“ + stavební slovo v předmětu
RE_DILO = re.compile(r"smlouv\w* o dilo|\bsod\b|stavb|stavebn|rekonstrukc|oprav|revitalizac|zateplen|chodnik|komunikac|kanalizac")
RE_NE = re.compile(r"najem|najmu|pacht|vypujc|bremen|dotac|prispev|pojist|uver|servis|licenc|projektov|dokumentac|dozor")

po_mesici = defaultdict(Counter)
mesta = defaultdict(Counter)
for soubor in sorted(glob.glob(os.path.join(slozka, "rs_*.jsonl"))):
    m = os.path.basename(soubor)[3:10]
    with open(soubor, encoding="utf-8") as fh:
        for radek in fh:
            r = json.loads(radek)
            if r["platny"] != "1":
                continue
            mesto = next((s["ico"] for s in r["strany"] if s["ico"] in ORP), None)
            if not mesto:
                continue
            pn = bezdia(r["predmet"])
            if not re.search(r"dodat(ek|ku|kem|ky)", pn) or not RE_DILO.search(pn) or RE_NE.search(pn):
                continue
            c = po_mesici[m]
            c["dodatku"] += 1
            c["s_vazbou"] += bool(r["navaz"])
            ma_hodnotu = bool(r["bez"] or r["s"]) and float(r["bez"] or r["s"]) != 0
            c["s_hodnotou"] += ma_hodnotu
            c["s_vazbou_i_hodnotou"] += bool(r["navaz"]) and ma_hodnotu
            mesta[mesto]["dodatku"] += 1
            mesta[mesto]["s_vazbou"] += bool(r["navaz"])

print("| měsíc | záznamů-dodatků ke stavebním smlouvám (města ORP) | s vazbou na původní smlouvu | s vyplněnou hodnotou | obojí |")
print("|---|---|---|---|---|")
S = Counter()
for m in sorted(po_mesici):
    c = po_mesici[m]
    S.update(c)
    print(f"| {m} | {c['dodatku']} | {c['s_vazbou']/c['dodatku']*100:.0f} % | {c['s_hodnotou']/c['dodatku']*100:.0f} % | {c['s_vazbou_i_hodnotou']/c['dodatku']*100:.0f} % |")
print(f"| celkem | {S['dodatku']} | {S['s_vazbou']/S['dodatku']*100:.0f} % | {S['s_hodnotou']/S['dodatku']*100:.0f} % | {S['s_vazbou_i_hodnotou']/S['dodatku']*100:.0f} % |")

# kázeň po městech: kolik měst vazbu používá vždy / někdy / nikdy (jen města s 5+ dodatky)
vic = {i: c for i, c in mesta.items() if c["dodatku"] >= 5}
vzdy = sum(1 for c in vic.values() if c["s_vazbou"] == c["dodatku"])
nikdy = sum(1 for c in vic.values() if c["s_vazbou"] == 0)
print(f"\nMěst s 5+ dodatky ve stažených měsících: {len(vic)} | vazbu vyplní vždy: {vzdy} | nikdy: {nikdy} | někdy: {len(vic)-vzdy-nikdy}")
print(f"Měst se sídlem ORP s aspoň jedním takovým dodatkem: {len(mesta)} z {len(ORP)}")
