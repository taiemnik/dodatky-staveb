# -*- coding: utf-8 -*-
"""Společná pravidla: jak poznat dodatek přiložený k původní smlouvě podle názvu souboru.

Proč:   města dodatek často nezveřejní jako vlastní záznam, ale přiloží ho k původní smlouvě (nová verze
        záznamu). Pilot z 25. 11. 2026 takovou přílohu poznal jen podle slova „dodat“ v názvu souboru.
        Kopřivnice ale soubory jmenuje i „D1.pdf“, „DOD_1_SoD_….pdf“, „SOD_DOD2_….pdf“, „Dod1.doc“ –
        u nejméně šesti smluv tak pilot hlásil „bez dodatku“, přestože dodatek v registru je.
Pozor:  krátké „D1“ je i označení části projektové dokumentace (D.1.1, D1_4_elektro). Proto se u názvů
        bez slova „dodat“ ještě čte začátek textu přílohy – musí se v něm mluvit o dodatku (viz over_textem).
"""
import re
import unicodedata


def bezdia(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


# tři podoby názvu, od nejjistější: „dodatek…“ · „dod1“, „DOD_2“, „dod č. 3“ · samotné „D1“, „D_2“
RE_DODAT = re.compile(r"dodat[a-z]*[\W_]*(?:c|cislo)?[\W_]*(\d{1,2})?(?!\d)")
RE_DOD = re.compile(r"(?:^|[\W_])dod[\W_]*(?:c[\W_]*)?(\d{1,2})(?!\d)")
RE_D = re.compile(r"(?:^|[\W_])d[\W_]?(\d{1,2})(?=$|[_\-\s]|\.[a-z])")


def druh_nazvu(nazev):
    """'dodat' | 'dod' | 'd' | '' – jak moc název přílohy vypadá jako dodatek."""
    b = bezdia(nazev)
    if "dodat" in b:
        return "dodat"
    if RE_DOD.search(b):
        return "dod"
    return "d" if RE_D.search(b) else ""


def cislo_prilohy(nazev):
    """Číslo dodatku z názvu souboru (Dodatek_č.2 -> 2, SOD_DOD1 -> 1, D2-P1 -> 2), jinak None."""
    b = bezdia(nazev)
    for vzor in (RE_DODAT, RE_DOD, RE_D):
        m = vzor.search(b)
        if m and m.group(1):
            return int(m.group(1))
    return None


RE_NADPIS_DODATKU = re.compile(r"dodat(?:ek|ku|kem)\s*(?:c\b|c\.|cislo|\d)")


def over_textem(text):
    """Je příloha dodatkem? Hledá nadpis „Dodatek č. 1…“ / „dodatku č. 2“ na začátku textu.
    Samotné „dodat“ nestačí: nájemní smlouva k „lávce přes dálnici D10“ má v názvu D10 a v textu
    „dodatečné“ – první verze pravidla ji 27. 11. 2026 vzala za dodatek."""
    return bool(RE_NADPIS_DODATKU.search(bezdia(text[:1500])))


def priloha_je_dodatek(p):
    """p = příloha z detaily.jsonl. Název se slovem „dodat“ stačí sám; ostatní podoby jen s potvrzením z textu
    (pole overeno_textem doplňuje pilot_dopln_api.py). „DOD1“ bez čitelného textu bereme také – sken dodatku."""
    druh = druh_nazvu(p.get("nazev", ""))
    if druh == "dodat":
        return True
    if druh == "dod":
        return p.get("overeno_textem") is not False and "overeno_textem" in p
    return druh == "d" and p.get("overeno_textem") is True
