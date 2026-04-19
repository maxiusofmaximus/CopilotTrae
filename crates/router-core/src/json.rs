use std::collections::BTreeMap;
use std::fmt;

pub type JsonObject = BTreeMap<String, JsonValue>;

#[derive(Debug, Clone, PartialEq)]
pub enum JsonValue {
    Null,
    Bool(bool),
    Number(f64),
    String(String),
    Array(Vec<JsonValue>),
    Object(JsonObject),
}

impl JsonValue {
    pub fn as_object(&self) -> Option<&JsonObject> {
        match self {
            Self::Object(value) => Some(value),
            _ => None,
        }
    }

    pub fn as_array(&self) -> Option<&[JsonValue]> {
        match self {
            Self::Array(value) => Some(value),
            _ => None,
        }
    }

    pub fn as_str(&self) -> Option<&str> {
        match self {
            Self::String(value) => Some(value),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct JsonError {
    message: String,
}

impl JsonError {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
        }
    }
}

impl fmt::Display for JsonError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.message)
    }
}

impl std::error::Error for JsonError {}

pub fn parse_json(input: &str) -> Result<JsonValue, JsonError> {
    let mut parser = Parser::new(input);
    let value = parser.parse_value()?;
    parser.skip_whitespace();

    if parser.is_eof() {
        Ok(value)
    } else {
        Err(JsonError::new("unexpected trailing content in JSON input"))
    }
}

pub fn get_array<'a>(object: &'a JsonObject, key: &str) -> Result<&'a [JsonValue], JsonError> {
    object
        .get(key)
        .and_then(JsonValue::as_array)
        .ok_or_else(|| JsonError::new(format!("missing array field `{key}`")))
}

pub fn get_object<'a>(object: &'a JsonObject, key: &str) -> Result<&'a JsonObject, JsonError> {
    object
        .get(key)
        .and_then(JsonValue::as_object)
        .ok_or_else(|| JsonError::new(format!("missing object field `{key}`")))
}

pub fn get_string(object: &JsonObject, key: &str) -> Result<String, JsonError> {
    object
        .get(key)
        .and_then(JsonValue::as_str)
        .map(ToOwned::to_owned)
        .ok_or_else(|| JsonError::new(format!("missing string field `{key}`")))
}

struct Parser<'a> {
    input: &'a [u8],
    position: usize,
}

impl<'a> Parser<'a> {
    fn new(input: &'a str) -> Self {
        Self {
            input: input.as_bytes(),
            position: 0,
        }
    }

    fn parse_value(&mut self) -> Result<JsonValue, JsonError> {
        self.skip_whitespace();

        match self.peek() {
            Some(b'{') => self.parse_object(),
            Some(b'[') => self.parse_array(),
            Some(b'"') => self.parse_string().map(JsonValue::String),
            Some(b't') => self.parse_true(),
            Some(b'f') => self.parse_false(),
            Some(b'n') => self.parse_null(),
            Some(b'-' | b'0'..=b'9') => self.parse_number(),
            Some(other) => Err(JsonError::new(format!(
                "unexpected character `{}` at position {}",
                other as char, self.position
            ))),
            None => Err(JsonError::new("unexpected end of JSON input")),
        }
    }

    fn parse_object(&mut self) -> Result<JsonValue, JsonError> {
        self.expect(b'{')?;
        self.skip_whitespace();

        let mut object = JsonObject::new();
        if self.peek() == Some(b'}') {
            self.position += 1;
            return Ok(JsonValue::Object(object));
        }

        loop {
            self.skip_whitespace();
            let key = self.parse_string()?;
            self.skip_whitespace();
            self.expect(b':')?;
            let value = self.parse_value()?;
            object.insert(key, value);
            self.skip_whitespace();

            match self.peek() {
                Some(b',') => self.position += 1,
                Some(b'}') => {
                    self.position += 1;
                    break;
                }
                _ => return Err(JsonError::new("unterminated JSON object")),
            }
        }

        Ok(JsonValue::Object(object))
    }

    fn parse_array(&mut self) -> Result<JsonValue, JsonError> {
        self.expect(b'[')?;
        self.skip_whitespace();

        let mut array = Vec::new();
        if self.peek() == Some(b']') {
            self.position += 1;
            return Ok(JsonValue::Array(array));
        }

        loop {
            array.push(self.parse_value()?);
            self.skip_whitespace();

            match self.peek() {
                Some(b',') => self.position += 1,
                Some(b']') => {
                    self.position += 1;
                    break;
                }
                _ => return Err(JsonError::new("unterminated JSON array")),
            }
        }

        Ok(JsonValue::Array(array))
    }

    fn parse_string(&mut self) -> Result<String, JsonError> {
        self.expect(b'"')?;
        let mut result = String::new();

        while let Some(byte) = self.next() {
            match byte {
                b'"' => return Ok(result),
                b'\\' => {
                    let escaped = self
                        .next()
                        .ok_or_else(|| JsonError::new("unterminated JSON escape sequence"))?;

                    match escaped {
                        b'"' => result.push('"'),
                        b'\\' => result.push('\\'),
                        b'/' => result.push('/'),
                        b'b' => result.push('\u{0008}'),
                        b'f' => result.push('\u{000C}'),
                        b'n' => result.push('\n'),
                        b'r' => result.push('\r'),
                        b't' => result.push('\t'),
                        b'u' => {
                            let code_point = self.parse_unicode_escape()?;
                            let character = char::from_u32(code_point)
                                .ok_or_else(|| JsonError::new("invalid unicode escape"))?;
                            result.push(character);
                        }
                        _ => return Err(JsonError::new("unsupported JSON escape sequence")),
                    }
                }
                _ => result.push(byte as char),
            }
        }

        Err(JsonError::new("unterminated JSON string"))
    }

    fn parse_unicode_escape(&mut self) -> Result<u32, JsonError> {
        let digits = self.take_exact(4)?;
        let value = std::str::from_utf8(digits)
            .map_err(|_| JsonError::new("unicode escape must be valid UTF-8"))?;

        u32::from_str_radix(value, 16).map_err(|_| JsonError::new("invalid unicode escape digits"))
    }

    fn parse_true(&mut self) -> Result<JsonValue, JsonError> {
        self.expect_sequence(b"true")?;
        Ok(JsonValue::Bool(true))
    }

    fn parse_false(&mut self) -> Result<JsonValue, JsonError> {
        self.expect_sequence(b"false")?;
        Ok(JsonValue::Bool(false))
    }

    fn parse_null(&mut self) -> Result<JsonValue, JsonError> {
        self.expect_sequence(b"null")?;
        Ok(JsonValue::Null)
    }

    fn parse_number(&mut self) -> Result<JsonValue, JsonError> {
        let start = self.position;

        if self.peek() == Some(b'-') {
            self.position += 1;
        }

        self.consume_digits();

        if self.peek() == Some(b'.') {
            self.position += 1;
            self.consume_digits();
        }

        if matches!(self.peek(), Some(b'e' | b'E')) {
            self.position += 1;
            if matches!(self.peek(), Some(b'+' | b'-')) {
                self.position += 1;
            }
            self.consume_digits();
        }

        let raw = std::str::from_utf8(&self.input[start..self.position])
            .map_err(|_| JsonError::new("numeric field must be valid UTF-8"))?;
        let value = raw
            .parse::<f64>()
            .map_err(|_| JsonError::new(format!("invalid JSON number `{raw}`")))?;

        Ok(JsonValue::Number(value))
    }

    fn consume_digits(&mut self) {
        while matches!(self.peek(), Some(b'0'..=b'9')) {
            self.position += 1;
        }
    }

    fn expect_sequence(&mut self, expected: &[u8]) -> Result<(), JsonError> {
        let actual = self.take_exact(expected.len())?;
        if actual == expected {
            Ok(())
        } else {
            Err(JsonError::new("invalid JSON literal"))
        }
    }

    fn expect(&mut self, expected: u8) -> Result<(), JsonError> {
        match self.next() {
            Some(actual) if actual == expected => Ok(()),
            _ => Err(JsonError::new(format!(
                "expected `{}` at position {}",
                expected as char, self.position
            ))),
        }
    }

    fn take_exact(&mut self, length: usize) -> Result<&'a [u8], JsonError> {
        if self.position + length > self.input.len() {
            return Err(JsonError::new("unexpected end of JSON input"));
        }

        let start = self.position;
        self.position += length;
        Ok(&self.input[start..self.position])
    }

    fn skip_whitespace(&mut self) {
        while matches!(self.peek(), Some(b' ' | b'\n' | b'\r' | b'\t')) {
            self.position += 1;
        }
    }

    fn peek(&self) -> Option<u8> {
        self.input.get(self.position).copied()
    }

    fn next(&mut self) -> Option<u8> {
        let value = self.peek()?;
        self.position += 1;
        Some(value)
    }

    fn is_eof(&self) -> bool {
        self.position >= self.input.len()
    }
}
