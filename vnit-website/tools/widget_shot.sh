#!/bin/bash
# Screenshot a page with the VNIT Assistant open after asking a question:
# tools/widget_shot.sh <page in dist> <png name> <width> <height> "<question>" ["<choice>|<choice>"] [base url]
# With a base url (for example http://127.0.0.1:8010/site/) the page comes from that server.
cd "$(dirname "$0")/.." || exit 1
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
PROFILE="$(cygpath -w "${TEMP:-/tmp}")\vnit-website-edge-profile"
OUT="checks/$2"
enc() { ~/anaconda3/python.exe -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=''))" "$1"; }
if [ -n "$7" ]; then SRC="$7$1?assistant=open"; else SRC="file:///$(cygpath -m "$PWD/dist/$1")?assistant=open"; fi
URL="file:///$(cygpath -m "$PWD/tools/widget_test.html")?w=$3&h=$4&q=$(enc "$5")&choose=$(enc "$6")&src=$(enc "$SRC")"
WIN=$3; [ "$WIN" -lt 600 ] && WIN=600
mkdir -p checks; rm -f "$OUT"
timeout 170 "$EDGE" --headless=new --disable-gpu --no-first-run --hide-scrollbars --allow-file-access-from-files \
  --user-data-dir="$PROFILE" --virtual-time-budget="${WAIT_MS:-8000}" --window-size="$WIN,$4" \
  --screenshot="$(cygpath -w "$PWD/$OUT")" "$URL" >/dev/null 2>&1
for _ in $(seq 1 90); do
  if [ -s "$OUT" ]; then
    [ "$WIN" != "$3" ] && ~/anaconda3/python.exe -c "import sys; from PIL import Image; im=Image.open(sys.argv[1]); im.crop((0,0,int(sys.argv[2]),im.height)).save(sys.argv[1])" "$OUT" "$3"
    echo "saved $OUT"; exit 0
  fi
  sleep 1
done
echo "no screenshot for $1"; exit 1
