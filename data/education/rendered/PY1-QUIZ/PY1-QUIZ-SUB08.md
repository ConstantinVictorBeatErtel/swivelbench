Submission PY1-QUIZ-SUB08
Profile: ambiguous_scan

Question PY1-QUIZ-Q01
scan faint / margin cut off
visible work:
range(5) gives 0 through 4... ?
last line is hard to read; maybe [0, 4, 16]

Question PY1-QUIZ-Q02
scan faint / margin cut off
visible work:
counts = Counter(xs)... ?
last line is hard to read; maybe scan counts, then scan in order; return first count==1 else None; O(n) time, O(n) space

Question PY1-QUIZ-Q03
scan faint / margin cut off
visible work:
A single pass fixes only adjacent inversions encountered once.... ?
last line is hard to read; maybe repeat passes or track the shrinking unsorted suffix; one pass alone is not a full sort

Question PY1-QUIZ-Q04
scan faint / margin cut off
visible work:
linear scan: up to 128 comparisons, Θ(n)... ?
last line is hard to read; maybe linear Θ(n), up to 128; binary Θ(log n), about 8

Question PY1-QUIZ-Q05
scan faint / margin cut off
visible work:
Removing shifts later elements left while the iterator advances.... ?
last line is hard to read; maybe mutation shifts elements and skips checks; use a filtered copy or iterate over a copy
