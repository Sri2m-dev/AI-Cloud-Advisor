from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from core.digital_twin.twin_graph import TwinGraph
from core.digital_twin.twin_state import TwinState
from core.entities.entity import utc_now_iso


@dataclass(slots=True)
class TwinSnapshot:
    twin_id: UUID
    state: TwinState
    graph: TwinGraph
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""
    twin_version: str = "1.0.0"
    state_version: str = "1.0.0"
    graph_version: str = "1.0.0"
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["twin_id"] = str(self.twin_id)
        payload["state"] = self.state.to_dict()
        payload["graph"] = self.graph.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TwinSnapshot":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["twin_id"] = UUID(str(data["twin_id"]))
        data["state"] = TwinState.from_dict(data["state"])
        graph_payload = data["graph"]
        data["graph"] = graph_payload if isinstance(graph_payload, TwinGraph) else graph_payload
        if isinstance(data["graph"], dict):
            raise ValueError("TwinSnapshot.from_dict requires graph reconstruction by TwinModel.")
        return cls(**data)
