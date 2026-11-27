# Dodatky stavebních zakázek měst

O kolik městům narůstá cena staveb přes dodatky ke smlouvě o dílo? Pilot nad Registrem smluv: řetěz smlouva → dodatky → konečná cena, srovnání měst, krajů a velikostí zakázek.

**Stav: pilot z 25. 11. 2026.** Čísla vznikla automatickým čtením smluv a dodatků a nejsou ručně ověřená. Dashboard: `docs/index.html`.

## Co pilot ukázal

| | Kopřivnice (všechny smlouvy) | Česko (náhodný vzorek) |
|---|---|---|
| Smlouvy | 91 stavebních smluv od 1,65 mil. Kč bez DPH, podpis 2016–2024 | 97 smluv nad 1 mil. Kč bez DPH, podpis 2023, města se sídlem ORP |
| Má aspoň jeden dodatek | 71 % | 60 % (95% interval 50–69 %) |
| Cena se změnila | 62 % (53 z 85 s jistou cenou) | 47 % (38 z 81; interval 36–58 %) |
| Typická změna tam, kde se cena změnila (medián) | +4,6 % | +6,8 % (2,3–10,5) |
| Průměr přes všechny smlouvy | +3,8 % | +4,0 % |
| Korunově (součet konečných proti původním cenám) | +7,9 % | +9,0 % |
| Šance na nárůst 10 % a víc | 13 % | 17 % |
| Šance na anomálii (20 % a víc) | 6 % (5 smluv) | 9 % (7 smluv) |
| Šance na abnormální nárůst (30 % a víc) | 2 % (2 smlouvy) | 2 % (2 smlouvy) |
| Nárůst o 1 mil. Kč a víc | 11 % | 10 % |

Čísla se po zpřísnění ověřovací sady (26. 11.) liší od první verze o jednotky smluv. Aktuální hodnoty jsou vždy v dashboardu a v souborech `data/kop/` a `data/vzorek/` (`souhrn.txt`, `typy.txt`, `sance.txt`).

### Tři měřítka nárůstu

Samotné procento klame: u zakázky za 1 mil. Kč je +300 tis. Kč „abnormálních“ 30 %, u zakázky za 50 mil. Kč je 30 % patnáct milionů. Proto se každá smlouva hodnotí procentem i korunami:

| Pole | Pravidlo (práh 20 % a 1 mil. Kč) | Kopřivnice | Česko (vzorek) |
|---|---|---|---|
| drobné rozšíření | 20 % a víc, pod 1 mil. Kč | 2 smlouvy | 5 smluv, všechny do 5 mil. Kč |
| tichý nárůst | pod 20 %, ale 1 mil. Kč a víc | 6 smluv (4 ze 6 zakázek nad 20 mil. Kč) | 6 smluv (3 z 5 zakázek nad 20 mil. Kč) |
| zásadní | 20 % a víc i 1 mil. Kč a víc | 3 smlouvy | 2 smlouvy |

### Typ města

Kategorie podle typu úřadu: statutární město (26) · obec III. typu (179) · obec II. typu (183); malé obce a Praha se neberou. **Obce II. typu z registru srovnávat nejde** – smlouvy uveřejňovat nemusí a v pěti stažených měsících je jen 14 stavebních smluv ze 6 obcí ze 183. Ve vzorku ČR: statutární města 30 smluv, nárůst 20 % a víc u 1; obce III. typu 51 smluv, u 6.

### Stačí metadata?

Ne na přesnou cenu, ano jako síto. Na 192 smlouvách s cenou ověřenou z textu trefila pole registru pásmo změny u 83 % a našla 11 ze 13 nárůstů nad 20 %. Chybuje tam, kde je dodatek přiložen k původnímu záznamu (cena v polích chybí), a u znaménka (zlevnění −16 % se tváří jako +16 %). Doporučený postup: celý registr z metadat jako síto, extrémy ověřit čtením dodatků.

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

### Pravidla Hlídače státu (licence platná od 8. 11. 2026)

- Data a obsah jsou pod **CC BY 4.0**: smí se sdílet i upravovat, i komerčně, s uvedením zdroje. Tvar: „Zdroj: Hlídač státu“ s odkazem na konkrétní záznam, odkaz na licenci, u upravených dat „vlastní výpočet“.
- **Automatizované stahování webu se počítá jako převzetí podstatné části databáze** – zdroj je pak povinný.
- **Držitel API klíče** (i bezplatného, platí i pro MCP server) uvádí zdroj u každého jednotlivého údaje, který zveřejní nebo předá dál, včetně výstupů aplikací a AI asistentů. Po výzvě má 30 dnů na nápravu, jinak smluvní pokuta 600 000 Kč za každý nenapravený případ. Klíč je jen pro uživatele a jeho zaměstnance; limity se nesmí obcházet více účty.
- Bezplatný tarif má omezený počet volání (čísla nejsou veřejná, jsou vidět po přihlášení na `api.hlidacstatu.cz`). Placené: 12 000 Kč za 6 měsíců (jen veřejné zakázky), 250 000 Kč ročně (vše, bez povinnosti uvádět zdroj).
- Texty smluv a příloh licence Hlídače nekryje (patří autorům); osobní údaje si každý zpracovává na vlastní odpovědnost podle GDPR.

Plné znění: https://www.hlidacstatu.cz/news/licence a https://www.hlidacstatu.cz/news/provoznipodminky.

### Token k API

Token patří do souboru `.env` v kořeni repa (je v `.gitignore`, do gitu se nedostane). Jeden řádek, bez uvozovek a mezer:

```
HLIDAC_STATU_API_TOKEN=sem-vložit-token
```

Skript `skripty/hs_api.py` si ho přečte sám, nikam ho nevypisuje a curl-u ho předává standardním vstupem. Zkouška spojení a limitů: `python -I skripty/hs_api.py test`. Pozor na zálohy složky mimo git – `.env` do nich nepatří.

## Skripty

Spouštět z kořene repa. Python vždy s `-I` (zpracovává stažená data).

| Skript | Co dělá |
|---|---|
| `skripty/obce_export.py` | převodník IČO → obec, kraj, ORP, obyvatelé (`data/obce.csv`); čte místní SQLite s daty ČSÚ |
| `skripty/rs_stahni.sh` + `rs_filtr.py` | proudově stáhne měsíční export a nechá si jen záznamy, kde je stranou obec |
| `skripty/rs_struktura.py` | jak města dodatky zveřejňují: podíl s vazbou na původní smlouvu a s vyplněnou hodnotou |
| `skripty/rs_kohorta.py`, `rs_souhrn.py` | „lehká metoda“: stavební smlouvy měst podepsané v daném roce, dodatky a změna ceny jen z metadat; vrstvené tabulky |
| `skripty/hs_api.py`, `api_sber.py` | API Hlídače s tokenem z `.env`; plný sběr metadat stavebních smluv a dodatků 388 měst od roku 2022 do `data/rs_api2/` (jeden dotaz za 4 s, jde přerušit a pustit znovu; u každého města kontroluje úplnost) |
| `skripty/uplnost_api.py` | kolik smluv známých z exportů registru sběr přes API nenajde – kontrola úplnosti po každém sběru |
| `skripty/hs_hledej.py` | hledání na Hlídači dotazovacím jazykem → CSV |
| `skripty/pilot_mesto.py` | pro seznam smluv stáhne detaily, nejstarší verzi záznamu, navázané dodatky a texty dodatků |
| `skripty/retezy.py` | složí řetěz smlouva → dodatky → konečná cena; cenu, vícepráce a méněpráce čte z textu dodatků |
| `skripty/retezy_souhrn.py`, `retezy_kontrola.py` | souhrn řetězů; křížová kontrola ceny z textu proti hodnotě v registru |
| `skripty/vzorek_priprav.py`, `vzorek_souhrn.py` | náhodný vzorek z celostátní kohorty a odhad s intervaly spolehlivosti |
| `skripty/typy.py`, `typy_souhrn.py` | třídění podle druhu stavby a povahy prací; standard (běžné pásmo) a extrémy po skupinách |
| `skripty/kategorie_mest.py` | typ města do `data/obce.csv`: statutární · III. typ · II. typ (číselník ČSÚ č. 61) |
| `skripty/sance_souhrn.py` | šance na nárůst 10 / 20 / 30 % a o 1 mil. Kč podle velikosti zakázky, typu města a typu stavby |
| `skripty/lehka_presnost.py` | jak přesně jdou změna ceny a anomálie poznat jen z polí registru |
| `skripty/csu_obyvatele.py` | počet obyvatel 388 měst k 1. 1. z otevřených dat ČSÚ (sada OBY02A) do `data/obce.csv` |
| `skripty/web_build.py` | sestaví `docs/data.js` pro dashboard a lokální aplikaci v jednom souboru `dodatky-staveb.html` (otevře se dvojklikem); bez názvů dodavatelů |

### Dvě chyby sběru, na které si dát pozor (27. 11. 2026)

1. **Stránkování s výchozím řazením ztrácí záznamy.** Hledání Hlídače (API i web) řadí podle relevance; u dotazů složených jen z filtrů má většina záznamů stejné skóre a na dalších stránkách se část záznamů opakuje a část chybí. Zkouška na Prostějově: 190 vrácených záznamů, jen 141 různých. První sběr (26.–27. 11., `data/rs_api/`) tak ztratil zhruba čtvrtinu smluv (z 1 154 smluv známých z exportů registru jich našel 74 %). Oprava: řadit podle času zveřejnění (`razeni=2`) a u každého dotazu porovnat počet různých záznamů s údajem `total`. Totéž platí pro `hs_hledej.py` – seznam Kopřivnice z pilotu měl 183 záznamů ze 197.
2. **Dodatky nehledat podle slova „dodatek“ a oboru.** Dotaz `oblast:stav AND predmet:dodatek` našel 7 z 12 dodatků známých z exportů; dotaz přes vazbu `navazanyZaznam:[1 TO *]` všech 12. Sběr proto bere všechny navázané záznamy města a nechává si ty, které se váží ke stavební smlouvě.

Odpověď API se navíc nesmí ukládat do společného souboru: dva současně běžící skripty si ji přepisovaly (opraveno v `hs_api.py`, odpověď se čte ze standardního výstupu).

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

- **Plný sběr z otevřených dat registru se nepovedl.** Server `data.smlouvy.gov.cz` 25. 11. po zhruba 1,5 GB přenosů přestal odpovídat a 26. 11. shodil i dva souběžné přenosy do dvou minut. Stahování je zastavené. Cesty dál: API Hlídače státu s tokenem, nebo jedno pomalé spojení po malých dávkách přes více dní.

- **Čtení cen je vyladěné na kopřivnické šablony dodatků.** Tam se cena z textu shodla s registrem u 71 ze 72 dodatků, u jiných měst zatím jen u 73 z 87. Rozpory jsou vyřazené, takže vzorek ČR má méně smluv s jistou cenou (85 z 97).
- **Lehká metoda je dolní mez.** Stažených měsíců je pět (4, 6, 7, 8/2023 a 10/2024); ze 58 smluv vzorku s dodatkem jich zachytila 14.
- Registr ukazuje sjednané ceny, ne zaplacené. Vícepráce zadané jako nová zakázka v řetězu nejsou.
- Důvod dodatku (termín, nepředvídané okolnosti, požadavek objednatele, odchylka od projektu) je vyčtený podle slov v textu, ne posouzený člověkem.
- Smlouvy z posledních dvou let ještě nemusí být dokončené. Málo dodatků neznamená dobře připravenou stavbu.
- Tatáž smlouva bývá v registru dvakrát; souhrn duplicity vyřazuje podle dodavatele, data a ceny.

## Co v repu není

Složka `data/` (stažené stránky, texty dodatků se jmény podepisujících, tabulky s názvy dodavatelů) zůstává jen na disku. Všechno jde znovu vyrobit skripty výše. Publikuje se jen `docs/data.js` – agregace a u vybraného města předmět smlouvy, ceny a odkaz na veřejný záznam.
