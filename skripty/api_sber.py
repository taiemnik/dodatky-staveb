# -*- coding: utf-8 -*-
"""Plný sběr metadat stavebních smluv měst přes API Hlídače státu (místo otevřených dat registru).

Co stahuje: pro každé město (statutární, III. a II. typ) dvě skupiny záznamů:
              základ   … smlouvy z oboru stavebnictví nad 1 mil. Kč s DPH
              dodatky  … všechny záznamy města s vyplněnou vazbou na jiný záznam (navazanyZaznam), a k nim
                         záznamy z oboru stavebnictví se slovem „dodatek“ v předmětu, které vazbu nemají.
                         Ukládají se jen ty, které se váží ke smlouvě ze základu (nebo vazbu nemají).
            API vrací 25 záznamů na stránku a nejvýš 200 stránek na dotaz; větší města se proto dělí po letech.
Kam:        data/rs_api2/rs_<IČO>.jsonl.gz ve stejném tvaru jako výstup rs_filtr.py, takže na ně jde pustit
            rs_kohorta.py beze změny. Hotové město se přeskočí – sběr jde přerušit a pustit znovu.
Úplnost:    POZOR NA ŘAZENÍ. Při výchozím řazení (0 = podle relevance) má většina záznamů stejné skóre a API je
            na dalších stránkách vrací v jiném pořadí: část záznamů přijde dvakrát a část vůbec. První sběr
            (26.–27. 11. 2026, složka data/rs_api) tak ztratil zhruba čtvrtinu záznamů. Proto se řadí podle
            času zveřejnění (2 = od nejstarších, nové záznamy přibývají na konci a stránky se neposouvají)
            a u každého dotazu se počet různých záznamů porovná s údajem `total`. Když nesedí, projde se dotaz
            ještě jednou opačným řazením; co chybí i potom, zapíše se do logu slovem NEÚPLNÉ.
            Dodatky se původně hledaly jen dotazem „obor stavebnictví a slovo dodatek“ – ten našel 7 z 12
            dodatků známých z exportů registru; dotaz přes vazbu všech 12.
Šetrnost:   jeden dotaz za sekundu (hs_api.PAUZA), při odmítnutí (401, 403, 429) nebo třech chybách po sobě skript
            skončí. Limity bezplatného tarifu nejsou zveřejněné – neobcházet, raději pokračovat další den.
Co v datech chybí proti exportům registru: starší (zneplatněné) verze záznamu a názvy příloh. Proto nejde poznat
            dodatek přiložený k původnímu záznamu ani původní cenu, pokud ji město později přepsalo.
Zdroj:      Hlídač státu (CC BY 4.0) – u každého záznamu se ukládá odkaz na jeho stránku na Hlídači.
Použití:    python -I skripty/api_sber.py [nejvýš_měst] [--jen=IČO] [--pockej=MIN] [--konec-pri-limitu]
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
CIL = KOREN / "data" / "rs_api2"   # druhý sběr; neúplný první zůstává v data/rs_api (nemazat, jen nepoužívat)
CIL.mkdir(parents=True, exist_ok=True)
LOG = CIL / "_sber.log"
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
MAX_MEST = int(ARGS[0]) if ARGS else 10 ** 6
# --pockej=MIN: před prvním dotazem počkat (když předchozí běh skončil na hodinovém limitu)
POCKEJ = next((int(a.split("=")[1]) for a in sys.argv[1:] if a.startswith("--pockej=")), 0)
# --konec-pri-limitu: po vyčerpání hodinového limitu nečekat a skončit (jeden běh = jeden „kus“ sběru;
#                     po něm se přepočítá a zveřejní stránka a pustí se další kus)
KONEC_PRI_LIMITU = "--konec-pri-limitu" in sys.argv
# --jen=IČO: stáhnout jen jedno město (zkouška, nebo oprava jednoho města)
JEN = next((a.split("=")[1] for a in sys.argv[1:] if a.startswith("--jen=")), "")
CEKANI_NA_LIMIT = 65 * 60        # API po zhruba tisíci dotazech za hodinu vrací 429; čekáme hodinu a kousek
KATEGORIE = ("statutární město", "obec III. typu", "obec II. typu")
OD_ROKU = 2022                    # hloubka sběru: smlouvy a dodatky podepsané od tohoto roku (zadání z 26. 11. 2026)
ROKY = range(OD_ROKU, 2027)
OBDOBI = f"podepsano:[{OD_ROKU}-01-01 TO 2026-12-31]"
MAX_STRAN = 200
RAZENI, RAZENI_ZPET = 2, 1        # 2 = od nejdříve zveřejněných, 1 = od nejnověji zveřejněných (kontrolní průchod)
hs_api.PAUZA = 4.0                # pomalu: pod 900 dotazů za hodinu (26. 11. 2026 přišlo 429 po ~1000 za 40 minut)


def log(text):
    radek = f"{time.strftime('%d.%m. %H:%M:%S')} {text}"
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(radek + "\n")
    print(radek, flush=True)


class Stop(Exception):
    pass


class Limit(Exception):
    pass


volani, chyby_za_sebou = 0, 0
chybi_celkem = 0                  # kolik záznamů se nepodařilo získat ani kontrolním průchodem (za celý běh)


def stranka(dotaz, strana, razeni=RAZENI):
    """Jedna stránka výsledků; hlídá odmítnutí a opakované chyby."""
    global volani, chyby_za_sebou
    stav, _, data = hs_api.hledej_smlouvy(dotaz, strana, razeni)
    volani += 1
    if stav == "429":
        raise Limit()
    if stav in ("401", "403"):
        raise Stop(f"API odmítlo dotaz (HTTP {stav}) po {volani} voláních")
    if stav != "200" or not isinstance(data, dict):
        chyby_za_sebou += 1
        if chyby_za_sebou >= 3:
            raise Stop(f"tři chyby po sobě (poslední HTTP {stav})")
        time.sleep(20)
        return None
    chyby_za_sebou = 0
    return data


def pruchod(dotaz, razeni, prvni=None):
    """Jeden průchod všemi stránkami dotazu v daném řazení. Vrátí (slovník id -> záznam, total)."""
    prvni = prvni or stranka(dotaz, 1, razeni)
    if prvni is None:
        return {}, 0
    celkem = prvni.get("total") or 0
    nalez = {r["id"]: r for r in prvni.get("results") or []}
    for s in range(2, (celkem + 24) // 25 + 1):
        d = stranka(dotaz, s, razeni)
        if d:
            nalez.update({r["id"]: r for r in d.get("results") or []})
    return nalez, celkem


def vse(dotaz):
    """Všechny záznamy dotazu jako slovník id -> záznam, s kontrolou úplnosti proti údaji `total`.
    Když je záznamů víc než strop stránkování, rozdělí dotaz po letech podpisu."""
    global chybi_celkem
    prvni = stranka(dotaz, 1)
    if prvni is None:
        chybi_celkem += 1                                   # první stránka se nepovedla: úplnost neznámá
        log(f"   NEÚPLNÉ: první stránka dotazu se nepodařila načíst | {dotaz[:70]}")
        return {}
    celkem = prvni.get("total") or 0
    if celkem > MAX_STRAN * 25:
        nalez = {}
        for rok in ROKY:
            nalez.update(vse(f"{dotaz} AND podepsano:[{rok}-01-01 TO {rok}-12-31]"))
        return nalez
    nalez, _ = pruchod(dotaz, RAZENI, prvni)
    if len(nalez) < celkem:                                 # něco chybí: kontrolní průchod opačným řazením
        druhy, celkem2 = pruchod(dotaz, RAZENI_ZPET)
        nalez.update(druhy)
        celkem = max(celkem, celkem2)
        if len(nalez) < celkem:
            chybi_celkem += celkem - len(nalez)
            log(f"   NEÚPLNÉ: {len(nalez)} z {celkem} záznamů i po kontrolním průchodu | {dotaz[:70]}")
    return nalez


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
if JEN:
    mesta = [m for m in mesta if m["ico"] == JEN]
log(f"START: měst {len(mesta)}, hotových {sum(1 for m in mesta if (CIL / f'rs_{m['ico']}.jsonl.gz').exists())}")
hotovo, volani_pri_cekani = 0, -1000
if POCKEJ:
    log(f"čekám {POCKEJ} minut před prvním dotazem")
    time.sleep(POCKEJ * 60)
try:
    for m in mesta:
        cil = CIL / f"rs_{m['ico']}.jsonl.gz"
        if cil.exists():
            continue
        if hotovo >= MAX_MEST:
            break
        while True:
            v0 = volani
            try:
                zaklad = vse(f"icoPlatce:{m['ico']} AND oblast:stav AND cena:>999999 AND {OBDOBI}")
                # dodatky: vše s vazbou na jiný záznam (bez ohledu na obor a slovo v předmětu),
                # a k tomu stavební záznamy se slovem „dodatek“, které vazbu vyplněnou nemají
                navazane = vse(f"icoPlatce:{m['ico']} AND (navazanyZaznam:[1 TO *] OR "
                               f"(oblast:stav AND predmet:dodatek)) AND {OBDOBI}")
                break
            except Limit:
                # limit tarifu se neobchází: počkáme a město zkusíme znovu. Když limit přijde hned po čekání,
                # je nejspíš denní – pak skončíme a pokračuje se další den (hotová města se přeskočí).
                if volani - volani_pri_cekani < 30 and not (KONEC_PRI_LIMITU and volani_pri_cekani < 0):
                    raise Stop(f"limit API i po čekání (celkem {volani} volání) – nejspíš denní, pokračovat další den")
                if KONEC_PRI_LIMITU:
                    raise Stop(f"limit API po {volani} voláních – konec kusu")
                log(f"limit API po {volani} voláních, čekám {CEKANI_NA_LIMIT // 60} minut")
                time.sleep(CEKANI_NA_LIMIT)
                volani_pri_cekani = volani
        # Z navázaných záznamů si necháme jen ty k věci: bez vazby (přišly přes „stavebnictví a slovo dodatek“)
        # a ty, které se váží ke smlouvě ze základu – přímo, nebo přes jiný ponechaný dodatek (řetěz dodatků).
        # Dodatky nájemních, dotačních a jiných smluv města pro tento účel nepotřebujeme, tak se neukládají.
        idsm = lambda r: str((r.get("identifikator") or {}).get("idSmlouvy") or "")
        ponechat = dict(zaklad)
        znama_ids = {idsm(r) for r in zaklad.values()}
        zbyva = {i: r for i, r in navazane.items() if i not in ponechat}
        while True:
            nove = {i: r for i, r in zbyva.items()
                    if not r.get("navazanyZaznam") or str(r.get("navazanyZaznam")) in znama_ids}
            if not nove:
                break
            ponechat.update(nove)
            znama_ids |= {idsm(r) for r in nove.values()}
            zbyva = {i: r for i, r in zbyva.items() if i not in nove}
        docasny = cil.with_suffix(".part")
        with gzip.open(docasny, "wt", encoding="utf-8") as out:
            for r in ponechat.values():
                out.write(json.dumps(prevod(r), ensure_ascii=False) + "\n")
        docasny.replace(cil)
        hotovo += 1
        log(f"{m['nazev']} ({m['kategorie']}): základ {len(zaklad)}, k nim dodatků {len(ponechat) - len(zaklad)} "
            f"z {len(navazane)} navázaných záznamů města, volání {volani - v0} (celkem {volani})")
except Stop as e:
    log(f"STOP: {e}")
log(f"KONEC: měst v tomto běhu {hotovo}, volání {volani}, nezískaných záznamů {chybi_celkem}")
