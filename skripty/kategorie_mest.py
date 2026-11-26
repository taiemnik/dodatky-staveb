# -*- coding: utf-8 -*-
"""Doplní do data/obce.csv sloupec „kategorie“: statutární město · obec III. typu · obec II. typu · obec I. typu · Praha.

Proč:   srovnávat má smysl jen města stejného typu úřadu. Malé obce (I. typ) a Praha se do rozboru neberou.
Zdroje: - obce II. typu = obce s pověřeným obecním úřadem: číselník ČSÚ č. 61 (CISPOU). Kód pověřeného
          úřadu začíná kódem obvodu ORP, název je název sídelní obce -> párujeme podle ORP + názvu.
        - obce III. typu = sídla obcí s rozšířenou působností (sloupec sidlo_orp)
        - statutární města: § 4 odst. 1 zákona č. 128/2000 Sb., o obcích (26 měst; ověřeno proti Hlídači státu)
Pozor:  obec III. typu je zároveň i pověřeným úřadem; kategorie je vždy ta NEJVYŠŠÍ (statutární > III. > II. > I.).
Vstup:  python skripty/kategorie_mest.py data/obce.csv data/csu/cispou.csv
        číselník: curl -sS -o data/csu/cispou.csv "https://apl.czso.cz/iSMS/do_cis_export?kodcis=61&typdat=0&cisjaz=203&format=2&separator=%3B"
"""
import csv
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
obce_csv, pou_csv = sys.argv[1], sys.argv[2]
STATUTARNI = {"Brno", "České Budějovice", "Děčín", "Frýdek-Místek", "Havířov", "Hradec Králové", "Chomutov",
              "Jablonec nad Nisou", "Jihlava", "Karlovy Vary", "Karviná", "Kladno", "Liberec", "Mladá Boleslav", "Most",
              "Olomouc", "Opava", "Ostrava", "Pardubice", "Plzeň", "Prostějov", "Přerov", "Teplice", "Třinec",
              "Ústí nad Labem", "Zlín"}

with open(obce_csv, encoding="utf-8-sig", newline="") as f:
    O = list(csv.DictReader(f, delimiter=";"))
with open(pou_csv, encoding="utf-8-sig", newline="") as f:
    POU = [r for r in csv.DictReader(f) if r["admnepo"].startswith("9999") and r["chodnota"] != "10000"]   # platné, bez Prahy
print("platných pověřených úřadů v číselníku:", len(POU))

podle = {(r["orp_id"], r["nazev"]): r for r in O}
sidla_pou, nenalezeno = set(), []
for p in POU:
    k = (f"orp:{p['chodnota'][:4]}", p["text"])
    if k in podle:
        sidla_pou.add(podle[k]["ico"])
    else:
        nenalezeno.append(p["text"])
print("spárováno se seznamem obcí:", len(sidla_pou), "| nespárováno:", nenalezeno)

for r in O:
    if r["nazev"] == "Praha":
        r["kategorie"] = "Praha"
    elif r["sidlo_orp"] == "1" and r["nazev"] in STATUTARNI:
        r["kategorie"] = "statutární město"
    elif r["sidlo_orp"] == "1":
        r["kategorie"] = "obec III. typu"
    elif r["ico"] in sidla_pou:
        r["kategorie"] = "obec II. typu"
    else:
        r["kategorie"] = "obec I. typu"
pole = [k for k in O[0].keys() if k != "kategorie"] + ["kategorie"]
with open(obce_csv, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=pole, delimiter=";")
    w.writeheader()
    w.writerows(O)
c = Counter(r["kategorie"] for r in O)
print("kategorie:", dict(c))
assert c["statutární město"] == 26, "statutárních měst má být 26"
assert c["statutární město"] + c["obec III. typu"] == 205, "sídel ORP má být 205"
