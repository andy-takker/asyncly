from yarl import URL


def default_route_resolver(url: URL) -> str:
    parts: list[str] = []
    for p in url.path.split("/"):
        if not p:
            continue
        if p.isdigit() or (len(p) in (8, 16, 32, 36) and any(ch.isalpha() for ch in p)):
            parts.append(":id")
        else:
            parts.append(p)
    return "/" + "/".join(parts) if parts else "/"
