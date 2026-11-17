"""Operações sobre intervalos fechados [início, fim]."""


def merge(intervals):
    """Une intervalos que se sobrepõem ou se tocam; devolve a lista ordenada."""
    merged = []
    for start, end in sorted(intervals):
        if merged and start < merged[-1][1]:
            merged[-1][1] = end
        else:
            merged.append([start, end])
    return merged


def total_length(intervals):
    return sum(end - start for start, end in merge(intervals))
