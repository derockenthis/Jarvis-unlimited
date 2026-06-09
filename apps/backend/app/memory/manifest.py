from pydantic import BaseModel, Field


class ManifestEntry(BaseModel):
    id: str
    title: str
    type: str
    status: str
    tags: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    updated_at: str
    summary: str = ""
    outgoing_links: list[dict[str, str]] = Field(default_factory=list)


class MemoryManifest(BaseModel):
    entries: list[ManifestEntry] = Field(default_factory=list)

    def active_entries(self) -> list[ManifestEntry]:
        return [entry for entry in self.entries if entry.status == "active"]
