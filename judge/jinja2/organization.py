from . import registry


@registry.function
def distinct_institutions(orgs):
    """Returns the distinct Institution objects among `orgs` (an iterable of Organization), in
    order of first appearance, skipping teams with no institution set. Used on user/contest
    ranking rows so a student who is in several teams of the same institution only shows that
    institution's flag/name once."""
    seen = set()
    result = []
    for org in orgs:
        inst = org.institution
        if inst is not None and inst.id not in seen:
            seen.add(inst.id)
            result.append(inst)
    return result
