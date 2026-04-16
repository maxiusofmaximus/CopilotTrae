from __future__ import annotations


def normalize_input(raw_input: str) -> str:
    return " ".join(raw_input.strip().split())


def parse_command_shape(normalized_input: str) -> tuple[str, list[str]]:
    parts = normalized_input.split()
    if not parts:
        return "", []
    return parts[0], parts[1:]
