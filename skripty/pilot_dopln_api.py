# -*- coding: utf-8 -*-
"""Doplnění pilotu (složka s detaily.jsonl, vazby.csv, texty/) přes API Hlídače státu.

Opravuje dvě mezery pilotu z 25. 11. 2026:
  1) NEÚPLNÝ SEZNAM SMLUV. Seznam vznikl hledáním na webu s výchozím řazením, které při stránkování část
     záznamů vynechá (Kopřivnice: 183 ze 197). S přepínačem --dopln-seznam se dotaz ze zaklad.csv projde
     znovu přes API se stabilním řazením a chybějící záznamy se přidají včetně navázaných dodatků.
  2) DODATKY V PŘÍLOHÁCH S JINÝM NÁZVEM. Přílohy původní smlouvy pojmenované „D1.pdf“, „DOD_1_….pdf“ apod.
     pilot nepoznal (hledal jen „dodat“ v názvu). Skript jim dotáhne text a podle jeho začátku rozhodne,
     jestli jde o dodatek (pravidla.py).
Co neumí: API nevrací starší verze záznamu. U přidaných smluv proto nejde ověřit, jestli město cenu
          původního záznamu později nepřepsalo (pole puvodni_* chybí).
Texty příloh zůstávají jen v místní složce data/ (do repa nejdou); zveřejňují se jen odvozená čísla s odkazem.
Vstup:    python -I skripty/pilot_dopln_api.py <složka pilotu> [--dopln-seznam]
Zdroj:    Hlídač státu (CC BY 4.0).
"""
import csv
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hs_api  # noqa: E402
from pravidla import druh_nazvu, over_textem  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
S = Path(sys.argv[1])
DOPLN_SEZNAM = "--dopln-seznam" in sys.argv
T = S / "texty"
T.mkdir(parents=True, exist_ok=True)
MAX_SLOV = 12000                  # delší přílohy jsou rozpočty a soupisy, ne tělo dodatku (stejně jako v pilot_mesto.py)
RE_DOD = re.compile(r"dodat", re.I)
hs_api.PAUZA = 1.5
volani = 0


def api(cesta, parametry=None):
    """Jedno volání; při chybě None (skript pokračuje a chybu vypíše v souhrnu)."""
    global volani
    stav, _, data = hs_api.volej(cesta, parametry)
    volani += 1
    if stav == "429":
        sys.exit("API hlásí vyčerpaný limit (429) – pustit znovu později; hotová část je uložená.")
    return data if stav == "200" and isinstance(data, (dict, list)) else None


def hledej_vse(dotaz):
    """Všechny záznamy dotazu se stabilním řazením (2 = od nejdříve zveřejněných)."""
    nalez, strana = {}, 1
    while True:
        d = api("smlouvy/hledat", {"dotaz": dotaz, "strana": strana, "razeni": 2})
        if not d:
            break
        for r in d.get("results") or []:
            nalez[str(r["id"])] = r
        if strana * 25 >= (d.get("total") or 0):
            break
        strana += 1
    return nalez


def den(x):
    """2023-06-30T00:00:00+02:00 -> 30.06.2023 (tvar, který používá pilot)"""
    return f"{x[8:10]}.{x[5:7]}.{x[0:4]}" if x and len(x) >= 10 else ""


def z_api(r, role):
    """Detail z API -> záznam ve tvaru detaily.jsonl (jako pilot_mesto.rozeber_detail)."""
    ident, pl = r.get("identifikator") or {}, r.get("platce") or {}
    pr = (r.get("prijemce") or [{}])[0] or {}
    d = {"id": str(r["id"]), "ids": str(ident.get("idSmlouvy") or ""), "idv": str(ident.get("idVerze") or r["id"]),
         "zverejnena": den(r.get("casZverejneni")), "uzavrena": den(r.get("datumUzavreni")),
         "cislo": r.get("cisloSmlouvy") or "", "navaz": str(r.get("navazanyZaznam") or ""),
         "bez_dph": r.get("hodnotaBezDph") or None, "s_dph": r.get("hodnotaVcetneDph") or None,
         "platce": pl.get("nazev") or "", "platce_ico": pl.get("ico") or "",
         "dodavatel": pr.get("nazev") or "", "dodavatel_ico": pr.get("ico") or "",
         "predmet": r.get("predmet") or "", "platna": bool(r.get("platnyZaznam")), "utvar": pl.get("utvar") or "",
         "oblasti": [], "verze": [], "role": role, "zdroj_detailu": "api",
         "prilohy": [{"nazev": p.get("nazevSouboru") or "", "hash": "", "slov": int(p.get("wordCount") or 0),
                      "soubor_id": ""} for p in r.get("prilohy") or []]}
    d["je_dodatek"] = role == "dodatek" or bool(d["navaz"]) or bool(RE_DOD.search(d["predmet"]))
    return d


def uloz_texty(d, r):
    """K přílohám záznamu d doplní texty z detailu API r. Vrátí počet nově uložených textů.
    Původní smlouva: jen přílohy, jejichž název vypadá jako dodatek. Samostatný dodatek: všechny kratší přílohy."""
    podle_nazvu = {}
    for p in r.get("prilohy") or []:
        podle_nazvu.setdefault(p.get("nazevSouboru") or "", []).append(p)
    novych = 0
    for k, p in enumerate(d["prilohy"], 1):
        druh = druh_nazvu(p["nazev"])
        if p.get("text") or (not d["je_dodatek"] and not druh):
            continue
        zdroje = podle_nazvu.get(p["nazev"]) or []
        text = (zdroje.pop(0).get("plainTextContent") or "").strip() if zdroje else ""
        if not d["je_dodatek"] and druh != "dodat":
            # „D1“, „DOD_1“: o tom, jestli jde o dodatek, rozhodne začátek textu (None = text není, nejde ověřit)
            p["overeno_textem"] = over_textem(text) if text else None
            if p["overeno_textem"] is False:
                continue
        if not text or not (0 < p["slov"] <= MAX_SLOV):
            continue
        p["text"] = f"{d['id']}_{k}.txt"
        cil = T / p["text"]
        if not cil.exists():
            cil.write_text(f"# zdroj: https://www.hlidacstatu.cz/Detail/{d['id']}\n"
                           f"# Hlídač státu / Registr smluv, ID {d['id']}, příloha: {p['nazev']}\n\n{text}", encoding="utf-8")
            novych += 1
    return novych


# ---------- načtení pilotu ----------
Z = {}
with open(S / "detaily.jsonl", encoding="utf-8") as f:
    for l in f:
        d = json.loads(l)
        Z[d["id"]] = d
with open(S / "vazby.csv", encoding="utf-8-sig", newline="") as f:
    vazby = [(r["ids_zakladu"], r["id_zakladu"], r["id_dodatku"]) for r in csv.DictReader(f, delimiter=";")]
print(f"pilot: {len(Z)} záznamů, {len(vazby)} vazeb", flush=True)

# ---------- 1) chybějící záznamy seznamu ----------
pridane, pridane_dodatky, texty_novych = [], [], 0
if DOPLN_SEZNAM:
    with open(S / "zaklad.csv", encoding="utf-8-sig", newline="") as f:
        radky = list(csv.DictReader(f, delimiter=";"))
    dotazy = list(dict.fromkeys(r["dotaz"] for r in radky if r.get("dotaz")))
    znama_id = {r["id"] for r in radky}
    for dotaz in dotazy:
        nalez = hledej_vse(dotaz)
        chybi = [i for i in nalez if i not in znama_id]
        print(f"dotaz „{dotaz}“: API {len(nalez)} záznamů, v seznamu pilotu chybí {len(chybi)}", flush=True)
        for sid in chybi:
            r = api(f"smlouvy/{sid}")
            if not r:
                print(f"   {sid}: detail se nepodařilo načíst")
                continue
            d = z_api(r, "zaklad")
            Z[sid] = d
            texty_novych += uloz_texty(d, r)
            pridane.append(d)
            radky.append({"id": sid, "podpis": d["uzavrena"], "zverejneno": d["zverejnena"], "platce": d["platce"],
                          "dodavatel": d["dodavatel"], "cena_s_dph": d["s_dph"] or "", "predmet": d["predmet"],
                          "dotaz": dotaz})
            if d["je_dodatek"] or not d["ids"]:
                continue
            # navázané samostatné dodatky přidané smlouvy
            for did, rr in hledej_vse(f"navazanyZaznam:{d['ids']}").items():
                vazby.append((d["ids"], sid, did))
                if did in Z:
                    continue
                r2 = api(f"smlouvy/{did}")
                if r2:
                    Z[did] = z_api(r2, "dodatek")
                    texty_novych += uloz_texty(Z[did], r2)
                    pridane_dodatky.append(did)
    with open(S / "zaklad.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(radky[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(radky)

# ---------- 2) přílohy původních smluv, které vypadají jako dodatek, ale pilot je nepoznal ----------
k_overeni = [d for d in Z.values() if d.get("role") == "zaklad" and not d.get("je_dodatek")
             and any(druh_nazvu(p["nazev"]) in ("dod", "d") and "overeno_textem" not in p and not p.get("text")
                     for p in d["prilohy"])]
print(f"původních smluv s přílohou typu „D1 / DOD_1“ k ověření: {len(k_overeni)}", flush=True)
texty_priloh = 0
for d in k_overeni:
    r = api(f"smlouvy/{d['id']}")
    if not r:
        print(f"   {d['id']}: detail se nepodařilo načíst")
        continue
    texty_priloh += uloz_texty(d, r)

# ---------- 3) dřívější potvrzení přepočítat podle současného pravidla (texty už jsou na disku) ----------
prehodnoceno = 0
for d in Z.values():
    for p in d["prilohy"]:
        if p.get("overeno_textem") is True and p.get("text") and (T / p["text"]).exists():
            text = (T / p["text"]).read_text(encoding="utf-8", errors="replace").split("\n\n", 1)[-1]
            if not over_textem(text):
                p["overeno_textem"] = False
                del p["text"]                     # soubor s textem na disku zůstává, jen se přestane číst jako dodatek
                prehodnoceno += 1
if prehodnoceno:
    print(f"přehodnoceno podle přísnějšího pravidla (není dodatek): {prehodnoceno} příloh", flush=True)

# ---------- uložení ----------
with open(S / "detaily.jsonl", "w", encoding="utf-8") as f:
    for d in Z.values():
        f.write(json.dumps(d, ensure_ascii=False) + "\n")
with open(S / "vazby.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["ids_zakladu", "id_zakladu", "id_dodatku"])
    w.writerows(list(dict.fromkeys(vazby)))

potvrzene = [(d["id"], d["predmet"][:55], [p["nazev"] for p in d["prilohy"] if p.get("overeno_textem")])
             for d in Z.values() if any(p.get("overeno_textem") for p in d["prilohy"])]
zamitnute = sum(1 for d in Z.values() for p in d["prilohy"] if p.get("overeno_textem") is False)
bez_textu = sum(1 for d in Z.values() for p in d["prilohy"] if "overeno_textem" in p and p["overeno_textem"] is None)
print(f"\npřidáno záznamů do seznamu: {len(pridane)} (z toho původních smluv {sum(1 for d in pridane if not d['je_dodatek'])}) "
      f"| k nim navázaných dodatků {len(pridane_dodatky)} | textů {texty_novych}")
for d in pridane:
    print(f"   {d['id']} | {d['uzavrena']} | {'dodatek' if d['je_dodatek'] else 'smlouva'} | {(d['bez_dph'] or 0) / 1e6:.2f} mil. bez DPH | {d['predmet'][:70]}")
print(f"přílohy „D1 / DOD_1“: potvrzeno textem u {len(potvrzene)} smluv | zamítnuto {zamitnute} příloh | bez čitelného textu {bez_textu} "
      f"| nových textů {texty_priloh}")
for sid, predmet, nazvy in potvrzene:
    print(f"   {sid} | {predmet} | {nazvy}")
print(f"volání API: {volani}")
