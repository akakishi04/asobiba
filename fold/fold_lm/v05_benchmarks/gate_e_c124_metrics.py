from __future__ import annotations


def hidden_invariant(rows):
    groups = {}
    for row in rows:
        key = (tuple(row["visible"]), tuple(row["actual"]), row["outcome"], row["count"])
        groups.setdefault(key, []).append(row["trace"])
    return float(all(len(v) == 2 and v[0] == v[1] for v in groups.values()))
