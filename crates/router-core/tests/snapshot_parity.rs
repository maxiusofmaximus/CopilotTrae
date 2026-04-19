use std::collections::BTreeSet;

use router_core::{
    JsonValue, ModuleRegistry, RegistrySnapshot, ToolRegistry, build_registry_snapshot,
    typed_empty_extensions,
};

#[test]
fn registry_snapshot_deserializes_from_python_fixture() {
    let raw = include_str!("../../../tests/contracts/router/snapshot_minimal.json");
    let parsed = RegistrySnapshot::from_json_str(raw).unwrap();

    assert_eq!(parsed.snapshot_version, "snap-fixture-1234");
    assert_eq!(parsed.built_for_session, "sess-fixture");
    assert!(parsed.tools.is_empty());
    assert!(parsed.modules.is_empty());
    assert_eq!(
        parsed.execution_surface.get("tools"),
        Some(&JsonValue::Array(vec![]))
    );
    assert_eq!(
        parsed.capability_surface.get("capabilities"),
        Some(&JsonValue::Array(vec![]))
    );
    assert_eq!(
        parsed.extensions.get("mcp_servers"),
        Some(&JsonValue::Array(vec![]))
    );
}

#[test]
fn typed_empty_extensions_returns_exact_required_keys() {
    let extensions = typed_empty_extensions();
    let keys = extensions.keys().cloned().collect::<BTreeSet<_>>();

    assert_eq!(
        keys,
        BTreeSet::from([
            "aliases".to_string(),
            "health_checks".to_string(),
            "mcp_servers".to_string(),
            "policies".to_string(),
            "provider_status".to_string(),
        ])
    );
    assert_eq!(
        extensions.get("aliases"),
        Some(&JsonValue::Object(Default::default()))
    );
    assert_eq!(extensions.get("mcp_servers"), Some(&JsonValue::Array(vec![])));
}

#[test]
fn build_registry_snapshot_generates_stable_session_version() {
    let tool_registry = ToolRegistry::default();
    let module_registry = ModuleRegistry::default();

    let snapshot_a = build_registry_snapshot("sess-1", &tool_registry, &module_registry);
    let snapshot_b = build_registry_snapshot("sess-1", &tool_registry, &module_registry);
    let snapshot_other_session = build_registry_snapshot("sess-2", &tool_registry, &module_registry);

    assert_eq!(snapshot_a.snapshot_version, snapshot_b.snapshot_version);
    assert_ne!(snapshot_a.snapshot_version, "generated");
    assert_ne!(snapshot_a.snapshot_version, snapshot_other_session.snapshot_version);
    assert_eq!(
        snapshot_a.source_versions.get("tool_registry"),
        Some(&JsonValue::String("1".to_string()))
    );
    assert_eq!(
        snapshot_a.source_versions.get("module_registry"),
        Some(&JsonValue::String("1".to_string()))
    );
}
