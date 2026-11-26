# -*- coding: utf-8 -*-
"""Volání API Hlídače státu s osobním tokenem.

Token:   soubor .env v kořeni repa, řádek HLIDAC_STATU_API_TOKEN=…  (soubor je v .gitignore). Když .env chybí,
         vezme se stejnojmenná proměnná prostředí. Hodnota se nikde nevypisuje ani neukládá.
Volání:  přes curl (Python na pracovním PC neprojde TLS). Hlavička s tokenem jde curl-u standardním vstupem,
         takže není vidět v seznamu procesů ani v logu.
Pravidla Hlídače: zdroj uvádět u každého zveřejněného údaje (odkaz je v každém záznamu), limity tarifu neobcházet.
Test:    python -I skripty/hs_api.py test   -> stav odpovědi, limity z hlaviček, názvy polí prvního záznamu
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

KOREN = Path(__file__).resolve().parent.parent
API = "https://api.hlidacstatu.cz/api/v2"
KLIC = "HLIDAC_STATU_API_TOKEN"
PAUZA = 1.0                       # sekundy mezi dotazy; bezplatný tarif má omezený počet dotazů za sekundu i hodinu


def nacti_token():
    """Token z .env (KLÍČ=hodnota), jinak z prostředí. Nikdy ho nevypisovat."""
    env = KOREN / ".env"
    if env.exists():
        for radek in env.read_text(encoding="utf-8-sig").splitlines():
            if radek.strip().startswith(KLIC + "="):
                return radek.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get(KLIC, "")


def volej(cesta, parametry=None, schema="Token"):
    """Jeden dotaz na API. Vrátí (stav HTTP, hlavičky odpovědi jako slovník, tělo jako JSON nebo text)."""
    token = nacti_token()
    if not token:
        sys.exit(f"Chybí token: vytvoř {KOREN / '.env'} podle .env.example.")
    url = f"{API}/{cesta}" + ("?" + urllib.parse.urlencode(parametry) if parametry else "")
    pracovni = KOREN / "data" / "api"
    pracovni.mkdir(parents=True, exist_ok=True)
    hlav, telo = pracovni / "_hlavicky.txt", pracovni / "_telo.json"
    # konfigurace curl-u standardním vstupem: token se nedostane na příkazovou řádku ani na disk
    konfig = f'header = "Authorization: {schema} {token}"\nheader = "Accept: application/json"\n'
    r = subprocess.run(["curl", "-sS", "-m", "90", "-K", "-", "-D", str(hlav), "-o", str(telo), "-w", "%{http_code}", url],
                       input=konfig.encode("utf-8"), capture_output=True)
    time.sleep(PAUZA)
    stav = r.stdout.decode("ascii", "replace").strip()
    hlavicky = {}
    if hlav.exists():
        for radek in hlav.read_text(encoding="utf-8", errors="replace").splitlines():
            if ":" in radek:
                k, v = radek.split(":", 1)
                hlavicky[k.strip().lower()] = v.strip()
    text = telo.read_text(encoding="utf-8", errors="replace") if telo.exists() else ""
    try:
        return stav, hlavicky, json.loads(text)
    except ValueError:
        return stav, hlavicky, text.replace(token, "***")[:500]


def hledej_smlouvy(dotaz, strana=1, razeni=0):
    """Hledání smluv dotazovacím jazykem Hlídače (stejný jako na webu)."""
    return volej("smlouvy/hledat", {"dotaz": dotaz, "strana": strana, "razeni": razeni})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2 or sys.argv[1] != "test":
        sys.exit("Použití: python -I skripty/hs_api.py test")
    stav, hl, data = hledej_smlouvy("icoPlatce:00298077 AND oblast:stav AND cena:>1999999")
    if stav == "401":                                   # některé verze API chtějí „Bearer“ místo „Token“
        stav, hl, data = volej("smlouvy/hledat", {"dotaz": "icoPlatce:00298077 AND oblast:stav AND cena:>1999999", "strana": 1}, "Bearer")
    print("stav HTTP:", stav)
    print("hlavičky s limity:", {k: v for k, v in hl.items() if any(s in k for s in ("limit", "remaining", "retry", "quota"))} or "žádné")
    if isinstance(data, dict):
        print("pole odpovědi:", list(data.keys()))
        zaznamy = next((v for v in data.values() if isinstance(v, list)), [])
        print("záznamů na stránce:", len(zaznamy), "| celkem:", data.get("total", data.get("Total", "?")))
        if zaznamy:
            print("pole záznamu:", sorted(zaznamy[0].keys()))
    else:
        print("odpověď:", data)
