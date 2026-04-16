from __future__ import annotations

from pydantic import BaseModel, Field


class ConfidencePolicy(BaseModel):
    global_auto_accept: float = 0.90
    by_intent: dict[str, float] = Field(
        default_factory=lambda: {
            "execution": 0.93,
            "command_fix": 0.90,
            "correction": 0.90,
            "installation": 0.85,
        }
    )

    @classmethod
    def defaults(cls) -> "ConfidencePolicy":
        return cls()

    def for_intent(self, intent: str) -> float:
        return self.by_intent.get(intent, self.global_auto_accept)


class PolicyMaterialization(BaseModel):
    trust_policy: dict[str, str] = Field(default_factory=lambda: {"mode": "strict"})

    @classmethod
    def empty(cls) -> "PolicyMaterialization":
        return cls()
