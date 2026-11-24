#!/bin/sh
# Boot -> first dialogue of chapter 1 (new game), screenshots in work/ui/shots/<prefix>*.png
P=${1:-nav}
cd "$(dirname "$0")/.."
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  timeout 20 python tools/gdbdbg.py run "wait 30" >/dev/null 2>&1 && break
  timeout 10 python tools/gdbreset.py >/dev/null 2>&1
done
timeout 600 python tools/gdbdbg.py run "press start; wait 200; press start; wait 120; press circle; wait 300; press up; wait 5; press circle; wait 600; press start; wait 400; press circle; wait 200; press circle; wait 200; press circle; wait 150; shot work/ui/shots/${P}1.png"
