use std::collections::BTreeSet;

use crate::json::{JsonObject, JsonValue};
use crate::snapshot::RegistrySnapshot;

#[derive(Debug, Clone, PartialEq)]
pub struct ToolRegistry {
    pub version: String,
    tools: Vec<JsonObject>,
}

impl Default for ToolRegistry {
    fn default() -> Self {
        Self {
            version: "1".to_string(),
            tools: Vec::new(),
        }
    }
}

impl ToolRegistry {
    pub fn snapshot_tools(&self) -> Vec<JsonObject> {
        self.tools
            .iter()
            .filter(|tool| matches!(tool.get("available"), Some(JsonValue::Bool(true))) || !tool.contains_key("available"))
            .cloned()
            .collect()
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct ModuleRegistry {
    pub version: String,
    modules: Vec<JsonObject>,
}

impl Default for ModuleRegistry {
    fn default() -> Self {
        Self {
            version: "1".to_string(),
            modules: Vec::new(),
        }
    }
}

impl ModuleRegistry {
    pub fn snapshot_modules(&self) -> Vec<JsonObject> {
        self.modules
            .iter()
            .filter(|module| matches!(module.get("enabled"), Some(JsonValue::Bool(true))) || !module.contains_key("enabled"))
            .cloned()
            .collect()
    }

    pub fn snapshot_capabilities(&self) -> JsonObject {
        let capabilities = self
            .snapshot_modules()
            .into_iter()
            .filter_map(|module| module.get("capabilities").cloned())
            .flat_map(|value| match value {
                JsonValue::Array(items) => items,
                _ => Vec::new(),
            })
            .filter_map(|value| match value {
                JsonValue::String(item) => Some(item),
                _ => None,
            })
            .collect::<BTreeSet<_>>()
            .into_iter()
            .map(JsonValue::String)
            .collect::<Vec<_>>();

        JsonObject::from([("capabilities".to_string(), JsonValue::Array(capabilities))])
    }
}

pub fn typed_empty_extensions() -> JsonObject {
    JsonObject::from([
        ("aliases".to_string(), JsonValue::Object(JsonObject::new())),
        ("policies".to_string(), JsonValue::Object(JsonObject::new())),
        ("mcp_servers".to_string(), JsonValue::Array(Vec::new())),
        ("provider_status".to_string(), JsonValue::Object(JsonObject::new())),
        ("health_checks".to_string(), JsonValue::Array(Vec::new())),
    ])
}

pub fn build_registry_snapshot(
    session_id: &str,
    tool_registry: &ToolRegistry,
    module_registry: &ModuleRegistry,
) -> RegistrySnapshot {
    let tools = tool_registry.snapshot_tools();
    let modules = module_registry.snapshot_modules();

    RegistrySnapshot {
        snapshot_version: stable_snapshot_version(session_id, tool_registry, module_registry, &tools, &modules),
        built_for_session: session_id.to_string(),
        built_at: String::new(),
        tools: tools.clone(),
        modules: modules.clone(),
        policies: JsonObject::new(),
        source_versions: JsonObject::from([
            (
                "tool_registry".to_string(),
                JsonValue::String(tool_registry.version.clone()),
            ),
            (
                "module_registry".to_string(),
                JsonValue::String(module_registry.version.clone()),
            ),
        ]),
        execution_surface: JsonObject::from([(
            "tools".to_string(),
            JsonValue::Array(tools.into_iter().map(JsonValue::Object).collect()),
        )]),
        capability_surface: module_registry.snapshot_capabilities(),
        extensions: typed_empty_extensions(),
    }
}

fn stable_snapshot_version(
    session_id: &str,
    tool_registry: &ToolRegistry,
    module_registry: &ModuleRegistry,
    tools: &[JsonObject],
    modules: &[JsonObject],
) -> String {
    let mut hasher = Fnv1a64::default();

    hash_str(&mut hasher, session_id);
    hash_str(&mut hasher, &tool_registry.version);
    hash_str(&mut hasher, &module_registry.version);

    for tool in tools {
        hash_json_value(&mut hasher, &JsonValue::Object(tool.clone()));
    }

    for module in modules {
        hash_json_value(&mut hasher, &JsonValue::Object(module.clone()));
    }

    format!("snap-{:016x}", hasher.finish())
}

fn hash_json_value(hasher: &mut Fnv1a64, value: &JsonValue) {
    match value {
        JsonValue::Null => hash_str(hasher, "null"),
        JsonValue::Bool(value) => hash_str(hasher, if *value { "true" } else { "false" }),
        JsonValue::Number(value) => hash_str(hasher, &value.to_string()),
        JsonValue::String(value) => {
            hasher.write(b"str");
            hash_str(hasher, value);
        }
        JsonValue::Array(items) => {
            hasher.write(b"arr");
            for item in items {
                hash_json_value(hasher, item);
            }
            hasher.write(b"]");
        }
        JsonValue::Object(object) => {
            hasher.write(b"obj");
            for (key, value) in object {
                hash_str(hasher, key);
                hash_json_value(hasher, value);
            }
            hasher.write(b"}");
        }
    }
}

fn hash_str(hasher: &mut Fnv1a64, value: &str) {
    hasher.write(&(value.len() as u64).to_le_bytes());
    hasher.write(value.as_bytes());
}

struct Fnv1a64 {
    state: u64,
}

impl Default for Fnv1a64 {
    fn default() -> Self {
        Self {
            state: 0xcbf29ce484222325,
        }
    }
}

impl Fnv1a64 {
    fn write(&mut self, bytes: &[u8]) {
        for byte in bytes {
            self.state ^= u64::from(*byte);
            self.state = self.state.wrapping_mul(0x100000001b3);
        }
    }

    fn finish(&self) -> u64 {
        self.state
    }
}
