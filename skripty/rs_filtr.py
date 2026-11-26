# -*- coding: utf-8 -*-
"""Proudový filtr měsíčního exportu Registru smluv (otevřená data data.smlouvy.gov.cz).

Co dělá:  čte XML ze standardního vstupu (curl ... | python rs_filtr.py ...), nic velkého neukládá.
          Nechá si jen záznamy, kde je některá smluvní strana obec (IČO ze seznamu obcí),
          a zapíše je po řádcích jako JSON. K tomu spočítá strukturu celého měsíce.
Proč:     export má 100–190 MB za měsíc a disk je skoro plný; záznamy obcí jsou jen zlomek.
Vstup:    python rs_filtr.py <značka RRRR_MM> <obce.csv> <výstupní složka>   (XML na stdin)
Výstup:   <složka>/rs_<značka>.jsonl   – záznamy obcí (jedna verze záznamu = jeden řádek)
          <složka>/rs_<značka>.stat.json – počty za celý měsíc
Soubor se přejmenuje na konečný název až po dočtení celého XML (useknutý přenos tak nezůstane nepoznán).
"""
import csv
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

NS = "{http://portal.gov.cz/rejstriky/ISRS/1.2/}"
znacka, obce_csv, slozka = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(slozka, exist_ok=True)


def ico8(x):
    """IČO na 8 číslic s nulami zleva; nečíselné -> ''."""
    x = re.sub(r"\D", "", x or "")
    return x.zfill(8) if x else ""


with open(obce_csv, encoding="utf-8-sig", newline="") as f:
    OBCE = {r["ico"] for r in csv.DictReader(f, delimiter=";") if r["ico"]}


def t(el, jmeno):
    """Text přímého potomka (nebo '')."""
    x = el.find(NS + jmeno)
    return (x.text or "").strip() if x is not None else ""


stat = {"znacka": znacka, "zaznamu": 0, "platnych": 0, "s_navazanym": 0, "predmet_dodatek": 0,
        "priloha_dodatek": 0, "obecnich": 0, "obecnich_s_navazanym": 0}
RE_DOD = re.compile(r"dodat", re.I)
cil = os.path.join(slozka, f"rs_{znacka}.jsonl")
docasny = f"{cil}.part{os.getpid()}"      # jedinečný název: dva souběžné přenosy téhož měsíce si nepřepíšou práci

with open(docasny, "w", encoding="utf-8") as out:
    # iterparse čte postupně; po zpracování záznam z paměti uvolníme (elem.clear)
    for _, elem in ET.iterparse(sys.stdin.buffer, events=("end",)):
        if elem.tag != NS + "zaznam":
            continue
        stat["zaznamu"] += 1
        sml = elem.find(NS + "smlouva")
        ident = elem.find(NS + "identifikator")
        platny = t(elem, "platnyZaznam")
        if platny == "1":
            stat["platnych"] += 1
        navaz = t(sml, "navazanyZaznam") if sml is not None else ""
        predmet = t(sml, "predmet") if sml is not None else ""
        prilohy = [t(p, "nazevSouboru") for p in elem.iter(NS + "priloha")]
        if navaz:
            stat["s_navazanym"] += 1
        if RE_DOD.search(predmet):
            stat["predmet_dodatek"] += 1
        if any(RE_DOD.search(p) for p in prilohy):
            stat["priloha_dodatek"] += 1

        # smluvní strany: „subjekt“ = kdo záznam vložil, „smluvniStrana“ = ostatní
        strany = []
        if sml is not None:
            s = sml.find(NS + "subjekt")
            if s is not None:
                strany.append({"role": "subjekt", "ico": ico8(t(s, "ico")), "nazev": t(s, "nazev"),
                               "utvar": t(s, "utvar"), "platce": t(s, "platce")})
            for s in sml.findall(NS + "smluvniStrana"):
                strany.append({"role": "strana", "ico": ico8(t(s, "ico")), "nazev": t(s, "nazev"),
                               "prijemce": t(s, "prijemce")})
        if any(x["ico"] in OBCE for x in strany):
            stat["obecnich"] += 1
            if navaz:
                stat["obecnich_s_navazanym"] += 1
            out.write(json.dumps({
                "ids": t(ident, "idSmlouvy"), "idv": t(ident, "idVerze"),
                "cas": t(elem, "casZverejneni"), "platny": platny,
                "strany": strany, "predmet": predmet,
                "datum": t(sml, "datumUzavreni"), "cislo": t(sml, "cisloSmlouvy"),
                "bez": t(sml, "hodnotaBezDph"), "s": t(sml, "hodnotaVcetneDph"),
                "cena_neuvedena": t(sml, "cenaNeuvedena"), "navaz": navaz, "prilohy": prilohy,
            }, ensure_ascii=False) + "\n")
        elem.clear()

os.replace(docasny, cil)
with open(os.path.join(slozka, f"rs_{znacka}.stat.json"), "w", encoding="utf-8") as f:
    json.dump(stat, f, ensure_ascii=False)
print(json.dumps(stat, ensure_ascii=False))
