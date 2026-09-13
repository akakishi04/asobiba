# FOLD Addendum — C90 / C91

Date: 2026-09-14

C90 accepted `hidden_width=4` as the smallest router capacity passing all routing-quality and compute gates on fresh seeds. It uses 2676 persistent bytes versus 14100 for default hidden32 (`0.1897872340x`). Hidden2 failed quality; hidden4/8/16/32 all passed.

C91 is the final large-width router candidate gate. It tests hidden4 at widths 3072 and 5120 with fresh seeds 20261141..43.

Predeclared requirements for every point: action accuracy >=0.995; five-class recall >=0.99; output allclose; learned/fixed device and wall median <=0.80; router/core persistent ratio <=0.01; router incremental device-free VRAM cost <=0.05 GiB.

If C91 passes, judge cumulative C84-C91 evidence for scoped Gate D passage. Gate D remains NOT PASSED until C91 is judged.
