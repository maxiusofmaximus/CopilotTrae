use crate::classifier::{normalize_input, parse_command_shape};
use crate::errors::RouterErrorEnvelope;
use crate::json::{JsonObject, JsonValue};
use crate::snapshot::RegistrySnapshot;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TerminalRequest {
    pub request_id: String,
    pub session_id: String,
    pub shell: String,
    pub raw_input: String,
    pub cwd: String,
    pub snapshot_version: String,
}

#[derive(Debug, Clone, PartialEq)]
pub enum RoutePayload {
    ToolExecution {
        tool_name: String,
        shell: String,
        argv: Vec<String>,
    },
    CommandFix {
        original: String,
        suggested_command: String,
    },
    Clarification {
        original: String,
        options: Vec<String>,
    },
}

impl RoutePayload {
    pub fn tool_name(&self) -> Option<&str> {
        match self {
            Self::ToolExecution { tool_name, .. } => Some(tool_name.as_str()),
            _ => None,
        }
    }

    pub fn shell(&self) -> Option<&str> {
        match self {
            Self::ToolExecution { shell, .. } => Some(shell.as_str()),
            _ => None,
        }
    }

    pub fn argv(&self) -> Option<&[String]> {
        match self {
            Self::ToolExecution { argv, .. } => Some(argv.as_slice()),
            _ => None,
        }
    }

    pub fn suggested_command(&self) -> Option<&str> {
        match self {
            Self::CommandFix {
                suggested_command, ..
            } => Some(suggested_command.as_str()),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
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

impl RouteEnvelope {
    fn tool_execution(
        snapshot_version: &str,
        tool_name: &str,
        shell: &str,
        argv: Vec<String>,
        resolver_path: Vec<String>,
    ) -> Self {
        Self {
            kind: "route".to_string(),
            snapshot_version: snapshot_version.to_string(),
            route: "tool_execution".to_string(),
            intent: "tool_execution".to_string(),
            payload: RoutePayload::ToolExecution {
                tool_name: tool_name.to_string(),
                shell: shell.to_string(),
                argv,
            },
            evidence: vec![format!("tool_name_match:{tool_name}")],
            confidence: 1.0,
            threshold_applied: 0.93,
            threshold_source: "intent:execution".to_string(),
            resolver_path,
        }
    }

    fn command_fix(
        snapshot_version: &str,
        original: &str,
        suggested_command: String,
        evidence: Vec<String>,
        confidence: f64,
        resolver_path: Vec<String>,
    ) -> Self {
        Self {
            kind: "route".to_string(),
            snapshot_version: snapshot_version.to_string(),
            route: "command_fix".to_string(),
            intent: "correction".to_string(),
            payload: RoutePayload::CommandFix {
                original: original.to_string(),
                suggested_command,
            },
            evidence,
            confidence,
            threshold_applied: 0.90,
            threshold_source: "intent:command_fix".to_string(),
            resolver_path,
        }
    }

    fn clarification(
        snapshot_version: &str,
        original: &str,
        options: Vec<String>,
        evidence: Vec<String>,
        confidence: f64,
        resolver_path: Vec<String>,
    ) -> Self {
        Self {
            kind: "route".to_string(),
            snapshot_version: snapshot_version.to_string(),
            route: "clarification".to_string(),
            intent: "correction".to_string(),
            payload: RoutePayload::Clarification {
                original: original.to_string(),
                options,
            },
            evidence,
            confidence,
            threshold_applied: 0.90,
            threshold_source: "intent:command_fix".to_string(),
            resolver_path,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum RouteResolution {
    Route(RouteEnvelope),
    Error(RouterErrorEnvelope),
}

#[derive(Debug, Clone)]
pub struct DeterministicRouter;

impl Default for DeterministicRouter {
    fn default() -> Self {
        Self
    }
}

impl DeterministicRouter {
    pub fn resolve(
        &self,
        request: &TerminalRequest,
        snapshot: &RegistrySnapshot,
    ) -> RouteResolution {
        if request.snapshot_version != snapshot.snapshot_version {
            return RouteResolution::Error(RouterErrorEnvelope::snapshot_version_mismatch(
                &request.request_id,
                &request.session_id,
                &request.snapshot_version,
                &snapshot.snapshot_version,
            ));
        }

        let mut resolver_path = Vec::new();
        let normalized = normalize_input(&request.raw_input);
        resolver_path.push("normalize_input".to_string());
        let (command, args) = parse_command_shape(&normalized);
        resolver_path.push("parse_command_shape".to_string());
        resolver_path.push("classify_intent".to_string());

        let tools = execution_tools(snapshot);
        resolver_path.push("resolve_local_candidates".to_string());
        let matching_tool = tools.iter().find(|tool| {
            string_field(tool, "tool_name")
                .is_some_and(|tool_name| tool_name == command)
                && bool_field(tool, "available").unwrap_or(false)
        });

        resolver_path.push("apply_deterministic_rules".to_string());
        if let Some(tool) = matching_tool {
            let tool_name = string_field(tool, "tool_name").unwrap_or_default();
            let shell = string_field(tool, "shell").unwrap_or(&request.shell);
            resolver_path.push("evaluate_confidence".to_string());

            return RouteResolution::Route(RouteEnvelope::tool_execution(
                &snapshot.snapshot_version,
                tool_name,
                shell,
                std::iter::once(command).chain(args).collect(),
                resolver_path,
            ));
        }

        let mut fix_path = resolver_path;
        fix_path.push("fixes.collect_alias_matches".to_string());
        let alias_matches = collect_alias_matches(&command, &tools);
        fix_path.push("fixes.collect_suffix_matches".to_string());
        let suffix_matches = collect_suffix_matches(&command, &tools);
        fix_path.push("fixes.rank_candidates".to_string());

        let candidates = rank_candidates(alias_matches, suffix_matches);
        fix_path.push("evaluate_confidence".to_string());

        if candidates.is_empty() {
            return RouteResolution::Route(RouteEnvelope::clarification(
                &snapshot.snapshot_version,
                &normalized,
                Vec::new(),
                vec!["no_fix_candidates".to_string()],
                0.0,
                fix_path,
            ));
        }

        let top_score = candidates[0].score;
        let top_candidates = candidates
            .into_iter()
            .take_while(|candidate| candidate.score == top_score)
            .collect::<Vec<_>>();
        let options = top_candidates
            .iter()
            .map(|candidate| suggested_command(&candidate.tool_name, &args))
            .collect::<Vec<_>>();
        let evidence = top_candidates
            .iter()
            .map(|candidate| candidate.evidence.clone())
            .collect::<Vec<_>>();

        if top_candidates.len() > 1 || top_score < 0.90 {
            return RouteResolution::Route(RouteEnvelope::clarification(
                &snapshot.snapshot_version,
                &normalized,
                options,
                evidence,
                top_score,
                fix_path,
            ));
        }

        let chosen = &top_candidates[0];
        RouteResolution::Route(RouteEnvelope::command_fix(
            &snapshot.snapshot_version,
            &normalized,
            suggested_command(&chosen.tool_name, &args),
            vec![chosen.evidence.clone()],
            chosen.score,
            fix_path,
        ))
    }
}

#[derive(Debug, Clone, PartialEq)]
struct Candidate {
    tool_name: String,
    score: f64,
    evidence: String,
}

fn execution_tools(snapshot: &RegistrySnapshot) -> Vec<JsonObject> {
    snapshot
        .execution_surface
        .get("tools")
        .and_then(JsonValue::as_array)
        .map(|tools| {
            tools
                .iter()
                .filter_map(|tool| tool.as_object().cloned())
                .collect::<Vec<_>>()
        })
        .unwrap_or_default()
}

fn collect_alias_matches(command: &str, tools: &[JsonObject]) -> Vec<Candidate> {
    let normalized_command = normalize_token(command);
    let mut matches = Vec::new();

    for tool in tools {
        let tool_name = string_field(tool, "tool_name").unwrap_or_default();
        if normalized_command == normalize_token(tool_name) {
            matches.push(Candidate {
                tool_name: tool_name.to_string(),
                score: 1.0,
                evidence: format!("tool_name_match:{tool_name}"),
            });
            continue;
        }

        let aliases = array_of_strings(tool, "aliases");
        if let Some(alias) = aliases
            .iter()
            .find(|alias| normalized_command == normalize_token(alias))
        {
            matches.push(Candidate {
                tool_name: tool_name.to_string(),
                score: 1.0,
                evidence: format!("alias_match:{alias}"),
            });
        }
    }

    matches
}

fn collect_suffix_matches(command: &str, tools: &[JsonObject]) -> Vec<Candidate> {
    let normalized_command = normalize_token(command);
    let mut matches = Vec::new();

    for tool in tools {
        let tool_name = string_field(tool, "tool_name").unwrap_or_default();
        let normalized_tool_name = normalize_token(tool_name);
        if normalized_command.ends_with(&normalized_tool_name)
            || normalized_tool_name.ends_with(&normalized_command)
        {
            matches.push(Candidate {
                tool_name: tool_name.to_string(),
                score: 0.9,
                evidence: format!("suffix_match:{tool_name}"),
            });
            continue;
        }

        for alias in array_of_strings(tool, "aliases") {
            let normalized_alias = normalize_token(&alias);
            if normalized_command.ends_with(&normalized_alias)
                || normalized_alias.ends_with(&normalized_command)
            {
                matches.push(Candidate {
                    tool_name: tool_name.to_string(),
                    score: 0.9,
                    evidence: format!("suffix_match:{alias}"),
                });
                break;
            }
        }
    }

    matches
}

fn rank_candidates(
    alias_matches: Vec<Candidate>,
    suffix_matches: Vec<Candidate>,
) -> Vec<Candidate> {
    let mut best_by_tool = std::collections::BTreeMap::new();

    for candidate in alias_matches.into_iter().chain(suffix_matches) {
        let should_replace = best_by_tool
            .get(&candidate.tool_name)
            .map(|current: &Candidate| candidate.score > current.score)
            .unwrap_or(true);
        if should_replace {
            best_by_tool.insert(candidate.tool_name.clone(), candidate);
        }
    }

    let mut ranked = best_by_tool.into_values().collect::<Vec<_>>();
    ranked.sort_by(|left, right| {
        right
            .score
            .total_cmp(&left.score)
            .then_with(|| left.tool_name.cmp(&right.tool_name))
    });
    ranked
}

fn suggested_command(tool_name: &str, args: &[String]) -> String {
    if args.is_empty() {
        return tool_name.to_string();
    }

    format!("{tool_name} {}", args.join(" "))
}

fn normalize_token(value: &str) -> String {
    value.to_ascii_lowercase().replace(['.', '_'], "-")
}

fn string_field<'a>(object: &'a JsonObject, field_name: &str) -> Option<&'a str> {
    object.get(field_name)?.as_str()
}

fn bool_field(object: &JsonObject, field_name: &str) -> Option<bool> {
    match object.get(field_name)? {
        JsonValue::Bool(value) => Some(*value),
        _ => None,
    }
}

fn array_of_strings(object: &JsonObject, field_name: &str) -> Vec<String> {
    object
        .get(field_name)
        .and_then(JsonValue::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(|item| item.as_str().map(ToOwned::to_owned))
                .collect::<Vec<_>>()
        })
        .unwrap_or_default()
}
