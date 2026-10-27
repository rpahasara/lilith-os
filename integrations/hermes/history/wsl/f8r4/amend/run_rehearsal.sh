#!/usr/bin/env bash
# MIRROR ONLY: normalize line endings, syntax-check, run the amended rehearsal, print the result table.
set -u
[[ $(hostname) != lilith-dev-01 ]] || exit 1
cd /root/f8r4/amend
sed -i 's/\r$//' ./*.sh ./*.py
bash -n rehearse.sh && python3 -m py_compile continuity_evidence.py test_continuity.py smoke_resume.py turn1_evidence.py && rm -rf __pycache__ || exit 1
bash rehearse.sh > rehearse.log 2>&1; echo "rc=$?"
cut -c1-330 rehearsal.tsv
tail -1 rehearse.log
