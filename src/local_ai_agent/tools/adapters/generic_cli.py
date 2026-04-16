from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class GenericCliToolAdapter:
    shell: Literal["powershell", "bash"]
    adapter_name: str = "generic_cli"
