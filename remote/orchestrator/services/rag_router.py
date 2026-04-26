from dataclasses import dataclass

from services.mode_policy import ModePolicy, get_mode_policy


@dataclass(frozen=True)
class RagRoute:
    namespace: str
    source: str = "mode_policy_stub"


class RagRouter:
    def route_for_mode(self, mode: str | ModePolicy) -> RagRoute:
        policy = mode if isinstance(mode, ModePolicy) else get_mode_policy(mode)
        return RagRoute(namespace=policy.rag_namespace)


rag_router = RagRouter()

__all__ = ["RagRoute", "RagRouter", "rag_router"]
