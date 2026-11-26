# -*- coding: utf-8 -*-
"""Třídění stavební smlouvy podle předmětu: DRUH stavby (co se staví) a POVAHA prací (jak).

Proč:  „standardní“ nárůst ceny je jiný u chodníku a jiný u rekonstrukce staré budovy. Aby šlo
       hledat extrémy, musí se smlouva srovnávat se stavbami stejného typu.
Jak:   podle slov v předmětu smlouvy (bez diakritiky). Pravidla jdou shora dolů, první shoda vyhrává –
       pořadí je proto součást metody (most na komunikaci je „most“, hřiště u školy je „škola“).
Limit: je to čtení názvu, ne projektu. Co pravidla nepoznají, spadne do „ostatní“.
"""
import re
import unicodedata


def bezdia(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


# (název, vzor) – pořadí = priorita
DRUHY = [
    ("mosty a lávky", r"\bmost(u|y|ni|ek|ku)?\b|\blavk"),
    ("školy (ZŠ, MŠ)", r"\bzs\b|\bms\b|\bzus\b|\bddm\b|zakladni(ch)? skol|materske|matersk|\bskol[ayue]\b|skolk|skolni|druzin|ucebn"),
    ("památky a kultura", r"\bvil[ayu]\b|zamek|zamku|kostel|kapl[ei]|radnic|muze[ua]|kulturn|\bkd\b|kino|divadl"
                          r"|knihovn|pamatk|histori|hradeb|smutecni|obradni"),
    ("sport a hřiště", r"hrist|stadion|koupalist|bazen|sportov|telocvic|\btj\b|sokolovn|pumptrack|kluzist"),
    ("bydlení a sociální", r"\bbyt|bytov|\bbd\b|\bdps\b|pecovatelsk|domov(a|u)? (pro|senior|duchod)|bydleni|komunitni|socialni(ch)? (byt|bydlen|sluz)"),
    ("sítě a osvětlení", r"kanalizac|odkanalizovan|vodovod|destov|verejne(ho)? osvetleni|\bvo\b|teplovod|plynovod|horkovod|\bcov\b"),
    ("chodníky a cyklostezky", r"chodnik|cyklostezk|stezk[ayu]|pro pesi|prechod(u|y)? pro chodce"),
    ("komunikace a parkoviště", r"komunikac|vozovk|silnic|\bmk\b|parkovist|parkovac|zpomalovac|krizovatk|zastavk|povrch(u|y|ů)?\b|\bulic[eiy]?\b|\bul\."),
    ("veřejný prostor", r"namesti|revitalizace centra|verejn(ych|eho|e) prostranstv|\bpark(u|y)?\b|zelen|hrbitov|kolumbari|mobiliar"),
    ("ostatní budovy", r"budov|objekt|dum\b|domu\b|hasic|zbrojnic|urad|\bmu\b|polyfunkc|vymenikov|strech|fasad|zatepl|vytah|kotel|\btzb\b"),
]
POVAHY = [
    ("novostavba", r"demolice a vystavb|novostavb|\bvystavb|vybudovan|\bpristavb|\bnastavb|\bvestavb|realizac[ei] (stavby )?(parkovist|hrist|chodnik)|\bvznik"),
    ("rekonstrukce", r"rekonstrukc|modernizac|stavebni uprav|revitalizac|regenerac|zateplen|snizeni energeticke|energetick\w* (opatren|uspor)"
                     r"|vymen[ayu]|rozsiren|zmena uzivani"),
    ("oprava a údržba", r"oprav|udrzb|sanac|havarij|obnov"),
    ("demolice", r"demolic|odstraneni stavb"),
    # poslední záchyt: „realizace stavby …“ bez slova oprava / rekonstrukce bývá nová stavba
    ("novostavba", r"realizac|zrizeni|zhotoveni stavby|\bstavba\b"),
]


def _prvni(pravidla, predmet, jinak):
    p = bezdia(predmet)
    for nazev, vzor in pravidla:
        if re.search(vzor, p):
            return nazev
    return jinak


def druh(predmet):
    return _prvni(DRUHY, predmet, "ostatní")


def povaha(predmet):
    return _prvni(POVAHY, predmet, "neurčeno")


SEZNAM_DRUHU = [d for d, _ in DRUHY] + ["ostatní"]
SEZNAM_POVAH = list(dict.fromkeys(d for d, _ in POVAHY)) + ["neurčeno"]
