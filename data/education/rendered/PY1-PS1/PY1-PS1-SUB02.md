Submission PY1-PS1-SUB02
Profile: arithmetic_error

Question PY1-PS1-Q01
work / setup:
  1. range(5) gives 0 through 4
  2. keep even i: 0, 2, 4
 crossed-out arithmetic: [smudged]
FINAL (maybe): [0, 4, 16] plus 1

Question PY1-PS1-Q02
work / setup:
  1. counts = Counter(xs)
  2. for x in xs: if counts[x] == 1: return x
 crossed-out arithmetic: [smudged]
FINAL (maybe): scan counts, then scan in order; return first count==1 else None; O(n) time, O(n) space plus 1

Question PY1-PS1-Q03
work / setup:
  1. A single pass fixes only adjacent inversions encountered once.
 crossed-out arithmetic: [smudged]
FINAL (maybe): repeat passes or track the shrinking unsorted suffix; one pass alone is not a full sort plus 1

Question PY1-PS1-Q04
work / setup:
  1. linear scan: up to 64 comparisons, Θ(n)
 crossed-out arithmetic: [smudged]
FINAL (maybe): linear Θ(n), up to 64; binary Θ(log n), about 7 plus 1

Question PY1-PS1-Q05
work / setup:
  1. Removing shifts later elements left while the iterator advances.
 crossed-out arithmetic: [smudged]
FINAL (maybe): mutation shifts elements and skips checks; use a filtered copy or iterate over a copy plus 1

Question PY1-PS1-Q06
work / setup:
  1. range(5) gives 0 through 4
  2. keep even i: 0, 2, 4
 crossed-out arithmetic: [smudged]
FINAL (maybe): [0, 4, 16] plus 1
