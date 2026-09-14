# C123-C124 addendum

## C123 ACCEPTED PASS

Fresh seeds `20261431..33`; 1,922 scenarios per seed. All deciding rates were `1.0`. Changed request epoch or provider generation produced zero commit, retry, and fallback. C37/fixture preserved; tracked tree clean.

## C124 ACTIVE

Experiment: `C124-v5e-receipt-replay-falsification`.

Fresh seeds `20261441..43`. Per seed: 480 first-delivery cases, 960 repeated-delivery cases, 2 none controls; 1,442 total.

One identical receipt is delivered 1, 2, or 3 times. The first delivery may claim it once; later duplicates must add no commit, retry, or fallback. APPLIED totals one commit; NOT_APPLIED totals one retry and one commit; STILL_UNKNOWN totals zero for all three. C123 remains a control gate.

Sequential delivery only. Concurrent atomic claims and crash durability remain out of scope. Gate E remains NOT PASSED.
