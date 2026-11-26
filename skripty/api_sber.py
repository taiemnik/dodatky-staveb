# -*- coding: utf-8 -*-
"""Plný sběr metadat stavebních smluv měst přes API Hlídače státu (místo otevřených dat registru).

Co stahuje: pro každé město (statutární, III. a II. typ) dvě skupiny záznamů z oboru stavebnictví:
              základ   … smlouvy nad 1 mil. Kč s DPH
              dodatky  … záznamy se slovem „dodatek“ v předmětu (nesou vazbu na původní smlouvu)
            API vrací 25 záznamů na stránku a nejvýš 200 stránek na dotaz; větší města se proto dělí po letech.
Kam:        data/rs_api/rs_<IČO>.jsonl.gz ve stejném tvaru jako výstup rs_filtr.py, takže na ně jde pustit
            rs_kohorta.py beze změny. Hotové město se přeskočí – sběr jde přerušit a pustit znovu.
Šetrnost:   jeden dotaz za sekundu (hs_api.PAUZA), při odmítnutí (401, 403, 429) nebo třech chybách po sobě skript
            skončí. Limity bezplatného tarifu nejsou zveřejněné – neobcházet, raději pokračovat další den.
Co v datech chybí proti exportům registru: starší (zneplatněné) verze záznamu a názvy příloh. Proto nejde poznat
            dodatek přiložený k původnímu záznamu ani původní cenu, pokud ji město později přepsalo.
Zdroj:      Hlídač státu (CC BY 4.0) – u každého záznamu se ukládá odkaz na jeho stránku na Hlídači.
Použití:    python -I skripty/api_sber.py [nejvýš_měst]
"""
import csv
import gzip
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hs_api  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
KOREN = Path(__file__).resolve().parent.parent
CIL = KOREN / "data" / "rs_api"
CIL.mkdir(parents=True, exist_ok=True)
LOG = CIL / "_sber.log"
MAX_MEST = int(sys.argv[1]) if len(sys.argv) > 1 else 10 ** 6
KATEGORIE = ("statutární město", "obec III. typu", "obec II. typu")
OD_ROKU = 2022                    # hloubka sběru: smlouvy a dodatky podepsané od tohoto roku (zadání z 26. 11. 2026)
ROKY = range(OD_ROKU, 2027)
OBDOBI = f"podepsano:[{OD_ROKU}-01-01 TO 2026-12-31]"
MAX_STRAN = 200
hs_api.PAUZA = 2.0                # pomalu: nejvýš jeden dotaz za dvě sekundy


def log(text):
    radek = f"{time.strftime('%d.%m. %H:%M:%S')} {text}"
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(radek + "\n")
    print(radek, flush=True)


class Stop(Exception):
    pass


volani, chyby_za_sebou = 0, 0


def stranka(dotaz, strana):
    """Jedna stránka výsledků; hlídá odmítnutí a opakované chyby."""
    global volani, chyby_za_sebou
    stav, _, data = hs_api.hledej_smlouvy(dotaz, strana)
    volani += 1
    if stav in ("401", "403", "429"):
        raise Stop(f"API odmítlo dotaz (HTTP {stav}) po {volani} voláních")
    if stav != "200" or not isinstance(data, dict):
        chyby_za_sebou += 1
        if chyby_za_sebou >= 3:
            raise Stop(f"tři chyby po sobě (poslední HTTP {stav})")
        time.sleep(20)
        return None
    chyby_za_sebou = 0
    return data


def vse(dotaz):
    """Všechny záznamy dotazu; když je jich víc než strop stránkování, rozdělí dotaz po letech podpisu."""
    prvni = stranka(dotaz, 1)
    if prvni is None:
        return []
    celkem = prvni.get("total") or 0
    if celkem > MAX_STRAN * 25:
        out = []
        for rok in ROKY:
            out += vse(f"{dotaz} AND podepsano:[{rok}-01-01 TO {rok}-12-31]")
        return out
    out = list(prvni.get("results") or [])
    for s in range(2, (celkem + 24) // 25 + 1):
        d = stranka(dotaz, s)
        if d:
            out += d.get("results") or []
    return out


def prevod(r):
    """Záznam z API -> tvar, který čte rs_kohorta.py (jedna verze záznamu)."""
    ident = r.get("identifikator") or {}
    pl = r.get("platce") or {}
    strany = [{"role": "subjekt", "ico": (pl.get("ico") or "").zfill(8), "nazev": pl.get("nazev") or "",
               "utvar": pl.get("utvar") or "", "platce": "1"}]
    for p in r.get("prijemce") or []:
        strany.append({"role": "strana", "ico": (p.get("ico") or "").zfill(8) if p.get("ico") else "",
                       "nazev": p.get("nazev") or "", "prijemce": "1"})
    cislo = lambda x: "" if x in (None, 0, 0.0) else str(x)
    return {"ids": str(ident.get("idSmlouvy") or ""), "idv": str(r.get("id") or ident.get("idVerze") or ""),
            "cas": r.get("casZverejneni") or "", "platny": "1" if r.get("platnyZaznam") else "0", "strany": strany,
            "predmet": r.get("predmet") or "", "datum": (r.get("datumUzavreni") or "")[:10], "cislo": r.get("cisloSmlouvy") or "",
            "bez": cislo(r.get("hodnotaBezDph")), "s": cislo(r.get("hodnotaVcetneDph")), "cena_neuvedena": "",
            "navaz": str(r.get("navazanyZaznam") or ""), "prilohy": [], "zdroj": r.get("source_Url") or ""}


with open(KOREN / "data" / "obce.csv", encoding="utf-8-sig", newline="") as f:
    mesta = [r for r in csv.DictReader(f, delimiter=";") if r.get("kategorie") in KATEGORIE]
mesta.sort(key=lambda r: (KATEGORIE.index(r["kategorie"]), r["nazev"]))
log(f"START: měst {len(mesta)}, hotových {sum(1 for m in mesta if (CIL / f'rs_{m['ico']}.jsonl.gz').exists())}")
hotovo = 0
try:
    for m in mesta:
        cil = CIL / f"rs_{m['ico']}.jsonl.gz"
        if cil.exists():
            continue
        if hotovo >= MAX_MEST:
            break
        v0 = volani
        zaklad = vse(f"icoPlatce:{m['ico']} AND oblast:stav AND cena:>999999 AND {OBDOBI}")
        dodatky = vse(f"icoPlatce:{m['ico']} AND oblast:stav AND predmet:dodatek AND {OBDOBI}")
        zaznamy = {r["id"]: r for r in zaklad + dodatky}            # tentýž záznam může být v obou skupinách
        docasny = cil.with_suffix(".part")
        with gzip.open(docasny, "wt", encoding="utf-8") as out:
            for r in zaznamy.values():
                out.write(json.dumps(prevod(r), ensure_ascii=False) + "\n")
        docasny.replace(cil)
        hotovo += 1
        log(f"{m['nazev']} ({m['kategorie']}): základ {len(zaklad)}, dodatky {len(dodatky)}, volání {volani - v0} (celkem {volani})")
except Stop as e:
    log(f"STOP: {e}")
log(f"KONEC: měst v tomto běhu {hotovo}, volání {volani}")
