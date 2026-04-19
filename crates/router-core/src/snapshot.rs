use crate::json::{JsonError, JsonObject, JsonValue, get_array, get_object, get_string, parse_json};

#[derive(Debug, Clone, PartialEq)]
pub struct RegistrySnapshot {
    pub snapshot_version: String,
    pub built_for_session: String,
    pub built_at: String,
    pub tools: Vec<JsonObject>,
    pub modules: Vec<JsonObject>,
    pub policies: JsonObject,
    pub source_versions: JsonObject,
    pub execution_surface: JsonObject,
    pub capability_surface: JsonObject,
    pub extensions: JsonObject,
}

impl RegistrySnapshot {
    pub fn minimal(snapshot_version: String, built_for_session: String) -> Self {
        Self {
            snapshot_version,
            built_for_session,
            built_at: String::new(),
            tools: Vec::new(),
            modules: Vec::new(),
            policies: JsonObject::new(),
            source_versions: JsonObject::new(),
            execution_surface: JsonObject::new(),
            capability_surface: JsonObject::new(),
            extensions: JsonObject::new(),
        }
    }

    pub fn from_json_str(input: &str) -> Result<Self, JsonError> {
        let root = parse_json(input)?;
        let object = root
            .as_object()
            .ok_or_else(|| JsonError::new("snapshot fixture must be a JSON object"))?;

        Ok(Self {
            snapshot_version: get_string(object, "snapshot_version")?,
            built_for_session: get_string(object, "built_for_session")?,
            built_at: get_string(object, "built_at")?,
            tools: array_of_objects(get_array(object, "tools")?, "tools")?,
            modules: array_of_objects(get_array(object, "modules")?, "modules")?,
            policies: get_object(object, "policies")?.clone(),
            source_versions: get_object(object, "source_versions")?.clone(),
            execution_surface: get_object(object, "execution_surface")?.clone(),
            capability_surface: get_object(object, "capability_surface")?.clone(),
            extensions: get_object(object, "extensions")?.clone(),
        })
    }
}

fn array_of_objects(values: &[JsonValue], field_name: &str) -> Result<Vec<JsonObject>, JsonError> {
    values
        .iter()
        .map(|value| {
            value
                .as_object()
                .cloned()
                .ok_or_else(|| JsonError::new(format!("array field `{field_name}` must contain objects")))
        })
        .collect()
}
