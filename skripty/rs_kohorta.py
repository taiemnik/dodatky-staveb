# -*- coding: utf-8 -*-
"""Celostátní „lehký“ průchod: stavební smlouvy měst (sídla ORP) a jejich dodatky – jen z metadat registru.

Co dělá:
  1) načte přefiltrované měsíční exporty (rs_*.jsonl = jen záznamy, kde je stranou obec),
  2) složí verze téhož záznamu (ID smlouvy) -> jedna „smlouva“ + historie verzí,
  3) vybere kohortu: stavební práce, objednatel = město se sídlem ORP, podpis v daném roce, cena >= práh,
  4) ke každé smlouvě dohledá dodatky třemi cestami:
       a) navázaný záznam (pole navazanyZaznam = ID původní smlouvy)        -> „navázaný“
       b) samostatný záznam bez vazby, shoda města + dodavatele + čísla/předmětu -> „odhadnutý“
       c) příloha s „dodatek“ v názvu u pozdější verze původního záznamu      -> „přiložený“
  5) změnu ceny bere JEN z metadat (hodnota dodatku, změna hodnoty mezi verzemi) – texty nečte.
     Proto je výsledek orientační: říká, kolik se dá zjistit bez čtení dodatků.
Vstup:   python rs_kohorta.py <složka s rs_*.jsonl> <obce.csv> <výstupní složka> [rok=2023] [práh bez DPH=1000000]
Výstup:  kohorta_<rok>.csv (smlouva = řádek), dodatky_<rok>.csv; souhrny na obrazovku
"""
import csv
import glob
import gzip
import html
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")
slozka, obce_csv, cil = sys.argv[1], sys.argv[2], sys.argv[3]
ROK = sys.argv[4] if len(sys.argv) > 4 else "2023"
PRAH = float(sys.argv[5]) if len(sys.argv) > 5 else 1_000_000
os.makedirs(cil, exist_ok=True)


def bezdia(s):
    """Malá písmena bez diakritiky – pro hledání klíčových slov."""
    s = unicodedata.normalize("NFD", html.unescape(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


with open(obce_csv, encoding="utf-8-sig", newline="") as fh:
    OBCE = {r["ico"]: r for r in csv.DictReader(fh, delimiter=";")}
# Které typy měst do rozboru patří (sloupec „kategorie“ doplňuje kategorie_mest.py). Malé obce a Praha ne.
KATEGORIE = {"statutární město", "obec III. typu", "obec II. typu"}

# ---------- klasifikace předmětu smlouvy (klíčová slova; registr sám obor neeviduje) ----------
RE_STAVBA = re.compile(
    r"rekonstrukc|oprav[ayue]\b|opravy |vystavb|stavebni uprav|stavebni prac|revitalizac|modernizac|zateplen"
    r"|pristavb|nastavb|novostavb|demolic|sanac[ei]|regenerac|vestavb|vybudovan|realizac[ei] stavby|zhotoveni stavby"
    r"|\bstavb[ayu]\b|snizeni energeticke narocnosti|vymen[ay] (oken|stresni|kotl|vytah)|odkanalizovan|chodnik"
    r"|cyklostezk|parkovist|parkovaci|hrist|kanalizac|vodovod|verejne(ho)? osvetleni|komunikac|\bmost[ue]?\b|lavk[ay]\b"
    r"|strech|fasad|sportovni areal|socialni(ch)? zarizeni")
RE_NESTAVBA = re.compile(
    r"projektov|dokumentac|\bpd\b|dozor|\bbozp\b|\bnajem|\bnajmu|pacht|kupni|koupe|darovac|dotac|prispev|bremen"
    r"|sluzebnost|pojist|uver|servis|licenc|software|studi[ei]\b|posud|zameren|geodet|administrac|inzenyrsk"
    r"|uklid|svoz|odpad|zimni udrzb|udrzb[ayu] zelen|bezna udrzb|provozovan|pronaj|vypujc|budouci|prelozk|pripojen"
    r"|dodavk[ayu] (elektr|plyn|tepl|vod)|sdruzen|spoluprac|komunalni(ch)? sluz|prevod|vyporadan|zajisteni financovani"
    r"|dopravni obsluznost|architektonick|soutez o navrh|navrh stavby|sosb|\bvb\b|spolecne(m)? zadavani|prefakturac|projekcni")
RE_DODATEK = re.compile(r"\bdodat(ek|ku|kem|ky|cich)?\b|\bdodatek|dodatek")
STOP = set("smlouva smlouve smlouvy dilo dila dodatek dodatku ke k na o c cislo ze dne sod stavby stavba akce akci "
           "realizace realizaci zhotoveni v ve a s pro mesto mesta ul ulice ulici etapa".split())


def tokeny(p):
    return {w for w in re.findall(r"[a-z0-9]{3,}", p) if w not in STOP}


# ---------- 1) + 2) načtení a složení verzí ----------
verze = defaultdict(list)
mesice = []
soubory = {os.path.basename(s)[3:10]: s for s in glob.glob(os.path.join(slozka, "rs_*.jsonl.gz"))}
soubory.update({os.path.basename(s)[3:10]: s for s in glob.glob(os.path.join(slozka, "rs_*.jsonl"))})   # rozbalený má přednost
for mesic in sorted(soubory):
    soubor = soubory[mesic]
    mesice.append(mesic)
    # exporty leží zabalené (.gz), čteme je rovnou – nic se nemusí rozbalovat na disk
    with (gzip.open(soubor, "rt", encoding="utf-8") if soubor.endswith(".gz") else open(soubor, encoding="utf-8")) as fh:
        for radek in fh:
            r = json.loads(radek)
            verze[r["ids"]].append(r)
print("měsíců:", len(mesice), mesice[0], "až", mesice[-1], "| záznamů (verzí):", sum(len(v) for v in verze.values()),
      "| smluv (ID smlouvy):", len(verze))


def hodnota(r):
    """Cena bez DPH; když je jen s DPH, vrátí ji a označí základ."""
    b, s = f(r["bez"]), f(r["s"])
    if b:
        return b, "bez"
    if s:
        return s, "s"
    return None, ""


smlouvy = {}
for ids, vs in verze.items():
    vs.sort(key=lambda r: int(r["idv"]))
    platne = [r for r in vs if r["platny"] == "1"]
    posl = platne[-1] if platne else vs[-1]            # aktuální stav záznamu
    prvni = vs[0]                                       # nejstarší verze v okně (původní smlouva)
    obecni = [s for s in posl["strany"] if s["ico"] in OBCE]
    jine = [s for s in posl["strany"] if s["ico"] not in OBCE]
    if not obecni:
        continue
    pn = bezdia(posl["predmet"])
    h_prvni, zaklad_prvni = hodnota(prvni)
    h_posl, zaklad_posl = hodnota(posl)
    # „pozdní příloha“: verze zveřejněná 14+ dní po první, která má víc příloh než předchozí.
    # Zachytí dodatek přiložený pod nic neříkajícím názvem souboru (např. „2900_1.pdf“).
    pozdni = 0
    for a, b in zip(vs, vs[1:]):
        dni = (date.fromisoformat(b["cas"][:10]) - date.fromisoformat(prvni["cas"][:10])).days
        if dni >= 14 and len(b["prilohy"]) > len(a["prilohy"]):
            pozdni += 1
    smlouvy[ids] = {
        "ids": ids, "idv": posl["idv"], "mesto_ico": obecni[0]["ico"], "mesto": OBCE[obecni[0]["ico"]]["nazev"],
        "dodavatel_ico": jine[0]["ico"] if jine else "", "dodavatel": jine[0]["nazev"] if jine else "",
        "predmet": html.unescape(posl["predmet"]), "pn": pn, "datum": posl["datum"], "cislo": posl["cislo"],
        "h_prvni": h_prvni, "h_posl": h_posl, "zaklad": zaklad_prvni or zaklad_posl, "navaz": posl["navaz"],
        "n_verzi": len(vs), "pozdni_prilohy": pozdni, "platny": bool(platne),
        "prvni_cas": prvni["cas"][:10], "posl_cas": posl["cas"][:10],
        "prilohy": posl["prilohy"],
        "je_dodatek": bool(posl["navaz"]) or bool(re.search(r"dodat(ek|ku|kem|ky)", pn)),
        "je_stavba": bool(RE_STAVBA.search(pn)) and not RE_NESTAVBA.search(pn),
    }
print("smluv s obcí jako stranou:", len(smlouvy),
      "| z toho záznamy-dodatky:", sum(1 for s in smlouvy.values() if s["je_dodatek"]),
      "| s vyplněným navázaným záznamem:", sum(1 for s in smlouvy.values() if s["navaz"]))

# ---------- 3) kohorta ----------
kohorta = {ids: s for ids, s in smlouvy.items()
           if not s["je_dodatek"] and s["je_stavba"] and s["platny"] and s["datum"].startswith(ROK)
           and OBCE[s["mesto_ico"]].get("kategorie") in KATEGORIE and s["dodavatel_ico"]
           and s["h_prvni"] and s["h_prvni"] >= PRAH}
print(f"KOHORTA {ROK}: stavební smlouvy měst (statutární, III. a II. typ), cena >= {PRAH:,.0f} Kč: {len(kohorta)}"
      f" | měst: {len({s['mesto_ico'] for s in kohorta.values()})}")
for kat in sorted(KATEGORIE):
    v_kat = [s for s in kohorta.values() if OBCE[s["mesto_ico"]]["kategorie"] == kat]
    vsech = sum(1 for o in OBCE.values() if o.get("kategorie") == kat)
    print(f"   {kat}: {len(v_kat)} smluv | měst se smlouvou {len({s['mesto_ico'] for s in v_kat})} z {vsech}")

# ---------- 4) dodatky ----------
dod_nav = defaultdict(list)          # a) navázané
for s in smlouvy.values():
    if s["navaz"] and s["platny"]:
        dod_nav[s["navaz"]].append(s)
# b) kandidáti bez vazby: klíč město + dodavatel
dod_volne = defaultdict(list)
for s in smlouvy.values():
    if s["je_dodatek"] and not s["navaz"] and s["platny"] and s["dodavatel_ico"]:
        dod_volne[(s["mesto_ico"], s["dodavatel_ico"])].append(s)


# c2) „navazující zakázky“: nové (ne-dodatkové) smlouvy téhož města s týmž dodavatelem – kandidáti na
#     vícepráce zadané mimo dodatek. Jen ukazatel k prověření: může jít i o poctivou další etapu.
dalsi_smlouvy = defaultdict(list)
for s in smlouvy.values():
    if not s["je_dodatek"] and s["platny"] and s["dodavatel_ico"] and s["h_prvni"]:
        dalsi_smlouvy[(s["mesto_ico"], s["dodavatel_ico"])].append(s)


def navazujici(s, B, zt):
    """Smlouvy do 18 měsíců po podpisu, do poloviny původní ceny, s podobným předmětem."""
    out = []
    try:
        d0 = date.fromisoformat(s["datum"])
    except ValueError:
        return out
    for x in dalsi_smlouvy.get((s["mesto_ico"], s["dodavatel_ico"]), []):
        if x["ids"] == s["ids"] or x["h_prvni"] >= 0.5 * B:
            continue
        try:
            dni = (date.fromisoformat(x["datum"]) - d0).days
        except ValueError:
            continue
        xt = tokeny(x["pn"])
        if 0 < dni <= 540 and zt and xt and len(zt & xt) >= 3 and len(zt & xt) / len(zt | xt) >= 0.5:
            out.append(x)
    return out


def cislo_dodatku_z_priloh(prilohy):
    """Kolik různých dodatků je mezi přílohami (podle názvu souboru)."""
    cisla, bez_cisla = set(), 0
    for p in prilohy:
        pn = bezdia(p)
        if "dodat" not in pn:
            continue
        m = re.search(r"dodat[a-z]*[\W_]*(?:c|cislo)?[\W_]*(\d{1,2})(?!\d)", pn)
        if m:
            cisla.add(int(m.group(1)))
        else:
            bez_cisla += 1
    return len(cisla) + (1 if bez_cisla and not cisla else 0)


def typ_hodnoty(v, B):
    """Co asi znamená hodnota u záznamu dodatku vůči ceně původní smlouvy B."""
    if not v:
        return "bez_hodnoty"
    if abs(v - B) / B <= 0.002:
        return "kopie_zakladu"
    if v >= 0.6 * B:
        return "nova_celkova"
    return "rozdil"


radky, radky_dod = [], []
for ids, s in kohorta.items():
    B = s["h_prvni"]
    nav = sorted(dod_nav.get(ids, []), key=lambda d: (d["datum"], int(d["idv"])))
    # b) odhad: stejný dodavatel, pozdější datum, číslo smlouvy jako předpona NEBO podobný předmět
    odh = []
    zt = tokeny(s["pn"])
    for d in dod_volne.get((s["mesto_ico"], s["dodavatel_ico"]), []):
        if d["datum"] < s["datum"]:
            continue
        c0, c1 = re.sub(r"\s", "", s["cislo"]).lower(), re.sub(r"\s", "", d["cislo"]).lower()
        shoda_cisla = len(c0) >= 5 and c1.startswith(c0) or (len(c0) >= 5 and c0 in bezdia(d["predmet"]).replace(" ", ""))
        dt = tokeny(d["pn"])
        jacc = len(zt & dt) / len(zt | dt) if zt and dt else 0
        if shoda_cisla or (jacc >= 0.6 and len(zt & dt) >= 3):
            odh.append(d)
    odh.sort(key=lambda d: (d["datum"], int(d["idv"])))
    n_pril = cislo_dodatku_z_priloh(s["prilohy"])
    samostatne = nav + odh

    # 5) změna ceny z metadat
    zdroj_ceny, konecna = "", None
    typy = []
    if samostatne:
        celk, rozd = None, 0.0
        for d in samostatne:
            v = d["h_posl"]
            ty = typ_hodnoty(v, B)
            typy.append(ty)
            radky_dod.append([ids, d["ids"], d["idv"], "navazany" if d in nav else "odhadnuty", d["datum"], v or "", ty,
                              d["predmet"][:160]])
            if ty == "nova_celkova":
                celk, rozd = v, 0.0            # celková cena přebíjí předchozí rozdíly
            elif ty == "rozdil":
                rozd += v
        if celk is not None or rozd:
            konecna = (celk if celk is not None else B) + rozd
            zdroj_ceny = "samostatne_dodatky"
        elif any(t == "kopie_zakladu" for t in typy):
            zdroj_ceny = "nejasne_kopie"
    if konecna is None and s["h_posl"] and abs(s["h_posl"] - B) / B > 0.002 and s["n_verzi"] > 1:
        konecna, zdroj_ceny = s["h_posl"], "zmena_hodnoty_verze"
    ma_dodatek = bool(samostatne) or n_pril > 0
    nz = navazujici(s, B, zt)
    o = OBCE[s["mesto_ico"]]
    radky.append({
        "ids": ids, "idv": s["idv"], "mesto": s["mesto"], "mesto_ico": s["mesto_ico"], "kategorie": o["kategorie"],
        "kraj": o["kraj"],
        "obyvatel": o["obyvatel"], "bvs_skupina": o["bvs_skupina"], "dodavatel": s["dodavatel"],
        "dodavatel_ico": s["dodavatel_ico"], "datum": s["datum"], "cislo": s["cislo"], "predmet": s["predmet"][:200],
        "cena_puvodni": B, "zaklad_ceny": s["zaklad"], "n_verzi": s["n_verzi"], "n_dod_navazanych": len(nav),
        "n_dod_odhadnutych": len(odh), "n_dod_prilohou": n_pril, "ma_dodatek": int(ma_dodatek),
        "vice_verzi_bez_dodatku": int(s["n_verzi"] > 1 and not ma_dodatek),
        "mozny_dodatek_prilohou": int(s["pozdni_prilohy"] > 0 and not ma_dodatek),
        "n_navazujicich_zakazek": len(nz), "navazujici_kc": round(sum(x["h_prvni"] for x in nz), 2),
        "cena_konecna": konecna if konecna is not None else "", "zdroj_ceny": zdroj_ceny,
        "zmena_pct": round((konecna - B) / B * 100, 2) if konecna is not None else "",
        "typy_hodnot": ",".join(typy), "odkaz": f"https://www.hlidacstatu.cz/Detail/{s['idv']}",
    })

with open(os.path.join(cil, f"kohorta_{ROK}.csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(radky[0].keys()), delimiter=";")
    w.writeheader()
    w.writerows(radky)
with open(os.path.join(cil, f"dodatky_{ROK}.csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh, delimiter=";")
    w.writerow(["ids_smlouvy", "ids_dodatku", "idv_dodatku", "vazba", "datum", "hodnota", "typ_hodnoty", "predmet"])
    w.writerows(radky_dod)

# ---------- souhrn na obrazovku ----------
n = len(radky)
sd = [r for r in radky if r["ma_dodatek"]]
sc = [r for r in radky if r["zmena_pct"] != ""]
print(f"\nSmluv v kohortě: {n}")
print(f"  s aspoň jedním dodatkem (jakákoli cesta): {len(sd)} = {len(sd)/n*100:.1f} %")
print(f"    navázaný záznam: {sum(1 for r in radky if r['n_dod_navazanych'])}"
      f" | odhadnutý: {sum(1 for r in radky if r['n_dod_odhadnutych'] and not r['n_dod_navazanych'])}"
      f" | jen přílohou: {sum(1 for r in radky if r['n_dod_prilohou'] and not r['n_dod_navazanych'] and not r['n_dod_odhadnutych'])}")
print(f"  více verzí záznamu, ale žádný rozpoznaný dodatek: {sum(r['vice_verzi_bez_dodatku'] for r in radky)}"
      f" | z toho pozdější verze s novou přílohou (možný nepojmenovaný dodatek): {sum(r['mozny_dodatek_prilohou'] for r in radky)}")
print(f"  změna ceny zjistitelná z metadat: {len(sc)} = {len(sc)/max(len(sd),1)*100:.1f} % smluv s dodatkem")
nzr = [r for r in radky if r["n_navazujicich_zakazek"]]
print(f"  smluv s možnou navazující zakázkou stejnému dodavateli (do 18 měsíců, podobný předmět): {len(nzr)}"
      f" = {len(nzr)/n*100:.1f} % | z toho bez jakéhokoli dodatku: {sum(1 for r in nzr if not r['ma_dodatek'])}")
print("  zdroj ceny:", Counter(r["zdroj_ceny"] for r in radky if r["ma_dodatek"]))
print("  typy hodnot u samostatných dodatků:", Counter(t for r in radky for t in r["typy_hodnot"].split(",") if t))
