//! Contract v1 documents and the request checks the matcher repeats independently of Python.
//! Schemas: backend/matching/schemas/v1/.

use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::config::{self, Config};

pub const CONTRACT_VERSION: &str = "1";
pub const MAX_REQUEST_BYTES: usize = 64 * 1024;
pub const MAX_CANDIDATES: usize = 10;
pub const MAX_SUGGESTIONS: usize = 3;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub contract_version: String,
    pub algorithm_version: String,
    pub config_version: String,
    pub report: Report,
    pub candidates: Vec<Candidate>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Report {
    pub id: String,
    pub version: u64,
    pub title: String,
    pub description: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Candidate {
    pub id: String,
    pub version: u64,
    pub title: String,
    pub summary: String,
    pub linked_reports: Vec<LinkedReport>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LinkedReport {
    pub id: String,
    pub title: String,
    pub description: String,
}

#[derive(Debug, PartialEq, Serialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum Outcome {
    Ranked { suggestions: Vec<Suggestion> },
    Abstain { abstain_reason: AbstainReason },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AbstainReason {
    NoCandidates,
    BelowThreshold,
    InsufficientMargin,
}

#[derive(Debug, PartialEq, Serialize)]
pub struct Suggestion {
    pub problem_id: String,
    pub score: f64,
    pub features: BTreeMap<&'static str, f64>,
    pub evidence: Vec<Evidence>,
}

#[derive(Debug, PartialEq, Eq, Serialize)]
pub struct Evidence {
    pub record: Record,
    pub id: String,
    pub field: Field,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Record {
    Problem,
    LinkedReport,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Field {
    Title,
    Summary,
    Description,
}

#[derive(Debug, PartialEq, Serialize)]
pub struct Response {
    pub contract_version: &'static str,
    pub algorithm_version: String,
    pub config_version: String,
    #[serde(flatten)]
    pub outcome: Outcome,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ErrorCategory {
    InvalidRequest,
    UnsupportedVersion,
}

/// A rejected request. `detail` is a fixed string, so diagnostics never echo input text.
#[derive(Debug, PartialEq, Eq)]
pub struct Rejection {
    pub category: ErrorCategory,
    pub detail: &'static str,
}

#[derive(Serialize)]
pub struct ErrorDocument {
    pub contract_version: &'static str,
    pub status: &'static str,
    pub error: ErrorCategory,
}

impl Rejection {
    pub fn document(&self) -> ErrorDocument {
        ErrorDocument {
            contract_version: CONTRACT_VERSION,
            status: "error",
            error: self.category,
        }
    }
}

fn invalid(detail: &'static str) -> Rejection {
    Rejection {
        category: ErrorCategory::InvalidRequest,
        detail,
    }
}

fn unsupported(detail: &'static str) -> Rejection {
    Rejection {
        category: ErrorCategory::UnsupportedVersion,
        detail,
    }
}

/// Parses and validates request bytes, returning the request and the config it names.
pub fn parse_request(input: &[u8]) -> Result<(Request, &'static Config), Rejection> {
    if input.len() > MAX_REQUEST_BYTES {
        return Err(invalid("request exceeds byte limit"));
    }
    let document: Value =
        serde_json::from_slice(input).map_err(|_| invalid("not a UTF-8 JSON document"))?;
    match document.get("contract_version") {
        None => return Err(invalid("missing contract_version")),
        Some(Value::String(version)) if version == CONTRACT_VERSION => {}
        Some(_) => return Err(unsupported("unknown contract_version")),
    }
    let request: Request =
        serde_json::from_value(document).map_err(|_| invalid("request does not match schema"))?;
    check_fields(&request)?;
    let config = config::find(&request.algorithm_version, &request.config_version)
        .ok_or_else(|| unsupported("unknown algorithm_version or config_version"))?;
    if request
        .candidates
        .iter()
        .any(|candidate| candidate.linked_reports.len() > config.max_linked_reports)
    {
        return Err(invalid("too many linked reports"));
    }
    Ok((request, config))
}

fn check_fields(request: &Request) -> Result<(), Rejection> {
    if !is_version_name(&request.algorithm_version) || !is_version_name(&request.config_version) {
        return Err(invalid("malformed version name"));
    }
    let report = &request.report;
    if !is_uuid(&report.id) || report.version < 1 || report.title.is_empty() {
        return Err(invalid("malformed report"));
    }
    if request.candidates.len() > MAX_CANDIDATES {
        return Err(invalid("too many candidates"));
    }
    let mut candidate_ids = BTreeSet::new();
    let mut linked_ids = BTreeSet::new();
    for candidate in &request.candidates {
        if !is_uuid(&candidate.id) || candidate.version < 1 || candidate.title.is_empty() {
            return Err(invalid("malformed candidate"));
        }
        if !candidate_ids.insert(candidate.id.as_str()) {
            return Err(invalid("duplicate candidate id"));
        }
        for linked in &candidate.linked_reports {
            if !is_uuid(&linked.id) || linked.title.is_empty() {
                return Err(invalid("malformed linked report"));
            }
            if !linked_ids.insert(linked.id.as_str()) {
                return Err(invalid("duplicate linked report id"));
            }
        }
    }
    Ok(())
}

/// Canonical lowercase UUID, as in the schema's `uuid` definition.
fn is_uuid(value: &str) -> bool {
    let bytes = value.as_bytes();
    bytes.len() == 36
        && bytes.iter().enumerate().all(|(index, &byte)| match index {
            8 | 13 | 18 | 23 => byte == b'-',
            _ => byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte),
        })
}

/// `^[a-z0-9][a-z0-9.-]{0,63}$`
fn is_version_name(value: &str) -> bool {
    let bytes = value.as_bytes();
    let allowed = |byte: &u8| byte.is_ascii_lowercase() || byte.is_ascii_digit();
    !bytes.is_empty()
        && bytes.len() <= 64
        && allowed(&bytes[0])
        && bytes[1..]
            .iter()
            .all(|byte| allowed(byte) || *byte == b'.' || *byte == b'-')
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn uuid_shape() {
        assert!(is_uuid("00000000-0000-4000-8000-0000000000a1"));
        assert!(!is_uuid("00000000-0000-4000-8000-0000000000A1"));
        assert!(!is_uuid("00000000-0000-4000-8000-0000000000a"));
        assert!(!is_uuid("00000000a0000-4000-8000-0000000000a1"));
    }

    #[test]
    fn version_name_shape() {
        assert!(is_version_name("lexical-1.0"));
        assert!(!is_version_name(""));
        assert!(!is_version_name("-lexical"));
        assert!(!is_version_name("Lexical"));
        assert!(is_version_name(&"a".repeat(64)));
        assert!(!is_version_name(&"a".repeat(65)));
    }
}
