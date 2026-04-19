from pathlib import Path


def test_contract_fixture_directories_exist():
    assert Path("tests/contracts/router").exists()
    assert Path("tests/contracts/terminal").exists()
    assert Path("tests/contracts/runtime").exists()
