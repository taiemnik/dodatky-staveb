# -*- coding: utf-8 -*-
"""Hledání smluv na veřejném webu Hlídače státu -> CSV.

Co dělá:  pošle dotaz v dotazovacím jazyce Hlídače (stejný jako v napojení),
          stáhne stránky výsledků curl-em a rozebere je na řádky.
Proč:     čísla mají jít ze skriptu, ne přes ruční přepis z chatu.
Vstup:    python hs_hledej.py <výstup.csv> "<dotaz>" [stran=1] [řazení]
          řazení: číslo podle webu Hlídače (prázdné = relevance)
Výstup:   CSV (středník, UTF-8 s BOM): id;podpis;zverejneno;platce;dodavatel;cena_s_dph;predmet;dotaz
Stahuje curl (Python na pracovním PC neprojde TLS). Mezi dotazy pauza.
Zdroj dat: Hlídač státu / Registr smluv (CC BY).
"""
import csv
import html
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

WEB = "https://www.hlidacstatu.cz/HledatSmlouvy?"
UA = "dodatky-staveb-pilot/0.1"          # poctivé označení klienta; Hlídač na něj odpovídá normálně
PAUZA = 1.5


def cisti(x):
    """HTML úryvek -> čistý text na jednom řádku."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()


def cena(txt):
    """'32 694 700 Kč' -> 32694700.0 ; neznámé -> ''."""
    m = re.search(r"-?[\d\s ]+(?:,\d+)?", txt)
    if not m or not re.search(r"\d", m.group(0)):
        return ""
    return float(re.sub(r"[\s ]", "", m.group(0)).replace(",", "."))


def stahni(url):
    r = subprocess.run(["curl", "-sS", "-L", "-m", "90", "-A", UA, url], capture_output=True)
    time.sleep(PAUZA)
    return r.stdout.decode("utf-8", "replace")


def rozeber(s):
    """Vrátí (celkem_text, řádky) z jedné stránky výsledků."""
    hlava = cisti(s[:120000])
    m = re.search(r"Nalezen[oaéy]?[^.]{0,90}", hlava)
    celkem = m.group(0) if m else "?"
    telo = s[s.find("hs-results"):]
    radky = []
    for a, b in re.findall(r'<tr class="bg first">(.*?)</tr>\s*<tr class="bg last">(.*?)</tr>', telo, flags=re.S):
        i = re.search(r"/Detail/(\d+)", a)
        tds = [cisti(t) for t in re.findall(r"<td[^>]*>(.*?)</td>", a, flags=re.S)]
        g = lambda k: tds[k] if len(tds) > k else ""
        predmet = cisti(b).split("| Obor smlouvy")[0].strip()
        radky.append([i.group(1) if i else "", g(1), g(2), g(3), g(4), cena(g(5)), predmet])
    return celkem, radky


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cil, dotaz = Path(sys.argv[1]), sys.argv[2]
    stran = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    razeni = sys.argv[4] if len(sys.argv) > 4 else ""
    novy = not cil.exists()
    vse = 0
    with open(cil, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        if novy:
            w.writerow(["id", "podpis", "zverejneno", "platce", "dodavatel", "cena_s_dph", "predmet", "dotaz"])
        for p in range(1, stran + 1):
            par = {"Q": dotaz, "Page": p}
            if razeni:
                par["Order"] = razeni
            celkem, radky = rozeber(stahni(WEB + urllib.parse.urlencode(par)))
            if p == 1:
                print("DOTAZ:", dotaz, "|", celkem)
            for r in radky:
                w.writerow(r + [dotaz])
            vse += len(radky)
            if not radky:
                break
    print("   řádků:", vse)


if __name__ == "__main__":
    main()
