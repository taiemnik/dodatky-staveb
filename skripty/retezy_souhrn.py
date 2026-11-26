# -*- coding: utf-8 -*-
"""Souhrn řetězů smlouva -> dodatky (výstup retezy.py): kolik akcí má dodatek, o kolik se mění cena, proč.

Vstup:  python retezy_souhrn.py <složka s retezy.csv a dodatky.csv> [poslední rok podpisu=2024] [práh ceny bez DPH=0]
Pozn.:  změna v % se počítá proti ceně v PŮVODNÍ smlouvě (bez DPH). Smlouvy bez dodatku mají změnu 0 %.
        Dodatek se stavem „neurceno“ / „bez_textu“ znamená, že cenu z něj skript neuměl bezpečně vyčíst
        – taková smlouva je označena a do statistik změny ceny se nepočítá (aby nevyšla falešná nula).
"""
import csv
import statistics as st
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
S = Path(sys.argv[1])
ROK_DO = sys.argv[2] if len(sys.argv) > 2 else "2024"
PRAH = float(sys.argv[3]) if len(sys.argv) > 3 else 0
NAN = float("nan")


def nacti(n):
    with open(S / n, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


R, D = nacti("retezy.csv"), nacti("dodatky.csv")
for r in R:
    for k in ("cena_puvodni", "cena_konecna", "zmena_pct", "viceprace", "meneprace", "obrat_pct", "cena_konecna_lehka"):
        r[k] = float(r[k])
    for k in ("stavba", "n_dodatku", "n_se_zmenou_ceny", "n_neurcenych", "n_verzi", "n_priloh_dodatek", "n_navazanych",
              "registr_prepsan", "termin", "nepredvid", "pozadavek_objednatele", "projekt"):
        r[k] = int(r[k])
vse = [r for r in R if r["stavba"] and r["podpis"][:4] <= ROK_DO and r["cena_puvodni"] >= PRAH]
# Tatáž smlouva bývá v registru dvakrát (opakované zveřejnění). Poznáme ji podle dodavatele, data a ceny;
# necháme záznam, na který jsou navázané dodatky.
uniq = {}
for r in vse:
    k = (r["dodavatel"], r["podpis"], round(r["cena_puvodni"]))
    if k not in uniq or r["n_dodatku"] > uniq[k]["n_dodatku"]:
        uniq[k] = r
duplicit = len(vse) - len(uniq)
vse = list(uniq.values())
# sjednotit názvy útvarů (v registru se tentýž odbor píše různě)
UTVARY = {"OMM": "OMM (odbor majetku města)", "Odbor majetku města": "OMM (odbor majetku města)",
          "INV": "ORM (rozvoj a investice)", "Oddělení investic": "ORM (rozvoj a investice)",
          "Odbor rozvoje města": "ORM (rozvoj a investice)", "ORM": "ORM (rozvoj a investice)"}
for r in vse:
    r["utvar"] = UTVARY.get(r.get("utvar", ""), r.get("utvar", ""))
print(f"Stavební smlouvy (podpis do {ROK_DO}, cena >= {PRAH:,.0f} Kč bez DPH): {len(vse)}  (z {len(R)} základních záznamů; "
      f"vyřazeno duplicitních zveřejnění: {duplicit})")


def kv(x, q):
    x = sorted(x)
    if not x:
        return NAN
    k = (len(x) - 1) * q
    a, b = int(k), min(int(k) + 1, len(x) - 1)
    return x[a] + (x[b] - x[a]) * (k - a)


def radek(nazev, rr):
    n = len(rr)
    if not n:
        return f"| {nazev} | 0 | | | | | | | | |"
    sd = [r for r in rr if r["n_dodatku"] > 0]
    cista = [r for r in rr if r["n_neurcenych"] == 0]           # cena je známá jistě (nebo dodatek není)
    zm = [r for r in cista if abs(r["zmena_pct"]) > 0.005]
    z_all = [r["zmena_pct"] for r in cista]
    z_zm = [r["zmena_pct"] for r in zm]
    kor = (sum(r["cena_konecna"] for r in cista) / sum(r["cena_puvodni"] for r in cista) - 1) * 100 if cista else NAN
    return (f"| {nazev} | {n} | {len(sd)} ({len(sd)/n*100:.0f} %) | {len(rr)-len(cista)} | {len(zm)} ({len(zm)/max(len(cista),1)*100:.0f} %) | "
            f"{kv(z_all,.5):.1f} | {st.mean(z_all) if z_all else NAN:.1f} | "
            f"{kv(z_zm,.5):.1f} | {kv(z_zm,.75):.1f} | {kor:.1f} |").replace(".", ",")


HL = ("| skupina | smluv | s dodatkem | cena neurčena | cena se změnila | medián všech % | průměr všech % | medián změněných % "
      "| Q3 změněných % | korunově % |\n|---|---|---|---|---|---|---|---|---|---|")
print("\n" + HL)
print(radek("Celkem", vse))


def pasmo(B):
    for h, n in ((2e6, "do 2 mil."), (5e6, "2–5 mil."), (10e6, "5–10 mil."), (20e6, "10–20 mil."), (1e12, "20+ mil.")):
        if B < h:
            return n


print("\n" + HL)
for p in ("do 2 mil.", "2–5 mil.", "5–10 mil.", "10–20 mil.", "20+ mil."):
    print(radek(p, [r for r in vse if pasmo(r["cena_puvodni"]) == p]))
print("\n" + HL)
for obd, a, b in (("2016–2019", "2016", "2019"), ("2020–2022", "2020", "2022"), ("2023–2024", "2023", "2024")):
    print(radek(obd, [r for r in vse if a <= r["podpis"][:4] <= b]))
utvary = Counter(r.get("utvar", "") for r in vse)
if len(utvary) > 1:                                     # pohled po odborech (jen když ho záznamy uvádějí)
    print("\n" + HL)
    for u, _ in utvary.most_common(6):
        print(radek(u or "(útvar neuveden)", [r for r in vse if r.get("utvar", "") == u]))

# ---- rozdělení změn proti hranám § 222 ZZVZ (15 % de minimis, 30 % souhrnný limit) ----
jiste = [r for r in vse if r["n_neurcenych"] == 0]
print(f"\nRozdělení změny ceny ({len(jiste)} smluv s jistou cenou):")
for a, b, n in ((-1e9, -5, "pod −5 %"), (-5, -0.005, "−5 až 0 %"), (-0.005, 0.005, "beze změny"), (0.005, 5, "0 až 5 %"),
                (5, 10, "5 až 10 %"), (10, 15, "10 až 15 %"), (15, 30, "15 až 30 %"), (30, 1e9, "nad 30 %")):
    k = sum(1 for r in jiste if a <= r["zmena_pct"] < b)
    print(f"  {n}: {k} ({k/len(jiste)*100:.0f} %)")

# ---- dodatky: stavy vytěžení, důvody ----
idv = {r["id"] for r in vse}
DD = [d for d in D if d["id_smlouvy"] in idv]
print(f"\nDodatků u těchto smluv: {len(DD)} | zdroj: {dict(Counter(d['zdroj'] for d in DD))}")
print("stav vytěžení ceny:", dict(Counter(d["stav"] for d in DD)))
print("hodnota dodatku v registru znamená:", dict(Counter(d["typ_hodnoty_v_registru"] for d in DD if d["zdroj"] == "navazany")))
for k, popis in (("vicepr", "zmiňuje vícepráce"), ("menepr", "zmiňuje méněpráce"), ("termin", "mění termín"),
                 ("nepredvid", "nepředvídané okolnosti"), ("pozadavek_objednatele", "požadavek objednatele"),
                 ("projekt", "odchylka od / vada projektové dokumentace")):
    s_textem = [d for d in DD if d[k] != ""]
    print(f"  {popis}: {sum(1 for d in s_textem if d[k]=='1')} z {len(s_textem)} dodatků s textem")
p222 = Counter()
for d in DD:
    for o in d["par222"].split(","):
        if o:
            p222[o] += 1
print("  odkaz na § 222 ZZVZ, odstavec (počet dodatků):", dict(sorted(p222.items())))

# ---- ověření lehké metody: konečná cena jen z hodnot v registru proti ceně vyčtené z textu ----
por = [r for r in vse if r["n_neurcenych"] == 0 and r["n_dodatku"] > 0]
sedi = [r for r in por if abs(r["cena_konecna_lehka"] - r["cena_konecna"]) <= max(2, 0.01 * r["cena_konecna"])]
print(f"\nOvěření lehké metody (jen hodnoty z registru): konečná cena sedí s textem na 1 % u {len(sedi)} z {len(por)} smluv s dodatkem")
vyssi = sum(1 for r in por if r["cena_konecna_lehka"] > r["cena_konecna"] * 1.01)
print(f"  lehká metoda vyšla výš u {vyssi}, níž u {len(por)-len(sedi)-vyssi}")
print(f"  cena v registru u původního záznamu dnes neodpovídá původní smlouvě (přepsána): {sum(r['registr_prepsan'] for r in vse)} z {len(vse)} smluv")

# ---- obrat: kolik z díla se během stavby „přepsalo“ (vícepráce + méněpráce k původní ceně) ----
zm = [r for r in jiste if r["obrat_pct"] > 0.005]
if zm:
    ob = [r["obrat_pct"] for r in zm]
    ci = [abs(r["zmena_pct"]) for r in zm]
    sV, sM, sB = sum(r["viceprace"] for r in zm), sum(r["meneprace"] for r in zm), sum(r["cena_puvodni"] for r in zm)
    print(f"\nObrat u {len(zm)} smluv se změnou: medián {kv(ob,.5):.1f} % původní ceny (čistá změna medián {kv(ci,.5):.1f} %), "
          f"Q3 {kv(ob,.75):.1f} %, nejvíc {max(ob):.1f} %")
    print(f"  součet víceprací {sV:,.0f} Kč, méněprací {sM:,.0f} Kč = obrat {(sV+sM)/sB*100:.1f} % a čistá změna {(sV-sM)/sB*100:+.1f} % "
          f"původních cen těchto smluv".replace(",", " "))
    print(f"  smluv, kde je obrat aspoň dvojnásobek čisté změny: {sum(1 for r in zm if r['obrat_pct'] >= 2*abs(r['zmena_pct']) and r['meneprace']>0)}")
    print(f"  smluv s vícepracemi nad 15 % původní ceny: {sum(1 for r in zm if r['viceprace']/r['cena_puvodni']>0.15)}"
          f" | nad 30 %: {sum(1 for r in zm if r['viceprace']/r['cena_puvodni']>0.30)}")
    print("  (obrat je dolní mez: kde dodatek uvádí jen výsledný rozdíl, vícepráce a méněpráce zvlášť neznáme)")

print("\nNejvětší změny (cena jistá):")
for r in sorted(jiste, key=lambda r: -abs(r["zmena_pct"]))[:12]:
    print(f"  {r['zmena_pct']:+6.1f} % (obrat {r['obrat_pct']:.0f} %) | {r['cena_puvodni']:>13,.0f} -> {r['cena_konecna']:>13,.0f} | dodatků {r['n_dodatku']} | {r['podpis']} | {r['predmet'][:70]} | {r['id']}".replace(",", " "))
print("\nSmlouvy s neurčenou cenou některého dodatku (k ručnímu / AI dočtení):")
for r in [r for r in vse if r["n_neurcenych"] > 0][:25]:
    print(f"  {r['id']} | dodatků {r['n_dodatku']} neurč. {r['n_neurcenych']} | {r['cena_puvodni']:>13,.0f} | {r['predmet'][:70]}".replace(",", " "))
