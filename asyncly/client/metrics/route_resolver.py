from yarl import URL


def default_route_resolver(url: URL) -> str:
    """Normalize a URL path into a low-cardinality route label.

    Numeric and UUID-like path segments are replaced with ``:id`` so that, for
    example, ``/cats/42`` and ``/cats/7`` both map to ``/cats/:id``. Used as the
    default route label for client metrics.
    """
    parts: list[str] = []
    for p in url.path.split("/"):
        if not p:
            continue
        if p.isdigit() or (len(p) in (8, 16, 32, 36) and any(ch.isalpha() for ch in p)):
            parts.append(":id")
        else:
            parts.append(p)
    return "/" + "/".join(parts) if parts else "/"
