def change_signature(changed_fields):
    parts = []
    for key in sorted(changed_fields):
        change = changed_fields[key]
        parts.append(f"{key}:{change['from']}->{change['to']}")
    return "|".join(parts)
