"""In-memory taxonomy service."""

from __future__ import annotations

from dataclasses import replace

from data_fabric.semantic.exceptions import SemanticValidationError
from data_fabric.semantic.interfaces import TaxonomyService
from data_fabric.semantic.models import TaxonomyNode, TaxonomyPath, normalize_term

PartitionKey = tuple[str, str | None]


class InMemoryTaxonomyService(TaxonomyService):
    def __init__(self) -> None:
        self._taxonomies: dict[PartitionKey, set[str]] = {}
        self._nodes: dict[PartitionKey, dict[str, TaxonomyNode]] = {}

    def create_taxonomy(self, taxonomy_id: str, *, organization_id: str, tenant_id: str | None) -> str:
        self._taxonomies.setdefault((organization_id, tenant_id), set()).add(taxonomy_id)
        return taxonomy_id

    def add_node(self, node: TaxonomyNode) -> TaxonomyNode:
        key = (node.organization_id, node.tenant_id)
        if node.taxonomy_id not in self._taxonomies.get(key, set()):
            self.create_taxonomy(node.taxonomy_id, organization_id=node.organization_id, tenant_id=node.tenant_id)
        if node.parent_node_id and node.parent_node_id not in self._nodes.get(key, {}):
            raise SemanticValidationError("parent taxonomy node must exist")
        nodes = self._nodes.setdefault(key, {})
        nodes[node.node_id] = node
        if self.detect_cycles(node.taxonomy_id, organization_id=node.organization_id, tenant_id=node.tenant_id):
            nodes.pop(node.node_id, None)
            raise SemanticValidationError("taxonomy cycle detected")
        return node

    def get_node(self, node_id: str, *, organization_id: str, tenant_id: str | None) -> TaxonomyNode | None:
        return self._nodes.get((organization_id, tenant_id), {}).get(node_id)

    def move_node(self, node_id: str, new_parent_node_id: str | None, *, organization_id: str, tenant_id: str | None) -> TaxonomyNode:
        key = (organization_id, tenant_id)
        node = self._nodes.get(key, {}).get(node_id)
        if node is None:
            raise SemanticValidationError("taxonomy node not found")
        if new_parent_node_id and new_parent_node_id not in self._nodes.get(key, {}):
            raise SemanticValidationError("parent taxonomy node must exist")
        updated = replace(node, parent_node_id=new_parent_node_id)
        old = node
        self._nodes[key][node_id] = updated
        if self.detect_cycles(updated.taxonomy_id, organization_id=organization_id, tenant_id=tenant_id):
            self._nodes[key][node_id] = old
            raise SemanticValidationError("taxonomy cycle detected")
        return updated

    def remove_node(self, node_id: str, *, organization_id: str, tenant_id: str | None) -> None:
        self._nodes.get((organization_id, tenant_id), {}).pop(node_id, None)

    def list_roots(self, taxonomy_id: str, *, organization_id: str, tenant_id: str | None) -> list[TaxonomyNode]:
        return sorted([node for node in self._nodes.get((organization_id, tenant_id), {}).values() if node.taxonomy_id == taxonomy_id and node.parent_node_id is None], key=lambda item: (item.display_order, item.node_id))

    def list_children(self, node_id: str, *, organization_id: str, tenant_id: str | None) -> list[TaxonomyNode]:
        return sorted([node for node in self._nodes.get((organization_id, tenant_id), {}).values() if node.parent_node_id == node_id], key=lambda item: (item.display_order, item.node_id))

    def get_path(self, node_id: str, *, organization_id: str, tenant_id: str | None) -> TaxonomyPath:
        nodes = self._nodes.get((organization_id, tenant_id), {})
        current = nodes.get(node_id)
        if current is None:
            raise SemanticValidationError("taxonomy node not found")
        path: list[TaxonomyNode] = []
        seen: set[str] = set()
        while current:
            if current.node_id in seen:
                raise SemanticValidationError("taxonomy cycle detected")
            seen.add(current.node_id)
            path.append(current)
            current = nodes.get(current.parent_node_id) if current.parent_node_id else None
        ordered = tuple(reversed(path))
        return TaxonomyPath(ordered[-1].taxonomy_id, tuple(node.node_id for node in ordered), tuple(node.concept_id for node in ordered))

    def search_taxonomy(self, taxonomy_id: str, term: str, *, organization_id: str, tenant_id: str | None) -> list[TaxonomyNode]:
        normalized = normalize_term(term)
        return sorted([node for node in self._nodes.get((organization_id, tenant_id), {}).values() if node.taxonomy_id == taxonomy_id and normalized in normalize_term(node.concept_id)], key=lambda item: item.node_id)

    def detect_cycles(self, taxonomy_id: str, *, organization_id: str, tenant_id: str | None) -> list[tuple[str, str]]:
        nodes = {node_id: node for node_id, node in self._nodes.get((organization_id, tenant_id), {}).items() if node.taxonomy_id == taxonomy_id}
        cycles: list[tuple[str, str]] = []
        for node in nodes.values():
            seen: set[str] = set()
            current = node
            while current.parent_node_id:
                if current.parent_node_id in seen or current.parent_node_id == node.node_id:
                    cycles.append((node.node_id, current.parent_node_id))
                    break
                seen.add(current.parent_node_id)
                parent = nodes.get(current.parent_node_id)
                if parent is None:
                    break
                current = parent
        return sorted(set(cycles))
