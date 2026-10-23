from collections.abc import Iterable


def parse_display_names(raw: str | None) -> dict[str, str]:
    if raw is None:
        return {}
    names: dict[str, str] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        label, sep, name = item.partition("=")
        label, name = label.strip(), name.strip()
        if not sep or not label or not name:
            raise ValueError(f"Invalid speaker mapping: {item!r}（格式應為 SPEAKER_XX=名稱）")
        names[label] = name
    return names


def display_name(label: str, names: dict[str, str]) -> str:
    return names.get(label, label)


def unknown_labels(names: dict[str, str], labels_found: Iterable[str]) -> list[str]:
    return sorted(set(names) - set(labels_found))
