pub fn normalize_input(raw_input: &str) -> String {
    raw_input.split_whitespace().collect::<Vec<_>>().join(" ")
}

pub fn parse_command_shape(normalized_input: &str) -> (String, Vec<String>) {
    let mut parts = normalized_input.split_whitespace();
    let Some(command) = parts.next() else {
        return (String::new(), Vec::new());
    };

    (
        command.to_string(),
        parts.map(ToOwned::to_owned).collect::<Vec<_>>(),
    )
}
