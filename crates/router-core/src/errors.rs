use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RouterErrorEnvelope {
    pub kind: String,
    pub snapshot_version: String,
    pub error_code: String,
    pub request_id: String,
    pub session_id: String,
    pub diagnostics: HashMap<String, String>,
}

impl RouterErrorEnvelope {
    pub fn snapshot_version_mismatch(
        request_id: &str,
        session_id: &str,
        request_snapshot_version: &str,
        active_snapshot_version: &str,
    ) -> Self {
        Self {
            kind: "router_error".to_string(),
            snapshot_version: active_snapshot_version.to_string(),
            error_code: "snapshot_version_mismatch".to_string(),
            request_id: request_id.to_string(),
            session_id: session_id.to_string(),
            diagnostics: HashMap::from([
                (
                    "request_snapshot_version".to_string(),
                    request_snapshot_version.to_string(),
                ),
                (
                    "active_snapshot_version".to_string(),
                    active_snapshot_version.to_string(),
                ),
            ]),
        }
    }
}
