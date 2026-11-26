#!/usr/bin/env bash
# Proudové stažení měsíčních exportů Registru smluv: curl -> filtr obcí (nic velkého se neukládá).
#
# Použití (z kořene složky analýzy):  bash skripty/rs_stahni.sh 2023_09 2023_10 2023_11
# Hotový měsíc (existuje data/rs/rs_<značka>.jsonl) se přeskočí, skript jde pustit znovu po výpadku.
#
# POZOR na souběh: server data.smlouvy.gov.cz dává ~150 kB/s na spojení a při 8 souběžných spojeních
# přestal 25. 11. 2026 odpovídat úplně. Proto jen 2 přenosy naráz (SOUBEH=2). Měsíc trvá 15–20 minut,
# celý registr (2016–2026, ~13,7 GB) je práce na noc až dvě. Nezvyšovat kvůli rychlosti.
#
# Zastavení: na Windows nestačí zastavit tento skript – smyčky xargs/bash a curl běží dál.
# Ukončit je přes PowerShell (Get-CimInstance Win32_Process, filtr na „rs_stahni“ a „data.smlouvy.gov.cz“).
SOUBEH=2
KOREN="$(cd "$(dirname "$0")/.." && pwd)"
jeden() {
  z="$1"
  if [ -f "$KOREN/data/rs/rs_$z.jsonl" ]; then echo "$z: už hotovo"; return; fi
  for pokus in 1 2; do
    # -m 5400: strop 90 minut na měsíc; filtr zapíše konečný soubor jen po dočtení celého XML
    curl -sS -m 5400 "https://data.smlouvy.gov.cz/dump_$z.xml" \
      | python -I "$KOREN/skripty/rs_filtr.py" "$z" "$KOREN/data/obce.csv" "$KOREN/data/rs" \
      && { echo "$z: OK (pokus $pokus) $(date +%H:%M:%S)"; return; }
    echo "$z: pokus $pokus selhal $(date +%H:%M:%S)"; sleep 120      # po výpadku počkat, netlačit
  done
}
export -f jeden; export KOREN
printf "%s\n" "$@" | xargs -P "$SOUBEH" -I{} bash -c 'jeden {}'
echo "KONEC $(date +%H:%M:%S)"
