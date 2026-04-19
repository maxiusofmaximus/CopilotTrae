use std::collections::HashMap;

use crate::json::{get_number, get_object, get_string, get_string_array, parse_json, JsonError};

#[derive(Debug)]
pub struct RouteEnvelope {
    pub kind: String,
    pub snapshot_version: String,
    pub route: String,
    pub intent: String,
    pub payload: RoutePayload,
    pub evidence: Vec<String>,
    pub confidence: f64,
    pub threshold_applied: f64,
    pub threshold_source: String,
    pub resolver_path: Vec<String>,
}

#[derive(Debug)]
pub struct RoutePayload {
    pub tool_name: String,
    pub shell: String,
    pub argv: Vec<String>,
}

impl RouteEnvelope {
    pub fn from_json_str(input: &str) -> Result<Self, JsonError> {
        let root = parse_json(input)?;
        let object = root
            .as_object()
            .ok_or_else(|| JsonError::new("route fixture must be a JSON object"))?;
        let payload = get_object(object, "payload")?;

        Ok(Self {
            kind: get_string(object, "kind")?,
            snapshot_version: get_string(object, "snapshot_version")?,
            route: get_string(object, "route")?,
            intent: get_string(object, "intent")?,
            payload: RoutePayload {
                tool_name: get_string(payload, "tool_name")?,
                shell: get_string(payload, "shell")?,
                argv: get_string_array(payload, "argv")?,
            },
            evidence: get_string_array(object, "evidence")?,
            confidence: get_number(object, "confidence")?,
            threshold_applied: get_number(object, "threshold_applied")?,
            threshold_source: get_string(object, "threshold_source")?,
            resolver_path: get_string_array(object, "resolver_path")?,
        })
    }
}

#[derive(Debug)]
pub struct RouterErrorEnvelope {
    pub kind: String,
    pub snapshot_version: String,
    pub error_code: String,
    pub request_id: String,
    pub session_id: String,
    pub diagnostics: HashMap<String, String>,
}

impl RouterErrorEnvelope {
    pub fn from_json_str(input: &str) -> Result<Self, JsonError> {
        let root = parse_json(input)?;
        let object = root
            .as_object()
            .ok_or_else(|| JsonError::new("router error fixture must be a JSON object"))?;
        let diagnostics = get_object(object, "diagnostics")?;

        Ok(Self {
            kind: get_string(object, "kind")?,
            snapshot_version: get_string(object, "snapshot_version")?,
            error_code: get_string(object, "error_code")?,
            request_id: get_string(object, "request_id")?,
            session_id: get_string(object, "session_id")?,
            diagnostics: diagnostics
                .iter()
                .map(|(key, value)| {
                    value
                        .as_str()
                        .map(|inner| (key.clone(), inner.to_string()))
                        .ok_or_else(|| JsonError::new("router diagnostics values must be strings"))
                })
                .collect::<Result<HashMap<_, _>, _>>()?,
        })
    }
}
