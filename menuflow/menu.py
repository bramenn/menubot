from __future__ import annotations

from typing import Dict, List, Optional

from attr import dataclass, ib

from mautrix.types import SerializableAttrs

from .nodes import HTTPRequest, Input, Message
from .utils.base_logger import BaseLogger


@dataclass
class Menu(SerializableAttrs, BaseLogger):
    id: str = ib(metadata={"json": "id"})

    nodes: List[Message, Input, HTTPRequest] = ib(metadata={"json": "nodes"}, factory=list)

    def get_node_by_id(self, node_id: str) -> Message | Input | HTTPRequest | None:
        for node in self.nodes:
            if node_id == node.id:
                return node

    def build_node(
        self, data: Dict, type_class: Message | Input | HTTPRequest | None
    ) -> Message | Input | HTTPRequest | None:
        return type_class.deserialize(data)

    def node(self, context: str) -> Message | Input | HTTPRequest | None:

        node = self.get_node_by_id(node_id=context)

        if node.type == "message":
            node = self.build_node(node.serialize(), Message)
        elif node.type == "input":
            node = self.build_node(node.serialize(), Input)
        elif node.type == "http_request":
            node = self.build_node(node.serialize(), HTTPRequest)
        else:
            return

        return node
