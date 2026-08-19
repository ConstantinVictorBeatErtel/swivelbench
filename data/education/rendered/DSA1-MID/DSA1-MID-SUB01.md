Submission DSA1-MID-SUB01
Profile: correct_clear

Question DSA1-MID-Q01
scratch: show step
  1. 7>4, go right; 7<9, go left; 7>6, go right.
  2. Comparison path: 4→9→6; parent of 7 is 6.
=> FINAL: path 4→9→6; parent=6   (check units/interpretation)

Question DSA1-MID-Q02
scratch: show step
  1. Maintain a hash set of values seen so far.
  2. Before inserting x, if x∈seen return True; otherwise insert x.
  3. Expected O(n) time and O(n) auxiliary space; invariant: seen contains exactly the prior prefix.
=> FINAL: hash set membership scan; expected O(n) time, O(n) space; prefix invariant   (check units/interpretation)

Question DSA1-MID-Q03
scratch: show step
  1. A balanced tree can be built recursively by choosing the median, with each key visited once: Θ(n).
  2. Height is Θ(log n), so search is Θ(log n).
=> FINAL: build Θ(n) with median recursion; search Θ(log n) in balanced tree   (check units/interpretation)

Question DSA1-MID-Q04
scratch: show step
  1. Queue A; discover B,C; then dequeue B and discover D; dequeue C and discover E.
  2. Order A,B,C,D,E; layer order equals shortest edge distance.
=> FINAL: A,B,C,D,E; BFS explores by distance layers and yields fewest edges   (check units/interpretation)

Question DSA1-MID-Q05
scratch: show step
  1. Invariant: the prefix before index i is sorted and contains the original prefix values.
  2. Initialization: one-element prefix is sorted; maintenance inserts the next item; termination covers the full array.
=> FINAL: sorted prefix invariant; initialization, insertion maintenance, termination imply correctness   (check units/interpretation)

Question DSA1-MID-Q06
scratch: show step
  1. 7>4, go right; 7<9, go left; 7>6, go right.
  2. Comparison path: 4→9→6; parent of 7 is 6.
=> FINAL: path 4→9→6; parent=6   (check units/interpretation)

Question DSA1-MID-Q07
scratch: show step
  1. Maintain a hash set of values seen so far.
  2. Before inserting x, if x∈seen return True; otherwise insert x.
  3. Expected O(n) time and O(n) auxiliary space; invariant: seen contains exactly the prior prefix.
=> FINAL: hash set membership scan; expected O(n) time, O(n) space; prefix invariant   (check units/interpretation)

Question DSA1-MID-Q08
scratch: show step
  1. A balanced tree can be built recursively by choosing the median, with each key visited once: Θ(n).
  2. Height is Θ(log n), so search is Θ(log n).
=> FINAL: build Θ(n) with median recursion; search Θ(log n) in balanced tree   (check units/interpretation)
