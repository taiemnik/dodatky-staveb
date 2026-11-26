#!/usr/bin/env bash
# Proudové stažení měsíčních exportů Registru smluv: curl -> filtr obcí (nic velkého se neukládá).
#
# Použití (z kořene repa):
#   bash skripty/rs_stahni.sh 2023_09 2023_10 2023_11      # vyjmenované měsíce
#   bash skripty/rs_stahni.sh vse                          # celý registr od 2016_07, od nejnovějšího měsíce
# Hotový měsíc (existuje data/rs/rs_<značka>.jsonl.gz) se přeskočí, skript jde pustit znovu po výpadku.
# Průběh se zapisuje do data/rs/_stahovani.log.
#
# POZOR na souběh: server data.smlouvy.gov.cz dává ~150 kB/s na spojení a při 8 souběžných spojeních
# přestal 25. 11. 2026 na půl hodiny odpovídat. Proto jen 2 přenosy naráz (SOUBEH=2). Měsíc trvá
# 15–20 minut, celý registr (2016–2026, ~13,7 GB) zhruba 15–20 hodin. Nezvyšovat kvůli rychlosti.
#
# Zastavení: na Windows nestačí zastavit tento skript – smyčky xargs/bash a curl běží dál.
# Ukončit je přes PowerShell (Get-CimInstance Win32_Process, filtr na „rs_stahni“ a „data.smlouvy.gov.cz“).
SOUBEH=2
KOREN="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$KOREN/data/rs"
LOG="$KOREN/data/rs/_stahovani.log"

if [ "$1" = "vse" ]; then
  # seznam měsíců z indexu registru (jen měsíční exporty, ne denní), bez právě běžícího měsíce
  curl -sS -m 120 -o "$KOREN/data/rs/_index.xml" https://data.smlouvy.gov.cz/index.xml
  MESICE=$(python -I -c "
import re, sys, datetime
s = open(sys.argv[1], encoding='utf-8').read()
ted = datetime.date.today().strftime('%Y_%m')
m = set()
for blok in re.findall(r'<dump>(.*?)</dump>', s, flags=re.S):
    if '<den>' in blok:
        continue
    x = re.search(r'<mesic>(\d+)</mesic><rok>(\d+)</rok>', blok)
    z = f'{x.group(2)}_{int(x.group(1)):02d}'
    if z < ted:
        m.add(z)
print(' '.join(sorted(m, reverse=True)))
" "$KOREN/data/rs/_index.xml")
else
  MESICE="$*"
fi

jeden() {
  z="$1"
  if [ -f "$KOREN/data/rs/rs_$z.jsonl.gz" ]; then return; fi
  for pokus in 1 2; do
    # -m 5400: strop 90 minut na měsíc; filtr zapíše konečný soubor jen po dočtení celého XML
    if curl -sS -m 5400 "https://data.smlouvy.gov.cz/dump_$z.xml" \
        | python -I "$KOREN/skripty/rs_filtr.py" "$z" "$KOREN/data/obce.csv" "$KOREN/data/rs" > /dev/null 2>> "$LOG.chyby"; then
      echo "$(date '+%d.%m. %H:%M') $z OK (pokus $pokus)" >> "$LOG"; return
    fi
    echo "$(date '+%d.%m. %H:%M') $z pokus $pokus selhal" >> "$LOG"; sleep 300      # po výpadku počkat, netlačit
  done
}
export -f jeden; export KOREN LOG
echo "$(date '+%d.%m. %H:%M') START: $(echo $MESICE | wc -w) měsíců, souběh $SOUBEH" >> "$LOG"
printf "%s\n" $MESICE | xargs -P "$SOUBEH" -I{} bash -c 'jeden {}'
echo "$(date '+%d.%m. %H:%M') KONEC: hotových měsíců $(ls "$KOREN/data/rs" | grep -c 'jsonl.gz$')" >> "$LOG"
echo "KONEC $(date '+%d.%m. %H:%M'), hotových měsíců: $(ls "$KOREN/data/rs" | grep -c 'jsonl.gz$')"
