from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PowerShellToolAdapter:
    shell: str = "powershell"
    adapter_name: str = "powershell"
