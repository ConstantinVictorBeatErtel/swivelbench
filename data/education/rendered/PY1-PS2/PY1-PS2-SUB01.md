Submission PY1-PS2-SUB01
Profile: correct_clear

Question PY1-PS2-Q01
scratch: show step
  1. range(5) gives 0 through 4
  2. keep even i: 0, 2, 4
  3. squares => [0, 4, 16]
=> FINAL: [0, 4, 16]   (check units/interpretation)

Question PY1-PS2-Q02
scratch: show step
  1. counts = Counter(xs)
  2. for x in xs: if counts[x] == 1: return x
  3. return None; two linear passes ⇒ O(n) time, O(n) space
=> FINAL: scan counts, then scan in order; return first count==1 else None; O(n) time, O(n) space   (check units/interpretation)

Question PY1-PS2-Q03
scratch: show step
  1. A single pass fixes only adjacent inversions encountered once.
  2. Repeat until no swaps (or n−1 passes), shrinking the suffix after each pass.
=> FINAL: repeat passes or track the shrinking unsorted suffix; one pass alone is not a full sort   (check units/interpretation)

Question PY1-PS2-Q04
scratch: show step
  1. linear scan: up to 128 comparisons, Θ(n)
  2. binary search: at most ⌈log₂(128)⌉+1 comparisons, Θ(log n)
=> FINAL: linear Θ(n), up to 128; binary Θ(log n), about 8   (check units/interpretation)

Question PY1-PS2-Q05
scratch: show step
  1. Removing shifts later elements left while the iterator advances.
  2. Build a filtered list or iterate over a copy, then replace the original.
=> FINAL: mutation shifts elements and skips checks; use a filtered copy or iterate over a copy   (check units/interpretation)

Question PY1-PS2-Q06
scratch: show step
  1. range(7) gives 0 through 6
  2. keep even i: 0, 2, 4, 6
  3. squares => [0, 4, 16, 36]
=> FINAL: [0, 4, 16, 36]   (check units/interpretation)

Question PY1-PS2-Q07
scratch: show step
  1. counts = Counter(xs)
  2. for x in xs: if counts[x] == 1: return x
  3. return None; two linear passes ⇒ O(n) time, O(n) space
=> FINAL: scan counts, then scan in order; return first count==1 else None; O(n) time, O(n) space   (check units/interpretation)

Question PY1-PS2-Q08
scratch: show step
  1. A single pass fixes only adjacent inversions encountered once.
  2. Repeat until no swaps (or n−1 passes), shrinking the suffix after each pass.
=> FINAL: repeat passes or track the shrinking unsorted suffix; one pass alone is not a full sort   (check units/interpretation)
