#!/usr/bin/env bash
# A2 (owner-approved): run the staged, hash-verified g7r.sh = requests #2-#4 with the position-based hold on #2, then G-7d.
set -u
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
bash /var/tmp/f8/amend/g7r.sh /var/tmp/f8/amend 0d00769ac01a
