# -*- coding: utf-8 -*-
"""Sestaví data pro dashboard (docs/data.js) z výsledků pilotu.

Co jde ven a co ne (stránka může být veřejná):
  - ANO: agregace, kraj a velikostní pásmo města, ceny, změny v %, předmět smlouvy a odkaz na Hlídače
         u smluv vybraného města (jsou to veřejné záznamy registru smluv).
  - NE:  názvy dodavatelů a IČO (mezi dodavateli jsou i fyzické osoby), názvy ostatních měst
         (celostátní kohorta je z neúplných dat – nechceme z ní dělat žebříček měst).
Vstup:   python skripty/web_build.py [--bez-detailu-mesta]
         čte data/cr/kohorta_2023.csv, data/kop/retezy.csv, data/kop/dodatky.csv, data/vzorek/*.csv, data/rs/*.stat.json
Výstup:  docs/data.js (window.DATA = {...})
"""
import csv
import glob
import json
import math
import random
import statistics as st
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))      # typy.py leží vedle (režim -I složku skriptu nepřidá)
from typy import SEZNAM_DRUHU, SEZNAM_POVAH, druh, povaha     # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
KOREN = Path(__file__).resolve().parent.parent
BEZ_DETAILU = "--bez-detailu-mesta" in sys.argv
MESTO, MESTO_ICO = "Kopřivnice", "00298077"
PRAH_MESTO = 1_650_000          # 2 mil. Kč s DPH = hranice, od které byl stažen seznam smluv města
ROK_DO = "2024"                  # novější smlouvy ještě nemusí být dokončené


def nacti(cesta):
    with open(KOREN / cesta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def wilson(k, n, z=1.96):
    """95% interval spolehlivosti pro podíl k z n (v procentech)."""
    if n == 0:
        return [None, None]
    p, d = k / n, 1 + z * z / n
    s = p + z * z / (2 * n)
    o = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round((s - o) / d * 100, 1), round((s + o) / d * 100, 1)]


def boot_median(x, B=4000):
    """Interval pro medián převzorkováním (bootstrap), pevné semínko."""
    if len(x) < 5:
        return [None, None]
    random.seed(1)
    m = sorted(st.median(random.choices(x, k=len(x))) for _ in range(B))
    return [round(m[int(0.025 * B)], 1), round(m[int(0.975 * B)], 1)]


# ---------- 1) náhodný vzorek ČR (ceny z textů dodatků) ----------
V = {r["id_hlidac"]: r for r in nacti("data/vzorek/vzorek.csv") if r["id_hlidac"]}
RV = {r["id"]: r for r in nacti("data/vzorek/retezy.csv")}


def popis_vzorku(ids):
    rr = [RV[i] for i in ids if i in RV]
    n = len(rr)
    sd = [r for r in rr if int(r["n_dodatku"]) > 0]
    jiste = [r for r in rr if int(r["n_neurcenych"]) == 0]
    zm = [float(r["zmena_pct"]) for r in jiste if abs(float(r["zmena_pct"])) > 0.005]
    vse = [float(r["zmena_pct"]) for r in jiste]
    kor = (sum(float(r["cena_konecna"]) for r in jiste) / sum(float(r["cena_puvodni"]) for r in jiste) - 1) * 100
    return {"n": n, "s_dodatkem": len(sd), "s_dodatkem_pct": round(len(sd) / n * 100, 1), "s_dodatkem_ci": wilson(len(sd), n),
            "jistych": len(jiste), "zmenenych": len(zm), "zmenenych_pct": round(len(zm) / len(jiste) * 100, 1),
            "zmenenych_ci": wilson(len(zm), len(jiste)),
            "median_zmenenych": round(st.median(zm), 1) if zm else None, "median_ci": boot_median(zm),
            "prumer_zmenenych": round(st.mean(zm), 1) if zm else None,
            "prumer_vsech": round(st.mean(vse), 1), "korunove": round(kor, 1),
            "zdrazilo": sum(1 for x in zm if x > 0), "zlevnilo": sum(1 for x in zm if x < 0)}


nah = [i for i, r in V.items() if r["vyber"] == "nahodny"]
vzorek = {
    "celek": popis_vzorku(nah),
    "pasma": [dict(popis_vzorku([i for i in nah if a <= float(V[i]["cena_puvodni"]) < b]), nazev=n)
              for n, a, b in (("1–5 mil. Kč", 0, 5e6), ("5 mil. Kč a víc", 5e6, 1e12))],
    "velke": popis_vzorku([i for i, r in V.items() if float(r["cena_puvodni"]) >= 5e7]),
    "lehka_videla": sum(1 for i in nah if i in RV and int(RV[i]["n_dodatku"]) > 0 and V[i]["ma_dodatek"] == "1"),
}

# ---------- 2) vybrané město do hloubky ----------
UTVARY = {"OMM": "OMM", "Odbor majetku města": "OMM", "INV": "ORM", "Oddělení investic": "ORM",
          "Odbor rozvoje města": "ORM", "ORM": "ORM"}
RK = [r for r in nacti("data/kop/retezy.csv")
      if r["stavba"] == "1" and r["podpis"][:4] <= ROK_DO and float(r["cena_puvodni"]) >= PRAH_MESTO]
uniq = {}
for r in RK:                                             # tatáž smlouva zveřejněná dvakrát -> jednou
    k = (r["dodavatel"], r["podpis"], round(float(r["cena_puvodni"])))
    if k not in uniq or int(r["n_dodatku"]) > int(uniq[k]["n_dodatku"]):
        uniq[k] = r
RK = list(uniq.values())
mesto = [{"id": r["id"] if not BEZ_DETAILU else "",
          "p": (r["predmet"].replace("Smlouva o dílo - ", "").strip()[:110]) if not BEZ_DETAILU else "",
          "r": int(r["podpis"][:4]), "u": UTVARY.get(r["utvar"], "jiný / neuveden"),
          "k": SEZNAM_DRUHU.index(druh(r["predmet"])), "h": SEZNAM_POVAH.index(povaha(r["predmet"])),
          "b": round(float(r["cena_puvodni"])), "f": round(float(r["cena_konecna"])),
          "z": float(r["zmena_pct"]), "o": float(r["obrat_pct"]), "d": int(r["n_dodatku"]),
          "n": int(int(r["n_neurcenych"]) > 0), "t": int(int(r["termin"]) > 0),
          "v": round(float(r["viceprace"])), "m": round(float(r["meneprace"]))} for r in RK]
idk = {r["id"] for r in RK}
DK = [d for d in nacti("data/kop/dodatky.csv") if d["id_smlouvy"] in idk]
s_textem = [d for d in DK if d["termin"] != ""]
duvody = {"dodatku": len(DK), "s_textem": len(s_textem),
          **{k: sum(1 for d in s_textem if d[k] == "1") for k in
             ("termin", "nepredvid", "pozadavek_objednatele", "projekt", "vicepr", "menepr")},
          "prilohou": sum(1 for d in DK if d["zdroj"] == "priloha"),
          "navazanych": sum(1 for d in DK if d["zdroj"] == "navazany"),
          "stavy": dict(Counter(d["stav"].split("+")[0] for d in DK))}

# ---------- 3) celostátní kohorta (lehká metoda, jen metadata; bez názvů měst a dodavatelů) ----------
KOHORTA = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--kohorta=")), "data/cr/kohorta_2023.csv")
K = nacti(KOHORTA)
OBCE = {r["ico"]: r for r in nacti("data/obce.csv")}
KATEGORIE = ["statutární město", "obec III. typu", "obec II. typu"]
kraje = sorted({r["kraj"] for r in K})
mesta = sorted({r["mesto"] for r in K})
PASMA_MEST = ["do 5 tis.", "5–10 tis.", "10–20 tis.", "20–30 tis.", "30–50 tis.", "50–100 tis.", "100+ tis."]
ZDROJE = ["bez dodatku", "hodnoty navázaných dodatků", "přepsaná hodnota původního záznamu", "dodatek bez ceny v registru"]


def pasmo_mesta(o):
    if not o:
        return -1                                        # počet obyvatel máme jen u sídel ORP
    return next(i for i, h in enumerate((5e3, 10e3, 20e3, 30e3, 50e3, 100e3, 1e12)) if float(o) < h)


def zdroj_ceny(r):
    if r["ma_dodatek"] == "0":
        return 0
    if r["zmena_pct"] == "":
        return 3
    return 2 if r["zdroj_ceny"] == "zmena_hodnoty_verze" else 1


# Celostátní smlouvy z metadat registru – po řádcích, aby si je šlo na stránce zkontrolovat:
# [ID verze (odkaz do registru), město, předmět, rok, typ města, kraj, pásmo obyvatel, původní cena, počet dodatků,
#  změna % (0 = bez dodatku, null = dodatek bez zjistitelné ceny), druh, povaha, jak je cena zjištěna]
cr = [[r["idv"], mesta.index(r["mesto"]), r["predmet"].replace("Smlouva o dílo - ", "").strip()[:90], int(r["datum"][:4]),
       KATEGORIE.index(r["kategorie"]), kraje.index(r["kraj"]), pasmo_mesta(OBCE[r["mesto_ico"]]["obyvatel"]), round(float(r["cena_puvodni"])),
       int(r["n_dod_navazanych"]) + int(r["n_dod_odhadnutych"]) + int(r["n_dod_prilohou"]),
       (0.0 if r["ma_dodatek"] == "0" else float(r["zmena_pct"]) if r["zmena_pct"] != "" else None),
       SEZNAM_DRUHU.index(druh(r["predmet"])), SEZNAM_POVAH.index(povaha(r["predmet"])), zdroj_ceny(r)] for r in K]
pokryti = {k: {"smluv": sum(1 for r in K if r["kategorie"] == k), "mest": len({r["mesto_ico"] for r in K if r["kategorie"] == k}),
               "mest_celkem": sum(1 for o in OBCE.values() if o.get("kategorie") == k)} for k in KATEGORIE}

# vzorek po smlouvách – bez názvu města, předmětu i odkazu:
# [druh, povaha, původní cena, změna % | null, má dodatek, náhodný výběr, typ města]
vz = [[SEZNAM_DRUHU.index(druh(V[i]["predmet"])), SEZNAM_POVAH.index(povaha(V[i]["predmet"])),
       round(float(r["cena_puvodni"])), (float(r["zmena_pct"]) if int(r["n_neurcenych"]) == 0 else None),
       int(int(r["n_dodatku"]) > 0), int(V[i]["vyber"] == "nahodny"),
       KATEGORIE.index(OBCE[V[i]["mesto_ico"]]["kategorie"])] for i, r in RV.items() if i in V]

# ---------- 4) struktura registru ve stažených měsících ----------
S = Counter()
for f in glob.glob(str(KOREN / "data/rs/*.stat.json")):
    for k, v in json.load(open(f, encoding="utf-8")).items():
        if k != "znacka":
            S[k] += v

def _pasmo(z):
    return 0 if z < -0.5 else 1 if z < 0.5 else 2 if z < 10 else 3 if z < 20 else 4 if z < 30 else 5


_over = [r for r in nacti("data/kop/retezy.csv") if r["stavba"] == "1" and int(r["n_neurcenych"]) == 0] \
    + [r for i, r in RV.items() if i in V and int(r["n_neurcenych"]) == 0]
_zz = [(float(r["zmena_pct"]), (float(r["cena_konecna_lehka"]) / float(r["cena_puvodni"]) - 1) * 100) for r in _over]
presnost = {"smluv": len(_zz), "pasmo": sum(1 for a, b in _zz if _pasmo(a) == _pasmo(b)),
            "skut20": sum(1 for a, b in _zz if a >= 20), "najde20": sum(1 for a, b in _zz if a >= 20 and b >= 20)}

DATA = {
    "meta": {"sestaveno": date.today().isoformat(), "mesto": MESTO, "prah_mesto": PRAH_MESTO, "rok_do": ROK_DO,
             "s_detailem": not BEZ_DETAILU, "presnost": presnost, "zdroj": "api" if "api" in KOHORTA else "exporty",
             "mest_v_datech": len({r["mesto_ico"] for r in K}), "mest_celkem": sum(1 for o in OBCE.values() if o.get("kategorie") in KATEGORIE), "mesice_exportu": sorted(Path(f).name[3:10] for f in glob.glob(str(KOREN / "data/rs/*.stat.json")))},
    "vzorek": vzorek, "vz": vz, "mesto": mesto, "duvody": duvody, "druhy": SEZNAM_DRUHU, "povahy": SEZNAM_POVAH,
    "cr": cr, "kraje": kraje, "mesta": mesta, "kategorie": KATEGORIE, "pokryti": pokryti, "zdroje": ZDROJE, "pasma_mest": PASMA_MEST,
    "registr": dict(S),
}
cil = KOREN / "docs" / "data.js"
cil.parent.mkdir(exist_ok=True)
cil.write_text("window.DATA = " + json.dumps(DATA, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
# Lokální aplikace v jednom souboru (data vložená přímo do stránky): otevře se dvojklikem, jde poslat e-mailem.
stranka = (KOREN / "docs" / "index.html").read_text(encoding="utf-8")
assert stranka.count('<script src="data.js"></script>') == 1
(KOREN / "dodatky-staveb.html").write_text(
    stranka.replace('<script src="data.js"></script>', "<script>\n" + cil.read_text(encoding="utf-8") + "</script>"), encoding="utf-8")
print(f"docs/data.js: {cil.stat().st_size/1024:.0f} kB | město {len(mesto)} smluv | kohorta ČR {len(cr)} | vzorek {vzorek['celek']['n']}"
      f" | detail města: {'ne' if BEZ_DETAILU else 'ano'}")
print("vzorek:", json.dumps(vzorek["celek"], ensure_ascii=False))
