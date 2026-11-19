#!/bin/bash
# Takes the screenshots into checks/: pages of the full site at laptop (1366x900) and phone (390x844) size.
cd "$(dirname "$0")/.." || exit 1
for size in "desktop 1366 900" "mobile 390 844"; do
  set -- $size
  bash tools/shot.sh index.html "home-$1.png" "$2" "$3"
  bash tools/shot.sh engineering/cse/index.html "department-$1.png" "$2" "$3"
  bash tools/shot.sh engineering/cse/faculty/index.html "faculty-$1.png" "$2" "$3"
  bash tools/shot.sh section/academics/fees/index.html "fees-$1.png" "$2" "$3"
  bash tools/shot.sh administration/index.html "menu-heading-$1.png" "$2" "$3"
  bash tools/shot.sh news-archive/index.html "news-$1.png" "$2" "$3"
  bash tools/shot.sh notices/index.html "notices-$1.png" "$2" "$3"
  bash tools/shot.sh "index.html?assistant=open" "home-assistant-$1.png" "$2" "$3"
done
