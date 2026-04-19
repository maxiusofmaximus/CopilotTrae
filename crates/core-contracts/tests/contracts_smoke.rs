use core_contracts::CONTRACTS_VERSION;

#[test]
fn workspace_smoke_builds() {
    assert_eq!(CONTRACTS_VERSION, "0.1.0");
}
