from pathlib import Path


class NodeStore:
    """File-backed durable memory node store."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.nodes_dir = root / "nodes"

    def initialize(self) -> None:
        self.nodes_dir.mkdir(parents=True, exist_ok=True)

    def node_path(self, node_id: str) -> Path:
        return self.nodes_dir / f"{node_id}.md"

    def write_node(self, node_id: str, content: str) -> Path:
        self.initialize()
        path = self.node_path(node_id)
        path.write_text(content, encoding="utf-8")
        return path

    def read_node(self, node_id: str) -> str:
        return self.node_path(node_id).read_text(encoding="utf-8")

    def list_node_ids(self) -> list[str]:
        self.initialize()
        return sorted(path.stem for path in self.nodes_dir.glob("*.md"))
