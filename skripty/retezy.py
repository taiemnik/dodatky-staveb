# -*- coding: utf-8 -*-
"""Řetězy „smlouva o dílo -> dodatky -> konečná cena“, s cenou vytaženou z TEXTU dodatků.

Výchozí cena:
  Bere se z NEJSTARŠÍ verze záznamu. Aktuální verze může nést už konečnou cenu – město ji při
  zveřejnění dodatku někdy přepíše (most Kpt. Jaroše: dnes 5,90 mil., původně 4,41 mil. Kč).

Jak se hledá nová cena (bez umělé inteligence, ověřitelně):
  Dodatek uvádí dosavadní cenu, změnu a novou cenu a často opakuje celou historii
  (cena dle smlouvy -> dle dodatku č. 1 -> dle dodatku č. 2 …). Skript vezme z těla dodatku čísla
  z cenových řádků a staví z nich řetěz: z ceny A se smí přejít na cenu B jen tehdy, když je v textu
  i rozdíl |B − A|, nebo popsané vícepráce a méněpráce, pro které platí A + vícepráce − méněpráce = B.
  Začíná u ceny, kterou zná (z registru nebo z předchozího dodatku), a novou cenou je ta dosažitelná
  cena, která stojí v textu nejníž. Ceny s DPH se vyřadí (pozná je podle toho, že je v textu i jejich
  základ). Když řetěz nevznikne, dodatek zůstane „neurčeno“ a jde k ručnímu nebo AI dočtení.
Vstup:   python retezy.py <složka pilotu s detaily.jsonl, vazby.csv, texty/>
Výstup:  retezy.csv (smlouva = řádek), dodatky.csv (dodatek = řádek s důkazem), souhrn na obrazovku
"""
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
S = Path(sys.argv[1])
DPH = (0.21, 0.15, 0.12, 0.10)


def bezdia(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


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
RE_CENOVY_RADEK = re.compile(r"cen[auyoe]|celk|dph|vicepr|menepr|dodatk|dodatec|neprovad|navys|sniz|zvys|castk|rozdil|dopad")
# začátek položkového rozpočtu: za ním už jsou tisíce čísel, mezi kterými součty vycházejí náhodou
RE_ROZPOCET = re.compile(r"^\s*(soupis prac|kryci list)|naklady (soupisu|stavby) celkem|\bmj\b.*mnozstvi"
                         r"|mnozstvi.*j\.? ?cena|cena jednotkova")
# číslo česky (1 234 567,89 / 1.234.567,89 / 1.234.567,-) nebo anglicky (1,234,567.89)
RE_CISLO = re.compile(r"(?<![\d,.])(?:\d{1,3}(?:,\d{3})+\.\d{2}|\d{1,3}(?:[  .]\d{3})+(?:,\d{1,2})?|\d{4,}(?:,\d{1,2})?)(?![\d])")
MAX_MALYCH = 80           # dvoukrokový součet bez popisků zkoušet jen v krátkém textu (jinak vychází náhodou)


def na_cislo(x):
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+\.\d{2}", x):
        return float(x.replace(",", ""))
    return float(re.sub(r"[  .]", "", x).replace(",", "."))


def cisla_z_textu(text):
    """Čísla z cenových řádků těla dodatku (do začátku položkového rozpočtu). Vrací [(hodnota, č. řádku)], řádky."""
    radky = text.splitlines()
    konec = len(radky)
    for i, r in enumerate(radky):
        if i > 15 and RE_ROZPOCET.search(bezdia(r)):
            konec = i
            break
    beru = set()
    for i, r in enumerate(radky[:konec]):
        if RE_CENOVY_RADEK.search(bezdia(r)):
            beru.update((i, i + 1, i + 2))            # tabulky se lámou: vzít i dva další řádky
    out = []
    for i in sorted(beru):
        if i < konec:
            for m in RE_CISLO.finditer(radky[i]):
                try:
                    v = na_cislo(m.group(0))
                except ValueError:
                    continue
                if v >= 100:
                    out.append((round(v, 2), i))
    return out, radky


def je(hodnota, mnozina, tol=1.01):
    return any(abs(hodnota - x) <= tol for x in mnozina)


RE_DOPAD = re.compile(r"(celkov\w* (cenov\w* )?dopad|dopad (vsech )?(zmen|vicepraci a menepraci)[^0-9]{0,60}cen|cena (dila )?se (zvysuje|snizuje|navysuje) o)")


def uvedeny_dopad(radky, konec=400):
    """Poslední řádek typu „celkový dopad na cenu díla je −27 310,00 Kč“ -> (částka se znaménkem, řádek)."""
    nalez = None
    for r in radky[:konec]:
        nb = bezdia(r)
        if not RE_DOPAD.search(nb):
            continue
        m = re.search(r"([+\-−–]?)\s*(" + RE_CISLO.pattern + r")", r[RE_DOPAD.search(nb).end():])
        if m:
            try:
                d = na_cislo(m.group(2))
            except ValueError:
                continue
            minus = m.group(1) in "-−–" and m.group(1) != "" or "snizuje" in nb
            nalez = (-d if minus else d, r.strip()[:140])
    return nalez


def najdi_novou_cenu(text, P, meta=None):
    """Vrátí dict s novou cenou N, vícepracemi V, méněpracemi M a důkazem, nebo None.

    meta = hodnota dodatku v registru (když je): slouží jen ke křížové kontrole nálezu z textu.
    """
    nal = _z_retezu(text, P, meta)
    cisla, radky = cisla_z_textu(text)
    hodn = sorted({v for v, _ in cisla})
    if not nal and hodn:
        # záloha: dodatek uvádí jen dopad na cenu, novou cenu ne -> N = P ± dopad
        dop = uvedeny_dopad(radky)
        if dop and 0 < abs(dop[0]) < 0.6 * P:
            N = P + dop[0]
            nal = {"N": N, "body": 2, "V": max(dop[0], 0.0), "M": max(-dop[0], 0.0), "presne": 0,
                   "potvrzeno_P": je(P, hodn), "radek": dop[1], "kandidatu": 1}
    if nal and meta:
        # křížová kontrola: sedí nález z textu s hodnotou dodatku v registru (rozdíl nebo nová celková cena)?
        d = abs(nal["N"] - P)
        if (abs(d - meta) <= max(2, 0.001 * meta) or abs(nal["N"] - meta) <= max(2, 0.0001 * meta)
                or any(abs(d * (1 + s) - meta) <= max(2, 0.001 * meta) for s in DPH)):      # registr může být s DPH
            nal["body"] += 2
            nal["potvrzeno_registrem"] = 1
    return nal


def _z_retezu(text, P, meta=None):
    """Nová cena z řetězu cen v textu a z „trojic“ cena bez DPH – DPH – cena s DPH."""
    cisla, radky = cisla_z_textu(text)
    hodn = sorted({v for v, _ in cisla})
    if not hodn or not P:
        return None
    pozice = {}
    for v, i in cisla:
        pozice[v] = max(i, pozice.get(v, -1))
    je_s_dph = lambda x: any(je(x / (1 + s), hodn, 2.0) for s in DPH)     # x je něčí cena s DPH
    ma_dph = lambda x: any(je(x * (1 + s), hodn, 2.0) for s in DPH)       # k x je v textu i cena s DPH
    # kulatý podíl z ceny (50 % z ceny díla, 10% pozastávka…) není nová cena, ale platební podmínka
    je_podil = lambda x: any(abs(x - P * k / 20) <= 1.0 for k in range(1, 50) if k != 20)
    uzly = [x for x in hodn if 0.4 * P < x < 2.5 * P and not je_s_dph(x) and not je_podil(x)]
    male = [x for x in hodn if x < 0.6 * P]
    male_r = {round(x) for x in male}
    lab_v = {v for v, i in cisla if re.search(r"vicepr|dodatecn", bezdia(radky[i]))}
    lab_m = {v for v, i in cisla if re.search(r"menepr|neprovad|odpocet", bezdia(radky[i]))}
    potvrzeno_P = je(P, hodn)

    def krok(a, b):
        """Síla důkazu, že se z ceny a přešlo na cenu b (0 = žádný)."""
        d = abs(b - a)
        if d < 1.5:
            return 0
        for v in lab_v:                                   # popsané vícepráce a méněpráce
            for m in lab_m:
                if abs(a + v - m - b) <= 1.5 and abs(v - m) > 1:
                    return 4
        if je(d, hodn):                                   # rozdíl je v textu
            return 3
        if len(male) <= MAX_MALYCH:                       # dvě nepopsané částky: a + v − m = b
            for v in male:
                m = a + v - b
                if m > 0 and abs(m - v) > 1 and (round(m) in male_r or round(m) + 1 in male_r or round(m) - 1 in male_r):
                    return 2
        return 0

    dosazene, fronta, videne = {}, [P], {round(P)}
    while fronta:                                         # průchod řetězem cen od známé ceny P
        a = fronta.pop()
        for b in uzly:
            if round(b) in videne:
                continue
            k = krok(a, b)
            if k:
                videne.add(round(b))
                dosazene[b] = k
                fronta.append(b)
    # „Trojice“: cena bez DPH, k ní v textu částka DPH i cena s DPH -> jde o celkovou cenu díla.
    # Dodatek, který uvádí jen novou cenu (bez rozdílu), se pozná právě takhle.
    for x in uzly:
        if abs(x - P) > 1.5 and x not in dosazene and any(
                je(x * s, hodn, 2.0) and je(x * (1 + s), hodn, 2.0) for s in DPH):
            dosazene[x] = 3
    if not dosazene:
        if potvrzeno_P:
            return None                                   # dosavadní cena v textu je, nová ne -> cena se nemění
        # P v textu není (jiný základ, chybí předchozí dodatek): vzít řetěz, který je v textu sám
        kand = [x for x in uzly if ma_dph(x)]
        for a in kand:
            for b in kand:
                if pozice[b] > pozice[a] and krok(a, b) >= 3:
                    dosazene[b] = 2
        if not dosazene:
            return None
    N = max(dosazene, key=lambda b: (pozice[b], dosazene[b]))
    if meta:
        # Rozhodčí: hodnota dodatku v registru. Když některá cena v textu sedí na „registr = nová celková
        # cena“, nebo se od jiné ceny v řetězu liší přesně o hodnotu z registru, je to cena po tomto dodatku
        # (dodatky často opakují historii a poslední cena v textu nemusí být ta nová).
        zdroje = [P] + list(dosazene)
        for b in sorted(uzly, key=lambda x: pozice[x], reverse=True):
            if abs(b - P) <= 1.5:
                continue
            if abs(b - meta) <= max(2, 1e-4 * meta) or any(
                    abs(b - a) > 1.5 and abs(abs(b - a) - meta) <= max(2, 1e-3 * meta) for a in zdroje):
                N = b
                dosazene.setdefault(b, 3)
                break
    # vícepráce a méněpráce tohoto dodatku: popsané částky, které přesně sedí; jinak jen čistý rozdíl
    V, M, presne = max(N - P, 0.0), max(P - N, 0.0), 0
    for v in lab_v:
        for m in lab_m:
            if abs(P + v - m - N) <= 1.5 and abs(v - m) > 1:
                V, M, presne = v, m, 1
    if not presne and ((N > P and je(N - P, lab_v)) or (N < P and je(P - N, lab_m))):
        presne = 1
    return {"N": N, "body": dosazene[N] + (2 if ma_dph(N) else 0) + (1 if potvrzeno_P else 0), "V": V, "M": M,
            "presne": presne, "potvrzeno_P": potvrzeno_P, "radek": radky[pozice[N]].strip()[:140],
            "kandidatu": len(dosazene)}


def priznaky(text):
    t = bezdia(text[:40000])
    return {
        "vicepr": int("vicepr" in t), "menepr": int("menepr" in t),
        "termin": int(bool(re.search(r"termin\w* (dokonceni|plneni|predani|provedeni)|lhut[ayu] (plneni|k provedeni)|prodlouz|prodluz", t))),
        "nepredvid": int("nepredvid" in t),
        "pozadavek_objednatele": int(bool(re.search(r"(pozadav|zadost)\w* objednatele|na zaklade pozadavku", t))),
        "projekt": int(bool(re.search(r"(vad|chyb|nesoulad|nedostat)\w* (v )?projektov|projektov\w* dokumentac\w* (ne|chyb)|odlisne od projektov", t))),
        "par222": ",".join(sorted(set(re.findall(r"222 odst\w*\.? ?(\d)", t)))),
    }


# ---------- načtení ----------
Z = {}
with open(S / "detaily.jsonl", encoding="utf-8") as f:
    for l in f:
        d = json.loads(l)
        Z[d["id"]] = d
vazby = defaultdict(list)
with open(S / "vazby.csv", encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f, delimiter=";"):
        vazby[r["id_zakladu"]].append(r["id_dodatku"])


def datum(d):
    x = d.get("uzavrena", "")
    return f"{x[6:10]}-{x[3:5]}-{x[0:2]}" if len(x) == 10 else ""


def cislo_dodatku(nazev):
    m = re.search(r"dodat[a-z]*[\W_]*(?:c|cislo)?[\W_]*(\d{1,2})(?!\d)", bezdia(nazev))
    return int(m.group(1)) if m else None


def text_souboru(nazev):
    p = S / "texty" / nazev
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace").split("\n\n", 1)[-1]


def typ_hodnoty(v, B):
    """Co asi znamená hodnota u záznamu dodatku v registru (stejné pravidlo jako v rs_kohorta.py)."""
    if not v:
        return "bez_hodnoty"
    if abs(v - B) / B <= 0.002:
        return "kopie_zakladu"
    return "nova_celkova" if v >= 0.6 * B else "rozdil"


retezy, dodatky = [], []
for sid, d in Z.items():
    pn = bezdia(d["predmet"])
    if d.get("je_dodatek") or d["role"] != "zaklad" or not d["platna"]:
        continue
    stavba = bool(RE_STAVBA.search(pn)) and not RE_NESTAVBA.search(pn)
    nyni = d["bez_dph"] or (d["s_dph"] / 1.21 if d["s_dph"] else None)
    B = d.get("puvodni_bez_dph") or (d["puvodni_s_dph"] / 1.21 if d.get("puvodni_s_dph") else None) or nyni
    if not B:
        continue
    # dokumenty dodatků: a) přiložené k původnímu záznamu, b) samostatné navázané záznamy
    docs = []
    for p in d["prilohy"]:
        if re.search("dodat", p["nazev"], re.I):
            docs.append({"zdroj": "priloha", "id": sid, "nazev": p["nazev"], "cd": cislo_dodatku(p["nazev"]),
                         "datum": "", "text": p.get("text", ""), "slov": p["slov"], "meta": None})
    for did in vazby.get(sid, []):
        dd = Z.get(did)
        if not dd or not dd["platna"]:
            continue
        texty = [p for p in dd["prilohy"] if p.get("text")]
        # tělo dodatku = příloha s „dodatek“ v názvu, jinak nejkratší čitelná
        texty.sort(key=lambda p: (0 if re.search("dodat", p["nazev"], re.I) else 1, p["slov"]))
        docs.append({"zdroj": "navazany", "id": did, "nazev": dd["predmet"],
                     "cd": cislo_dodatku(dd["predmet"]) or cislo_dodatku(dd["cislo"]),
                     "datum": datum(dd), "text": texty[0]["text"] if texty else "",
                     "dalsi_texty": [p["text"] for p in texty[1:]],      # záznam mívá víc příloh (tělo + rozpočty)
                     "slov": texty[0]["slov"] if texty else 0, "meta": dd["bez_dph"] or dd["s_dph"]})
    # stejný dodatek může být přílohou i samostatným záznamem -> podle čísla nechat jeden (raději s textem)
    podle_cisla, bez_cisla = {}, []
    for x in docs:
        if x["cd"] is None:
            bez_cisla.append(x)
            continue
        y = podle_cisla.get(x["cd"])
        if y is None or (not y["text"] and x["text"]) or (x["zdroj"] == "navazany" and y["zdroj"] != "navazany" and x["text"]):
            if y is not None and x["meta"] is None:
                x["meta"] = y["meta"]
            podle_cisla[x["cd"]] = x
        elif y["meta"] is None:
            y["meta"] = x["meta"]
    poradi = [podle_cisla[k] for k in sorted(podle_cisla)] + sorted(bez_cisla, key=lambda x: x["datum"])

    P, n_zmen, n_neurc, prizn = B, 0, 0, Counter()
    sum_V = sum_M = 0.0
    obrat_presny = 1
    lehka_celk, lehka_rozd, lehka_ma = None, 0.0, False       # „lehká metoda“: jen hodnoty z registru
    for x in poradi:
        t = text_souboru(x["text"]) if x["text"] else ""
        nal = najdi_novou_cenu(t, P, x["meta"]) if t else None
        for dalsi in x.get("dalsi_texty", []):               # tělo dodatku může být v jiné příloze záznamu
            if nal:
                break
            t2 = text_souboru(dalsi)
            nal = najdi_novou_cenu(t2, P, x["meta"]) if t2 else None
            if nal or not t:
                t = t2 or t
        pr = priznaky(t) if t else {}
        if nal:
            stav = "zmena_ceny"
        elif not t:
            stav = "bez_textu"
        elif not (pr.get("vicepr") or pr.get("menepr")) and not re.search(
                r"cen[ay] (dila|za dilo)\w* se (zvys|sniz|men|navys|upravuj)", bezdia(t)):
            stav = "bez_zmeny_ceny"
        else:
            stav = "neurceno"
        ty = typ_hodnoty(x["meta"], B) if x["zdroj"] == "navazany" else ""
        if nal and ty in ("rozdil", "nova_celkova") and not nal.get("potvrzeno_registrem"):
            # Dva nezávislé zdroje se neshodly (cena z textu × hodnota v registru): nevěříme ani jednomu.
            # Smlouva se označí jako neurčená a do statistik změny ceny nejde.
            stav, nal_rozpor, nal = "rozpor_text_registr", nal, None
        elif stav == "bez_zmeny_ceny" and (ty == "rozdil" or (ty == "nova_celkova" and abs(x["meta"] - P) / P > 0.002)):
            # Text o změně ceny mlčí, ale registr u dodatku částku má -> také rozpor (text mohl být špatně přečten)
            stav = "rozpor_text_registr"
        N = nal["N"] if nal else None
        V, M = (nal["V"], nal["M"]) if nal else (0.0, 0.0)
        if stav in ("neurceno", "bez_textu") and ty == "rozdil":
            # záloha: hodnota v registru je rozdíl ceny; znaménko z ní nepoznáme, bereme ji jako navýšení
            N, V, M, stav = P + x["meta"], x["meta"], 0.0, stav + "+registr_rozdil"
        elif stav in ("neurceno", "bez_textu") and ty == "nova_celkova":
            N, V, M, stav = x["meta"], max(x["meta"] - P, 0.0), max(P - x["meta"], 0.0), stav + "+registr_celkova"
        if ty == "nova_celkova":
            lehka_celk, lehka_rozd, lehka_ma = x["meta"], 0.0, True
        elif ty == "rozdil":
            lehka_rozd, lehka_ma = lehka_rozd + x["meta"], True
        dodatky.append({"id_smlouvy": sid, "id_dodatku": x["id"], "zdroj": x["zdroj"], "cislo_dodatku": x["cd"] or "",
                        "datum": x["datum"], "slov": x["slov"], "stav": stav, "cena_pred": round(P, 2),
                        "cena_po": round(N, 2) if N else "", "zmena": round(N - P, 2) if N else "",
                        "viceprace": round(V, 2) if N else "", "meneprace": round(M, 2) if N else "",
                        "hodnota_v_registru": x["meta"] or "", "typ_hodnoty_v_registru": ty,
                        "body": nal["body"] if nal else "", "kandidatu": nal["kandidatu"] if nal else "",
                        "potvrzeno_registrem": nal.get("potvrzeno_registrem", 0) if nal else "",
                        **{k: pr.get(k, "") for k in ("vicepr", "menepr", "termin", "nepredvid",
                                                      "pozadavek_objednatele", "projekt", "par222")},
                        "dukaz": nal["radek"] if nal else "", "nazev": x["nazev"][:90]})
        if N:
            n_zmen += 1
            sum_V += V
            sum_M += M
            obrat_presny &= (nal["presne"] if nal and stav == "zmena_ceny" else 0)
            P = N
        elif stav.startswith(("neurceno", "bez_textu", "rozpor")):
            n_neurc += 1
        for k, v in pr.items():
            if v and k != "par222":
                prizn[k] += 1
    # „lehká metoda“ = jen pole registru, bez čtení textů (stejná pravidla jako rs_kohorta.py):
    # hodnoty navázaných dodatků; když žádné nejsou, vezme se dnešní hodnota původního záznamu, pokud ji město přepsalo
    if lehka_ma:
        lehka = (lehka_celk if lehka_celk is not None else B) + lehka_rozd
    elif nyni and abs(nyni - B) / B > 0.002:
        lehka = nyni
    else:
        lehka = B
    retezy.append({"id": sid, "ids": d["ids"], "podpis": datum(d), "utvar": d.get("utvar", ""),
                   "dodavatel": d["dodavatel"], "predmet": d["predmet"][:150],
                   "stavba": int(stavba), "oblasti": "|".join(d["oblasti"]), "cena_puvodni": round(B, 2),
                   "cena_v_registru_nyni": round(nyni, 2) if nyni else "",
                   "registr_prepsan": int(bool(nyni) and abs(nyni - B) / B > 0.002),
                   "n_verzi": len(d["verze"]) + 1, "n_dodatku": len(poradi),
                   "n_priloh_dodatek": sum(1 for x in poradi if x["zdroj"] == "priloha"),
                   "n_navazanych": sum(1 for x in poradi if x["zdroj"] == "navazany"),
                   "n_se_zmenou_ceny": n_zmen, "n_neurcenych": n_neurc, "cena_konecna": round(P, 2),
                   "zmena_pct": round((P - B) / B * 100, 2),
                   # obrat = vícepráce + méněpráce k původní ceně: kolik z díla se během stavby „přepsalo“
                   "viceprace": round(sum_V, 2), "meneprace": round(sum_M, 2),
                   "obrat_pct": round((sum_V + sum_M) / B * 100, 2), "obrat_presny": obrat_presny if n_zmen else "",
                   "cena_konecna_lehka": round(lehka, 2), "termin": prizn["termin"], "nepredvid": prizn["nepredvid"],
                   "pozadavek_objednatele": prizn["pozadavek_objednatele"], "projekt": prizn["projekt"],
                   "odkaz": f"https://www.hlidacstatu.cz/Detail/{sid}"})

for nazev, radky in (("retezy.csv", retezy), ("dodatky.csv", dodatky)):
    with open(S / nazev, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(radky[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(radky)

print("základních smluv:", len(retezy), "| z toho stavební práce (podle předmětu):", sum(r["stavba"] for r in retezy),
      "| cena v registru přepsána proti původní:", sum(r["registr_prepsan"] for r in retezy))
print("dodatků celkem:", len(dodatky), "| stavy:", dict(Counter(x["stav"] for x in dodatky)))
print("zdroj dodatku:", dict(Counter(x["zdroj"] for x in dodatky)))
