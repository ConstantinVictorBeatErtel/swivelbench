Submission PY1-QUIZ-SUB06
Profile: notation_error

Question PY1-QUIZ-Q01
notation changes halfway:
  1. range(5) gives 0 through 4
  2. keep even i: 0, 2, 4
  3. squares  ≈ > [0, 4, 16]
marks, subscripts, and units are mixed up
result written as: [0, 4, 16] (please interpret)

Question PY1-QUIZ-Q02
notation changes halfway:
  1. counts  ≈  Counter(xs)
  2. for x in xs: if counts[x]  ≈  ≈  1: return x
  3. return None; two linear passes ⇒ O(n) time, O(n) space
marks, subscripts, and units are mixed up
result written as: scan counts, then scan in order; return first count==1 else None; O(n) time, O(n) space (please interpret)

Question PY1-QUIZ-Q03
notation changes halfway:
  1. A single pass fixes only adjacent inversions encountered once.
  2. Repeat until no swaps (or n−1 passes), shrinking the suffix after each pass.
marks, subscripts, and units are mixed up
result written as: repeat passes or track the shrinking unsorted suffix; one pass alone is not a full sort (please interpret)

Question PY1-QUIZ-Q04
notation changes halfway:
  1. linear scan: up to 128 comparisons, Θ(n)
  2. binary search: at most ⌈log₂(128)⌉+1 comparisons, Θ(log n)
marks, subscripts, and units are mixed up
result written as: linear Θ(n), up to 128; binary Θ(log n), about 8 (please interpret)

Question PY1-QUIZ-Q05
notation changes halfway:
  1. Removing shifts later elements left while the iterator advances.
  2. Build a filtered list or iterate over a copy, then replace the original.
marks, subscripts, and units are mixed up
result written as: mutation shifts elements and skips checks; use a filtered copy or iterate over a copy (please interpret)
