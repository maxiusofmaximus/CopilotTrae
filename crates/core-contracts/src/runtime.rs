use crate::json::{
    get_array, get_object, get_optional_value, get_string, parse_json, JsonError, JsonValue,
};

#[derive(Debug)]
pub struct SessionReply {
    pub timestamp: String,
    pub event: String,
    pub provider: String,
    pub model: String,
    pub request: SessionRequest,
    pub response: SessionResponse,
}

impl SessionReply {
    pub fn from_json_str(input: &str) -> Result<Self, JsonError> {
        let root = parse_json(input)?;
        let object = root
            .as_object()
            .ok_or_else(|| JsonError::new("runtime fixture must be a JSON object"))?;
        let request = get_object(object, "request")?;
        let response = get_object(object, "response")?;
        let messages = get_array(request, "messages")?;

        Ok(Self {
            timestamp: get_string(object, "timestamp")?,
            event: get_string(object, "event")?,
            provider: get_string(object, "provider")?,
            model: get_string(object, "model")?,
            request: SessionRequest {
                input: get_string(request, "input")?,
                messages: messages
                    .iter()
                    .map(SessionMessage::from_json_value)
                    .collect::<Result<Vec<_>, _>>()?,
            },
            response: SessionResponse {
                content: get_string(response, "content")?,
                finish_reason: get_string(response, "finish_reason")?,
                usage: get_optional_value(response, "usage"),
            },
        })
    }
}

#[derive(Debug)]
pub struct SessionRequest {
    pub input: String,
    pub messages: Vec<SessionMessage>,
}

#[derive(Debug)]
pub struct SessionMessage {
    pub role: String,
    pub content: String,
}

impl SessionMessage {
    fn from_json_value(value: &JsonValue) -> Result<Self, JsonError> {
        let object = value
            .as_object()
            .ok_or_else(|| JsonError::new("runtime message must be a JSON object"))?;

        Ok(Self {
            role: get_string(object, "role")?,
            content: get_string(object, "content")?,
        })
    }
}

#[derive(Debug)]
pub struct SessionResponse {
    pub content: String,
    pub finish_reason: String,
    pub usage: Option<JsonValue>,
}
