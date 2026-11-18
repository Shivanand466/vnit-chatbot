#!/bin/bash
# Takes the Step 7 screenshots into checks/: six pages at laptop (1366x900) and phone (390x844) size.
cd "$(dirname "$0")/.." || exit 1
for size in "desktop 1366 900" "mobile 390 844"; do
  set -- $size
  bash tools/shot.sh index.html "home-$1.png" "$2" "$3"
  bash tools/shot.sh departments/cse.html "department-$1.png" "$2" "$3"
  bash tools/shot.sh students/hostel-fees.html "hostel-fees-$1.png" "$2" "$3"
  bash tools/shot.sh notices.html "notices-$1.png" "$2" "$3"
  bash tools/shot.sh more/contact.html "contact-$1.png" "$2" "$3"
  bash tools/shot.sh "index.html?assistant=open" "home-assistant-$1.png" "$2" "$3"
done
