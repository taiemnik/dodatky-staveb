# -*- coding: utf-8 -*-
"""Vytáhne z BI-CHECK seznam obcí s IČO, krajem, ORP a počtem obyvatel -> obce.csv.

Proč:  registr smluv zná jen IČO. Abychom uměli říct „město, ORP, kraj, velikost“,
       potřebujeme převodník IČO -> území. BI-CHECK ho má (tabulka uzemi) a má i obyvatele z ČSÚ.
Vstup: cesta k bicheck.sqlite (jen čtení), cesta k výstupnímu CSV
"""
import csv
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
db, cil = sys.argv[1], sys.argv[2]
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)   # mode=ro: do databáze nic nezapisujeme
cur = con.cursor()

# 1) jaké sloupce má pohled s hodnotami a jak se jmenuje ukazatel počtu obyvatel
print("sloupce v_hodnota:", [r[1] for r in cur.execute("PRAGMA table_info(v_hodnota)")])
print("sloupce ukazatel:", [r[1] for r in cur.execute("PRAGMA table_info(ukazatel)")])
uk = cur.execute("SELECT id, nazev FROM ukazatel WHERE id LIKE 'csu:obyvatel%' ORDER BY id").fetchall()
print("ukazatele obyvatel:", uk[:12])
con.row_factory = sqlite3.Row
radky = con.execute("SELECT * FROM v_hodnota WHERE ukazatel_id='csu:obyvatel_1_1' AND uzemi_id='obec:599565' "
                    "ORDER BY obdobi DESC LIMIT 2").fetchall() if uk else []
for r in radky:
    print("ukázka:", dict(r))

# 2) vlastní export: obce + městské části s IČO; obyvatelé = poslední dostupný rok ukazatele
sql = """
SELECT u.ico, u.nazev, u.typ, u.kod, u.kraj_id, k.nazev AS kraj, u.orp_id, u.sidlo_orp, u.bvs_skupina,
       (SELECT h.hodnota FROM hodnota h WHERE h.ukazatel_id='csu:obyvatel_1_1' AND h.uzemi_id=u.id
        ORDER BY h.obdobi DESC LIMIT 1) AS obyvatel,
       (SELECT h.obdobi FROM hodnota h WHERE h.ukazatel_id='csu:obyvatel_1_1' AND h.uzemi_id=u.id
        ORDER BY h.obdobi DESC LIMIT 1) AS obyvatel_rok
FROM uzemi u LEFT JOIN uzemi k ON k.id = u.kraj_id
WHERE u.typ IN ('obec','mestska_cast') AND u.ico IS NOT NULL AND u.ico <> ''
"""
rows = con.execute(sql).fetchall()
with open(cil, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(rows[0].keys())
    for r in rows:
        w.writerow([("" if v is None else v) for v in tuple(r)])
print("obcí s IČO:", len(rows), "| sídel ORP:", sum(1 for r in rows if r["sidlo_orp"] == 1),
      "| s počtem obyvatel:", sum(1 for r in rows if r["obyvatel"] is not None),
      "| městských částí:", sum(1 for r in rows if r["typ"] == "mestska_cast"))
dupl = len(rows) - len({r["ico"] for r in rows})
print("duplicitních IČO:", dupl)
