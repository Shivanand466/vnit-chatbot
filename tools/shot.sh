#!/bin/bash
# Screenshot the chat page served on a test port with headless Edge:
#   tools/shot.sh "<path and query, e.g. /?q=hello>" <png name> <width> <height> [wait ms]
# The same approach as vnit-website/tools/shot.sh: Edge gets its own profile folder,
# may return before the PNG is written (so this waits), and can't go below about
# 500 px wide, so phone widths load the page in tools/phone_frame.html.
cd "$(dirname "$0")/.." || exit 1
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
PROFILE="$(cygpath -w "${TEMP:-/tmp}")\vnit-chatbot-v2-edge-profile"
BASE="${BASE:-http://127.0.0.1:8020}"
OUT="checks/$2"
PAGE="$BASE$1"
WIN="$3"
if [ "$3" -lt 600 ]; then
  ENC=$(~/anaconda3/python.exe -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=''))" "$PAGE")
  PAGE="file:///$(cygpath -m "$PWD/tools/phone_frame.html")?w=$3&h=$4&src=$ENC"
  WIN=600
fi
mkdir -p checks
rm -f "$OUT"
timeout 180 "$EDGE" --headless=new --disable-gpu --no-first-run --hide-scrollbars --user-data-dir="$PROFILE" \
  --virtual-time-budget="${5:-4000}" --window-size="$WIN,$4" --screenshot="$(cygpath -w "$PWD/$OUT")" "$PAGE" >/dev/null 2>&1
for _ in $(seq 1 90); do
  if [ -s "$OUT" ]; then
    [ "$WIN" != "$3" ] && ~/anaconda3/python.exe -c "import sys; from PIL import Image; im=Image.open(sys.argv[1]); im.crop((0,0,int(sys.argv[2]),im.height)).save(sys.argv[1])" "$OUT" "$3"
    echo "saved $OUT"; exit 0
  fi
  sleep 1
done
echo "no screenshot for $1"; exit 1
