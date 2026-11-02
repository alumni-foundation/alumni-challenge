def escape_like(value: str) -> str:
    """Make `%`, `_` and `\\` in a search term match themselves inside an ILIKE pattern
    (use with `escape="\\\\"`)."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
