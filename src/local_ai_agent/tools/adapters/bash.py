from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BashToolAdapter:
    shell: str = "bash"
    adapter_name: str = "bash"
