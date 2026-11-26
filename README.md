# Dodatky stavebních zakázek měst

O kolik městům narůstá cena staveb přes dodatky ke smlouvě o dílo? Pilot nad Registrem smluv: řetěz smlouva → dodatky → konečná cena, srovnání měst, krajů a velikostí zakázek.

**Stav: pilot z 25. 11. 2026.** Čísla vznikla automatickým čtením smluv a dodatků a nejsou ručně ověřená. Dashboard: `docs/index.html`.

## Co pilot ukázal

| | Kopřivnice (všechny smlouvy) | Česko (náhodný vzorek) |
|---|---|---|
| Smlouvy | 91 stavebních smluv od 1,65 mil. Kč bez DPH, podpis 2016–2024 | 97 smluv nad 1 mil. Kč bez DPH, podpis 2023, města se sídlem ORP |
| Má aspoň jeden dodatek | 71 % | 60 % (95% interval 50–69 %) |
| Cena se změnila | 62 % | 46 % (36–56 %) |
| Typická změna tam, kde se cena změnila (medián) | +4,5 % | +6,1 % (2,9–10,1) |
| Průměr přes všechny smlouvy | +3,7 % | +3,9 % |
| Korunově (součet konečných proti původním cenám) | +7,9 % | +8,6 % |

- Typická smlouva cenu nezmění nebo jen málo. Průměr a korunový nárůst táhne menšina zakázek, hlavně velkých.
- Čistá změna ceny skrývá **obrat**: u kopřivnických smluv se změnou je medián čisté změny 5,5 %, ale vícepráce a méněpráce dohromady dělají 9,4 % původní ceny.
- Jen z vyplněných polí registru (bez čtení textů) vyjde konečná cena správně u 36 z 61 kopřivnických smluv s dodatkem. Hodnota u dodatku nemá znaménko a dodatky přiložené k původnímu záznamu hodnotu nemají vůbec.

### Standard podle typu (průměr změny ceny přes všechny smlouvy skupiny)

| Skupina | Kopřivnice | Česko (vzorek) |
|---|---|---|
| rekonstrukce | +4,1 % (48 smluv; běžné pásmo 0 až +6,1 %) | +3,5 % (35; 0 až +6,7 %) |
| oprava a údržba | +4,5 % (18) | +5,0 % (20) |
| novostavba | +4,8 % (13) | +4,3 % (13) |
| chodníky a cyklostezky | málo smluv | +0,1 % (8) |
| komunikace a parkoviště | +3,2 % (16) | +3,3 % (18) |
| školy (ZŠ, MŠ) | +1,5 % (21) | +3,1 % (19) |
| památky a kultura | +3,9 % (6) | +11,0 % (9) |
| mosty a lávky | +8,5 % (7) | málo smluv |

Skupiny mají jednotky až desítky smluv – je to směr, ne norma. Na normu pro „města typu X a stavby typu Y“ je potřeba plný sběr.

## Zdroje dat

| Kanál | K čemu | Omezení |
|---|---|---|
| Otevřená data registru `data.smlouvy.gov.cz` (`index.xml`, `dump_RRRR_MM.xml`) | celostátní průchod: všechny záznamy a jejich verze | 70–190 MB za měsíc, ~13,7 GB celkem, bez komprese; **nejvýš 2 souběžná spojení** (při 8 server na půl hodiny přestal odpovídat); obor smlouvy ani text příloh v nich nejsou |
| Hlídač státu – veřejné hledání a detail smlouvy | řetěz smlouva → dodatky pro jedno město nebo vzorek, čistý text příloh (včetně OCR) | veřejné stránky jen šetrně (40 dotazů za minutu, dávkově); pro větší objem API Hlídače s tokenem |
| ČSÚ | počet obyvatel měst | – |

Licence dat: CC BY. U každého převzatého údaje uvádět „Hlídač státu / Registr smluv“ a ID smlouvy.

## Skripty

Spouštět z kořene repa. Python vždy s `-I` (zpracovává stažená data).

| Skript | Co dělá |
|---|---|
| `skripty/obce_export.py` | převodník IČO → obec, kraj, ORP, obyvatelé (`data/obce.csv`); čte místní SQLite s daty ČSÚ |
| `skripty/rs_stahni.sh` + `rs_filtr.py` | proudově stáhne měsíční export a nechá si jen záznamy, kde je stranou obec |
| `skripty/rs_struktura.py` | jak města dodatky zveřejňují: podíl s vazbou na původní smlouvu a s vyplněnou hodnotou |
| `skripty/rs_kohorta.py`, `rs_souhrn.py` | „lehká metoda“: stavební smlouvy měst podepsané v daném roce, dodatky a změna ceny jen z metadat; vrstvené tabulky |
| `skripty/hs_hledej.py` | hledání na Hlídači dotazovacím jazykem → CSV |
| `skripty/pilot_mesto.py` | pro seznam smluv stáhne detaily, nejstarší verzi záznamu, navázané dodatky a texty dodatků |
| `skripty/retezy.py` | složí řetěz smlouva → dodatky → konečná cena; cenu, vícepráce a méněpráce čte z textu dodatků |
| `skripty/retezy_souhrn.py`, `retezy_kontrola.py` | souhrn řetězů; křížová kontrola ceny z textu proti hodnotě v registru |
| `skripty/vzorek_priprav.py`, `vzorek_souhrn.py` | náhodný vzorek z celostátní kohorty a odhad s intervaly spolehlivosti |
| `skripty/typy.py`, `typy_souhrn.py` | třídění podle druhu stavby a povahy prací; standard (běžné pásmo) a extrémy po skupinách |
| `skripty/web_build.py` | sestaví `docs/data.js` pro dashboard (bez názvů dodavatelů a ostatních měst) |

### Postup

```bash
# 1) celostátně: stáhnout měsíce (2 souběžně, měsíc ~15–20 min) a spočítat kohortu
bash skripty/rs_stahni.sh 2023_09 2023_10 2023_11
python -I skripty/rs_struktura.py data/rs data/obce.csv
python -I skripty/rs_kohorta.py data/rs data/obce.csv data/cr 2023 1000000
python -I skripty/rs_souhrn.py data/cr/kohorta_2023.csv 00298077

# 2) jedno město do hloubky (stavebnictví nad 2 mil. Kč s DPH)
python -I skripty/hs_hledej.py data/kop/zaklad.csv "icoPlatce:00298077 AND oblast:stav AND cena:>1999999" 12
python -I skripty/pilot_mesto.py data/kop/zaklad.csv data/kop
python -I skripty/retezy.py data/kop
python -I skripty/retezy_kontrola.py data/kop
python -I skripty/retezy_souhrn.py data/kop 2024 1650000

# 3) náhodný vzorek z celostátní kohorty (úplné dohledání dodatků)
python -I skripty/vzorek_priprav.py data/cr/kohorta_2023.csv data/vzorek 100 50000000
python -I skripty/pilot_mesto.py data/vzorek/zaklad.csv data/vzorek
python -I skripty/retezy.py data/vzorek
python -I skripty/vzorek_souhrn.py data/vzorek

# 4) dashboard
python -I skripty/web_build.py            # s detailem smluv města; --bez-detailu-mesta jen souhrny
python -m http.server 8796 --bind 127.0.0.1 --directory docs
```

Stažené exporty leží v `data/rs/` zabalené (`.jsonl.gz`); před výpočtem je rozbal (`python -m gzip -d data/rs/*.gz`).

## Užitečné dotazy na Hlídači

| Dotaz | Co vrátí |
|---|---|
| `icoPlatce:00298077 AND oblast:stav AND cena:>1999999` | stavební smlouvy města nad 2 mil. Kč |
| `oblasti:stav_konstr` | jen podobor (konstrukční a stavební práce) |
| `navazanyZaznam:<ID smlouvy>` | dodatky navázané na původní smlouvu |
| `idSmlouvy:<ID smlouvy>` | aktuální verze záznamu (Hlídač čísluje verze, registr smlouvy) |
| `predmet:dodatek AND NOT navazanyZaznam:[1 TO *]` | dodatky bez vazby na původní smlouvu |

## Jak se počítá

- **Jednotka je stavební akce** = smlouva o dílo a všechny její dodatky. Změna se počítá proti ceně v původní smlouvě, bez DPH.
- **Město = sídlo obce s rozšířenou působností (205).** Menší obce smlouvy uveřejňovat nemusí (zákon o registru smluv, § 3 odst. 2 písm. k). Praha a městské části zahrnuty nejsou.
- **Výchozí cena se bere z nejstarší verze záznamu.** Aktuální verze může nést už konečnou cenu – město ji při zveřejnění dodatku někdy přepíše (v Kopřivnici u 6 z 91 smluv).
- **Dodatek se hledá třemi cestami:** navázaný záznam · příloha s „dodatek“ v názvu u pozdější verze původního záznamu · samostatný záznam bez vazby (shoda města, dodavatele a čísla nebo předmětu).
- **Cena z textu:** dodatek uvádí dosavadní cenu, změnu a novou cenu a často opakuje celou historii. Skript staví z čísel v textu řetěz cen a novou cenu přijme jen tehdy, když vyjde součtem (dosavadní + vícepráce − méněpráce = nová). Hodnota dodatku v registru slouží jako rozhodčí a křížová kontrola.
- **Rozpor = neurčeno.** Když se cena z textu a hodnota v registru neshodnou, smlouva se označí a do statistik změny ceny nejde.
- **Obrat** = vícepráce + méněpráce k původní ceně. Kde dodatek uvádí jen výsledný rozdíl, je obrat dolní mez.
- **Stavební práce se v exportech poznávají podle slov v předmětu** (registr obor neeviduje). Na vzorku 60 smluv bylo 5 zařazeno chybně, pravidla jsou od té doby zpřísněná.
- **Typ stavby** má dva rozměry, oba podle slov v předmětu: *druh* (mosty a lávky · školy · památky a kultura · sport a hřiště · bydlení a sociální · sítě a osvětlení · chodníky a cyklostezky · komunikace a parkoviště · veřejný prostor · ostatní budovy) a *povaha prací* (novostavba · rekonstrukce · oprava a údržba · demolice). Pravidla jdou shora dolů, první shoda vyhrává.
- **Standard** = běžné pásmo změny ceny ve skupině (dolní až horní čtvrtina, medián, průměr, směrodatná odchylka) přes všechny smlouvy skupiny včetně těch beze změny.
- **Extrém** = smlouva nad horní hradbou své skupiny: horní čtvrtina + 1,5násobek rozpětí čtvrtin, nejméně +10 %. U skupin pod 8 smluv se bere hradba celého souboru.

## Známá slabá místa

- **Čtení cen je vyladěné na kopřivnické šablony dodatků.** Tam se cena z textu shodla s registrem u 71 ze 72 dodatků, u jiných měst zatím jen u 73 z 87. Rozpory jsou vyřazené, takže vzorek ČR má méně smluv s jistou cenou (85 z 97).
- **Lehká metoda je dolní mez.** Stažených měsíců je pět (4, 6, 7, 8/2023 a 10/2024); ze 58 smluv vzorku s dodatkem jich zachytila 14.
- Registr ukazuje sjednané ceny, ne zaplacené. Vícepráce zadané jako nová zakázka v řetězu nejsou.
- Důvod dodatku (termín, nepředvídané okolnosti, požadavek objednatele, odchylka od projektu) je vyčtený podle slov v textu, ne posouzený člověkem.
- Smlouvy z posledních dvou let ještě nemusí být dokončené. Málo dodatků neznamená dobře připravenou stavbu.
- Tatáž smlouva bývá v registru dvakrát; souhrn duplicity vyřazuje podle dodavatele, data a ceny.

## Co v repu není

Složka `data/` (stažené stránky, texty dodatků se jmény podepisujících, tabulky s názvy dodavatelů) zůstává jen na disku. Všechno jde znovu vyrobit skripty výše. Publikuje se jen `docs/data.js` – agregace a u vybraného města předmět smlouvy, ceny a odkaz na veřejný záznam.
