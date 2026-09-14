from __future__ import annotations


def rate(rows, predicate):
    selected=[row for row in rows if predicate(row)]
    if not selected:
        raise RuntimeError("empty C123 metric selection")
    return sum(bool(row["passed"]) for row in selected)/len(selected)


def hidden_invariant(rows):
    groups={}
    for row in rows:
        key=(tuple(row["visible"]),tuple(row["actual"]),row["case"],row["outcome"])
        groups.setdefault(key,[]).append(row["trace"])
    return float(all(len(items)==2 and items[0]==items[1] for items in groups.values()))
