mod classifier;
mod errors;
mod json;
mod pipeline;
mod registry;
mod snapshot;

pub use classifier::{normalize_input, parse_command_shape};
pub use errors::RouterErrorEnvelope;
pub use json::{JsonError, JsonObject, JsonValue};
pub use pipeline::{DeterministicRouter, RouteEnvelope, RoutePayload, RouteResolution, TerminalRequest};
pub use registry::{ModuleRegistry, ToolRegistry, build_registry_snapshot, typed_empty_extensions};
pub use snapshot::RegistrySnapshot;
