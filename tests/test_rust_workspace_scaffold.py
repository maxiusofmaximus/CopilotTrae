import subprocess
import tomllib
from pathlib import Path


def test_rust_workspace_scaffold_builds_and_tests():
    root_manifest = Path("Cargo.toml")
    assert root_manifest.exists(), "missing root Cargo.toml"

    manifest = tomllib.loads(root_manifest.read_text(encoding="utf-8"))
    workspace = manifest["workspace"]
    members = set(workspace["members"])
    expected_members = {
        "crates/core-contracts",
        "crates/router-core",
        "crates/terminal-core",
        "crates/runtime-core",
        "crates/cli-app",
    }

    assert expected_members.issubset(members)

    for member in expected_members:
        crate_dir = Path(member)
        assert crate_dir.exists(), f"missing crate directory: {member}"
        assert (crate_dir / "Cargo.toml").exists(), f"missing crate manifest: {member}"

    test_result = subprocess.run(
        ["cargo", "test", "-p", "core-contracts"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert test_result.returncode == 0, test_result.stderr

    build_result = subprocess.run(
        ["cargo", "build"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert build_result.returncode == 0, build_result.stderr
