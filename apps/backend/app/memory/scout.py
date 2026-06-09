from app.memory.manifest import ManifestEntry, MemoryManifest


def score_manifest_entries(query: str, manifest: MemoryManifest, limit: int) -> list[ManifestEntry]:
    """Cheap keyword scorer for the first NBAM retrieval phase."""

    terms = {term.lower() for term in query.split() if term.strip()}
    scored: list[tuple[int, ManifestEntry]] = []
    for entry in manifest.active_entries():
        haystack = " ".join(
            [entry.title, entry.type, entry.summary, *entry.tags, *entry.aliases]
        ).lower()
        score = sum(1 for term in terms if term in haystack)
        if score:
            scored.append((score, entry))

    return [entry for _, entry in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]]
