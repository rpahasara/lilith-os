cd /root/f8r4
for r in run4/results.tsv results.tsv; do
  echo "== $r $(wc -l < "$r") rows"; cut -f2 "$r" | sort | uniq -c
  grep -v -P '\t(PASS|CLEAN|SUCCESS)(\t|$)' "$r" | head
done
cmp run4/results.tsv results.tsv >/dev/null && echo same || diff <(cut -f1,2 run4/results.tsv) <(cut -f1,2 results.tsv) | head

