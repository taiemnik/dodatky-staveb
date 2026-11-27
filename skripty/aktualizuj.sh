#!/usr/bin/env bash
# Po dalším kusu sběru: přepočítat kohortu 2022–2025, přestavět stránku i lokální aplikaci a uložit commit.
# Odeslání na GitHub (git push) je záměrně zvlášť – až po kontrole toho, co odchází.
# Použití (z kořene repa):  bash skripty/aktualizuj.sh
KOREN="$(cd "$(dirname "$0")/.." && pwd)"
cd "$KOREN" || exit 1
# data/rs_api2 = opravený sběr z 27. 11. 2026 (první sběr v data/rs_api je neúplný, nepoužívat)
MEST=$(ls data/rs_api2 | grep -c 'jsonl.gz$')
python -I skripty/rs_kohorta.py data/rs_api2 data/obce.csv data/cr_api 2022-2025 1000000 | sed -n '3,6p'
python -I skripty/web_build.py --kohorta=data/cr_api/kohorta_2022-2025.csv | head -1
git add docs/index.html docs/data.js skripty README.md
if git diff --cached --quiet; then
  echo "beze změny – není co ukládat"
else
  git commit -q -m "Data: sběr přes API Hlídače státu, hotových měst $MEST z 388 ($(date '+%-d. %-m. %Y'))

Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>"
  git log --oneline | head -1
fi
