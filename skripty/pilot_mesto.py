# -*- coding: utf-8 -*-
"""Pilot: řetěz „smlouva o dílo -> dodatky“ pro jedno město z veřejných stránek Hlídače státu.

Co dělá (vše s mezipamětí, takže jde pustit znovu):
  A) ke každé smlouvě ze seznamu (CSV z hs_hledej.py) stáhne stránku detailu a vytáhne:
     ID smlouvy, ID verze, data, číslo smlouvy, ceny, strany, obory, přílohy a HISTORII VERZÍ
     (dodatek přiložený k původnímu záznamu = nová verze záznamu)
  B) k ID smlouvy dohledá samostatné záznamy dodatků (dotaz navazanyZaznam:<ID smlouvy>)
  C) stáhne detaily těchto dodatků
  D) uloží čistý text příloh, které jsou dodatkem (podle názvu souboru nebo typu záznamu)
Vstup:   python pilot_mesto.py <zaklad.csv> <výstupní složka>
Výstup:  <složka>/detaily.jsonl (jeden záznam = jeden řádek), <složka>/vazby.csv, <složka>/texty/*.txt
Zdroj:   Hlídač státu / Registr smluv (CC BY).
Stahuje se dávkově: jeden proces curl na celou dávku adres (spuštění procesu na pracovním PC trvá
několik sekund), s omezením tempa, ať server nezatěžujeme.
"""
import csv
import html
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

WEB = "https://www.hlidacstatu.cz"
UA = "dodatky-staveb-pilot/0.1"          # poctivé označení klienta; Hlídač na něj odpovídá normálně
TEMPO = "40/m"            # nejvýš 40 dotazů za minutu
MAX_SLOV = 12000          # delší přílohy jsou rozpočty a soupisy, ne tělo dodatku
RE_DOD = re.compile(r"dodat", re.I)

sys.stdout.reconfigure(encoding="utf-8")
zaklad, slozka = Path(sys.argv[1]), Path(sys.argv[2])
H, T = slozka / "html", slozka / "texty"
H.mkdir(parents=True, exist_ok=True)
T.mkdir(parents=True, exist_ok=True)
pocet_dotazu = 0


def davka(pary, min_bajtu=2000):
    """Stáhne chybějící stránky jedním procesem curl. pary = [(adresa, soubor v mezipaměti), …]"""
    global pocet_dotazu
    chybi = [(u, c) for u, c in pary if not (c.exists() and c.stat().st_size >= min_bajtu)]
    if not chybi:
        return
    cfg = slozka / "_curl.cfg"
    with open(cfg, "w", encoding="utf-8") as f:
        for u, c in chybi:
            f.write(f'url = "{u}"\noutput = "{c.as_posix()}"\n')
    subprocess.run(["curl", "-sS", "-L", "--max-time", "120", "--retry", "2", "--rate", TEMPO,
                    "-A", UA, "-K", str(cfg)])
    pocet_dotazu += len(chybi)
    print(f"   staženo {len(chybi)} stránek (celkem dotazů {pocet_dotazu})", flush=True)


def nacti(cache):
    if not cache.exists():
        return ""
    return html.unescape(cache.read_text(encoding="utf-8", errors="replace"))


def txt(b):
    """HTML -> text se svislítky mezi prvky (drží pořadí popisek | hodnota)."""
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", b)
    t = re.sub(r"<[^>]+>", "|", t)
    t = re.sub(r"\s+", " ", t)
    return re.sub(r"(\| *)+", "| ", t)


def cislo(x):
    """'28 430 174' -> 28430174.0"""
    x = re.sub(r"[^\d,\-]", "", x or "").replace(",", ".")
    return float(x) if re.search(r"\d", x) else None


def g(vzor, t, k=1):
    m = re.search(vzor, t)
    return m.group(k).strip() if m else ""


def rozeber_detail(s, sid):
    t = txt(s)
    d = {"id": sid, "ids": g(r"ID smlouvy (\d+)", t), "idv": g(r"ID Verze: (\d+)", t),
         "zverejnena": g(r"Zveřejněna \|? ?(\d\d\.\d\d\.\d{4})", t),
         "uzavrena": g(r"Uzavřena (\d\d\.\d\d\.\d{4})", t),
         "cislo": g(r"číslo smlouvy ([^|]*?) ?(?:, existuje|\|)", t),
         "navaz": g(r"Q=idSmlouvy:(\d+)'>související smlouva", s),
         "bez_dph": cislo(g(r"Cena bez DPH: \| ([\d\s ,]+) Kč", t)),
         "s_dph": cislo(g(r"Cena s DPH: \| ([\d\s ,]+) Kč", t)),
         "platce": g(r"Plátce / Objednatel\| ([^|]+)\|", t),
         "platce_ico": g(r"Plátce / Objednatel\|.*?ICO \| (\d+)", t),
         "dodavatel": g(r"Příjemci / Dodavatelé\| ([^|]+)\|", t),
         "dodavatel_ico": g(r"Příjemci / Dodavatelé\|.*?ICO \| (\d+)", t),
         "predmet": g(r"<title>\s*(.*?)\s*- Hlídač státu", s),
         "platna": "Toto je platná smlouva" in t}
    # útvar objednatele (odbor): druhá buňka za názvem; když v ní je PSČ, jde o adresu a útvar chybí
    u = g(r"Plátce / Objednatel\| [^|]+\| ([^|]+)\|", t)
    d["utvar"] = "" if re.search(r"\d{3} ?\d{2}", u) else u
    ob = g(r"Oblasti smlouvy \| (.*?)Jsou oblasti špatně", t)
    d["oblasti"] = [x.strip() for x in re.findall(r"([^|()]+?) \| \(\| najít", ob)]
    # přílohy: každá je ve vlastním bloku s názvem v <h4 title="…">
    d["prilohy"] = []
    for blok in s.split('<div class="bs-callout primary small">')[1:]:
        nazev = g(r'<h4 class="font-monospace" title="([^"]*)"', blok)
        if not nazev:
            continue
        d["prilohy"].append({"nazev": nazev, "hash": g(r"TextSmlouvy/\d+\?hash=([0-9a-fA-F]{64})", blok),
                             "slov": int(g(r"\((\d+) slov\)", blok) or 0),
                             "soubor_id": g(r"smlouvy\.gov\.cz/smlouva/soubor/(\d+)/", blok)})
    # historie verzí téhož záznamu (zneplatněné starší verze)
    pv = g(r"Provázané smlouvy\|(.*?)(?:Toto je seznam smluv|Podobné smlouvy|$)", t)
    d["verze"] = [{"idv": a, "zverejnena": b} for a, b in re.findall(r"Verze (\d+); zveřejněna (\d\d\.\d\d\.\d{4})", pv)]
    return d


def cisty_text(stranka):
    bloky = re.findall(r"<pre[^>]*>(.*?)</pre>", stranka, flags=re.S | re.I)
    telo = max(bloky, key=len) if bloky else re.sub(r"(?is)<(script|style|nav|header|footer).*?</\1>", " ", stranka)
    telo = re.sub(r"(?i)<br\s*/?>", "\n", telo)
    return re.sub(r"<[^>]+>", "", telo).replace("\r", "").strip()


def cache_detail(sid):
    return H / f"d_{sid}.html"


# ---------- běh ----------
with open(zaklad, encoding="utf-8-sig", newline="") as f:
    ids = list(dict.fromkeys(r["id"] for r in csv.DictReader(f, delimiter=";") if r["id"]))
print("smluv v základu:", len(ids), flush=True)

# A) detaily smluv ze seznamu
davka([(f"{WEB}/Detail/{sid}", cache_detail(sid)) for sid in ids])
zaznamy = {}
for sid in ids:
    s = nacti(cache_detail(sid))
    if s:
        zaznamy[sid] = dict(rozeber_detail(s, sid), role="zaklad")
print("A) detailů základu:", len(zaznamy), flush=True)

# A2) PŮVODNÍ cena: aktuální verze záznamu může nést už konečnou cenu (město ji při dodatku přepíše).
#     Proto u záznamů s historií stáhneme nejstarší verzi a cenu vezmeme z ní.
nejstarsi = {sid: min(d["verze"], key=lambda v: int(v["idv"]))["idv"] for sid, d in zaznamy.items() if d["verze"]}
davka([(f"{WEB}/Detail/{idv}", cache_detail(idv)) for idv in nejstarsi.values()])
for sid, idv in nejstarsi.items():
    s = nacti(cache_detail(idv))
    if s:
        p = rozeber_detail(s, idv)
        zaznamy[sid].update({"puvodni_idv": idv, "puvodni_bez_dph": p["bez_dph"], "puvodni_s_dph": p["s_dph"],
                             "puvodni_zverejnena": p["zverejnena"]})
print("A2) nejstarších verzí:", len(nejstarsi), flush=True)

# B) navázané dodatky: dotaz navazanyZaznam:<ID smlouvy>
zakl = [d for d in zaznamy.values() if d["ids"]]
adresa_n = lambda d: f"{WEB}/HledatSmlouvy?" + urllib.parse.urlencode({"Q": f"navazanyZaznam:{d['ids']}"})
davka([(adresa_n(d), H / f"n_{d['ids']}.html") for d in zakl])
vazby = []
for d in zakl:
    s = nacti(H / f"n_{d['ids']}.html")
    telo = s[s.find("hs-results"):]
    for did in dict.fromkeys(re.findall(r'<tr class="bg first">.*?/Detail/(\d+)', telo, flags=re.S)):
        vazby.append((d["ids"], d["id"], did))
print("B) vazeb na dodatky:", len(vazby), flush=True)

# C) detaily dodatků, které ještě nemáme
nove = list(dict.fromkeys(v[2] for v in vazby if v[2] not in zaznamy))
davka([(f"{WEB}/Detail/{sid}", cache_detail(sid)) for sid in nove])
for sid in nove:
    s = nacti(cache_detail(sid))
    if s:
        zaznamy[sid] = dict(rozeber_detail(s, sid), role="dodatek")
print("C) detailů dodatků:", len(nove), flush=True)

# D) texty: u samostatného dodatku všechny kratší přílohy, u původní smlouvy jen přílohy s „dodatek“ v názvu
k_stazeni = []
for d in zaznamy.values():
    d["je_dodatek"] = d["role"] == "dodatek" or bool(d["navaz"]) or bool(RE_DOD.search(d["predmet"]))
    for k, p in enumerate(d["prilohy"], 1):
        if not p["hash"] or p["slov"] == 0 or p["slov"] > MAX_SLOV:
            continue
        if not d["je_dodatek"] and not RE_DOD.search(p["nazev"]):
            continue
        p["text"] = f"{d['id']}_{k}.txt"
        url = f"{WEB}/Home/TextSmlouvy/{d['id']}?hash={p['hash']}"
        k_stazeni.append((url, H / f"t_{d['id']}_{k}.html", T / p["text"], d["id"], p["nazev"]))
davka([(u, c) for u, c, _, _, _ in k_stazeni], min_bajtu=300)
for url, c, cil, sid, nazev in k_stazeni:
    if not cil.exists():
        cil.write_text(f"# zdroj: {url}\n# Hlídač státu / Registr smluv, ID {sid}, příloha: {nazev}\n\n"
                       + cisty_text(nacti(c)), encoding="utf-8")
print("D) textů:", len(k_stazeni), flush=True)

with open(slozka / "detaily.jsonl", "w", encoding="utf-8") as f:
    for d in zaznamy.values():
        f.write(json.dumps(d, ensure_ascii=False) + "\n")
with open(slozka / "vazby.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["ids_zakladu", "id_zakladu", "id_dodatku"])
    w.writerows(vazby)
print("záznamů:", len(zaznamy), "| vazeb:", len(vazby), "| textů:", len(list(T.glob('*.txt'))),
      "| dotazů na web:", pocet_dotazu)
