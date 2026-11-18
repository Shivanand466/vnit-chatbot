#!/bin/bash
# Screenshot one built page with headless Edge: tools/shot.sh <page in dist> <png name> <width> <height>
# Edge needs its own profile folder, or it hands the job to an Edge window that is
# already open; it can return before the PNG is written, so this waits for it; and it
# can't go below about 500 px wide, so phone widths use tools/phone_frame.html.
cd "$(dirname "$0")/.." || exit 1
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
PROFILE="$(cygpath -w "${TEMP:-/tmp}")\vnit-website-edge-profile"
OUT="checks/$2"
PAGE="file:///$(cygpath -m "$PWD/dist/$1")"
WIN="$3"
if [ "$3" -lt 600 ]; then
  PAGE="file:///$(cygpath -m "$PWD/tools/phone_frame.html")?w=$3&h=$4&src=$(echo "$PAGE" | sed 's/?/%3F/; s/&/%26/g')"
  WIN=600
fi
mkdir -p checks
rm -f "$OUT"
timeout 90 "$EDGE" --headless=new --disable-gpu --no-first-run --hide-scrollbars --user-data-dir="$PROFILE" \
  --virtual-time-budget=4000 --window-size="$WIN,$4" --screenshot="$(cygpath -w "$PWD/$OUT")" "$PAGE" >/dev/null 2>&1
for _ in $(seq 1 60); do
  if [ -s "$OUT" ]; then
    [ "$WIN" != "$3" ] && ~/anaconda3/python.exe -c "import sys; from PIL import Image; im=Image.open(sys.argv[1]); im.crop((0,0,int(sys.argv[2]),im.height)).save(sys.argv[1])" "$OUT" "$3"
    echo "saved $OUT"; exit 0
  fi
  sleep 1
done
echo "no screenshot for $1"; exit 1
