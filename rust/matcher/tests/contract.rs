//! Shared contract fixtures from backend/matching, plus ranking edge cases.

use std::fs;
use std::io::Write;
use std::path::PathBuf;
use std::process::{Command, Stdio};

use matcher::config::SOURCES;
use matcher::contract::{AbstainReason, ErrorCategory, Outcome};
use matcher::normalize::tokens;
use serde_json::{Value, json};

fn backend_matching() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../backend/matching")
}

fn load(relative: &str) -> Value {
    let text = fs::read_to_string(backend_matching().join(relative)).expect("fixture exists");
    serde_json::from_str(&text).expect("fixture is JSON")
}

fn rank(request: &Value) -> Outcome {
    matcher::handle(&serde_json::to_vec(request).unwrap())
        .expect("request is accepted")
        .outcome
}

#[test]
fn tokenizer_matches_every_fixture() {
    let fixtures = load("normalization.json");
    for fixture in fixtures["fixtures"].as_array().unwrap() {
        let expected: Vec<String> = serde_json::from_value(fixture["tokens"].clone()).unwrap();
        assert_eq!(
            tokens(fixture["input"].as_str().unwrap()),
            expected,
            "{}",
            fixture["name"]
        );
    }
}

#[test]
fn every_config_file_is_embedded() {
    let mut on_disk: Vec<String> = fs::read_dir(backend_matching().join("configs"))
        .unwrap()
        .map(|entry| fs::read_to_string(entry.unwrap().path()).unwrap())
        .collect();
    let mut embedded: Vec<String> = SOURCES.iter().map(|source| source.to_string()).collect();
    on_disk.sort();
    embedded.sort();
    assert_eq!(on_disk, embedded);
}

#[test]
fn example_requests_get_their_expected_outcome() {
    let examples = load("schemas/v1/examples.json");
    for example in examples["requests"].as_array().unwrap() {
        let name = &example["name"];
        let bytes = serde_json::to_vec(&example["document"]).unwrap();
        let result = matcher::handle(&bytes);
        match example["expect"].as_str().unwrap() {
            "ok" => {
                let response = result.unwrap_or_else(|r| panic!("{name}: {r:?}"));
                assert_eq!(
                    response.config_version,
                    example["document"]["config_version"]
                );
            }
            "invalid_request" => {
                assert_eq!(
                    result.unwrap_err().category,
                    ErrorCategory::InvalidRequest,
                    "{name}"
                )
            }
            "unsupported_version" => assert_eq!(
                result.unwrap_err().category,
                ErrorCategory::UnsupportedVersion,
                "{name}"
            ),
            other => panic!("{name}: unexpected expectation {other}"),
        }
    }
}

fn valid_request() -> Value {
    let examples = load("schemas/v1/examples.json");
    examples["requests"]
        .as_array()
        .unwrap()
        .iter()
        .find(|example| example["name"] == "valid")
        .unwrap()["document"]
        .clone()
}

fn uuid(n: u32) -> String {
    format!("00000000-0000-4000-8000-{n:012x}")
}

fn candidate(n: u32, title: &str, summary: &str) -> Value {
    json!({"id": uuid(n), "version": 1, "title": title, "summary": summary, "linked_reports": []})
}

fn request(title: &str, description: &str, candidates: Vec<Value>) -> Value {
    let mut request = valid_request();
    request["report"]["title"] = json!(title);
    request["report"]["description"] = json!(description);
    request["candidates"] = Value::Array(candidates);
    request
}

#[test]
fn valid_example_ranks_the_matching_problem_first() {
    let Outcome::Ranked { suggestions } = rank(&valid_request()) else {
        panic!("expected a ranking");
    };
    assert_eq!(
        suggestions[0].problem_id,
        "00000000-0000-4000-8000-0000000000a1"
    );
    assert!(suggestions[0].evidence.iter().all(|e| !e.id.is_empty()));
}

#[test]
fn replay_is_byte_identical() {
    let bytes = serde_json::to_vec(&valid_request()).unwrap();
    let first = serde_json::to_vec(&matcher::handle(&bytes).unwrap()).unwrap();
    for _ in 0..20 {
        assert_eq!(
            serde_json::to_vec(&matcher::handle(&bytes).unwrap()).unwrap(),
            first
        );
    }
}

#[test]
fn empty_pool_abstains_with_no_candidates() {
    assert_eq!(
        rank(&request("Anything", "", vec![])),
        Outcome::Abstain {
            abstain_reason: AbstainReason::NoCandidates
        }
    );
}

#[test]
fn unrelated_pool_abstains_below_threshold() {
    let outcome = rank(&request(
        "Invoice totals are wrong",
        "",
        vec![
            candidate(1, "Login page is slow", ""),
            candidate(2, "Dark mode colours", ""),
        ],
    ));
    assert_eq!(
        outcome,
        Outcome::Abstain {
            abstain_reason: AbstainReason::BelowThreshold
        }
    );
}

#[test]
fn empty_and_punctuation_only_text_abstains() {
    let outcome = rank(&request(
        "!!!",
        "   ",
        vec![candidate(1, "Login page is slow", "")],
    ));
    assert_eq!(
        outcome,
        Outcome::Abstain {
            abstain_reason: AbstainReason::BelowThreshold
        }
    );
}

#[test]
fn identical_candidates_abstain_on_margin() {
    let outcome = rank(&request(
        "CSV export times out",
        "",
        vec![
            candidate(1, "CSV export times out", ""),
            candidate(2, "CSV export times out", ""),
        ],
    ));
    assert_eq!(
        outcome,
        Outcome::Abstain {
            abstain_reason: AbstainReason::InsufficientMargin
        }
    );
}

#[test]
fn ties_break_by_problem_id() {
    // A clear leader, then two candidates whose single shared words have equal weight.
    let outcome = rank(&request(
        "alpha beta gamma delta",
        "",
        vec![
            candidate(9, "alpha beta gamma delta", "alpha beta gamma delta"),
            candidate(5, "gamma", ""),
            candidate(3, "delta", ""),
        ],
    ));
    let Outcome::Ranked { suggestions } = outcome else {
        panic!("expected a ranking, got {outcome:?}");
    };
    let ids: Vec<&str> = suggestions.iter().map(|s| s.problem_id.as_str()).collect();
    assert_eq!(ids, [uuid(9), uuid(3), uuid(5)]);
    assert_eq!(suggestions[1].score, suggestions[2].score);
}

#[test]
fn similar_but_distinct_problems_prefer_the_closer_wording() {
    let outcome = rank(&request(
        "SSO login loops back to the sign-in page",
        "After entering Okta credentials the browser returns to sign-in.",
        vec![
            candidate(
                1,
                "SSO login redirect loop",
                "Okta sign-in returns to the sign-in page.",
            ),
            candidate(
                2,
                "Password reset email not sent",
                "Reset emails never arrive.",
            ),
            candidate(
                3,
                "Login page slow to load",
                "The login page takes 10 seconds.",
            ),
        ],
    ));
    let Outcome::Ranked { suggestions } = outcome else {
        panic!("expected a ranking, got {outcome:?}");
    };
    assert_eq!(suggestions[0].problem_id, uuid(1));
}

#[test]
fn duplicate_tokens_do_not_inflate_scores() {
    let pool = vec![
        candidate(1, "Export fails", ""),
        candidate(2, "Login slow", ""),
    ];
    let once = rank(&request("Export fails", "", pool.clone()));
    let repeated = rank(&request("Export fails export fails EXPORT FAILS", "", pool));
    assert_eq!(once, repeated);
}

#[test]
fn unicode_text_matches_after_lowercasing() {
    let outcome = rank(&request(
        "ÉCHEC de l'export",
        "",
        vec![
            candidate(1, "échec export", ""),
            candidate(2, "connexion lente", ""),
        ],
    ));
    let Outcome::Ranked { suggestions } = outcome else {
        panic!("expected a ranking, got {outcome:?}");
    };
    assert_eq!(suggestions[0].problem_id, uuid(1));
}

#[test]
fn negation_is_kept_as_its_own_token() {
    // Lexical features cannot read negation; the contraction survives so a config can use it.
    assert_eq!(tokens("Export doesn't fail"), ["export", "doesnt", "fail"]);
}

#[test]
fn evidence_names_only_supplied_records_with_shared_words() {
    let mut pool = vec![candidate(1, "CSV export times out", "Nothing related")];
    pool[0]["linked_reports"] = json!([
        {"id": uuid(100), "title": "Unrelated", "description": "CSV export spinner"},
        {"id": uuid(101), "title": "Different words", "description": "Nothing"}
    ]);
    pool.push(candidate(2, "Login slow", ""));
    let Outcome::Ranked { suggestions } = rank(&request("CSV export times out", "", pool)) else {
        panic!("expected a ranking");
    };
    let evidence: Vec<(String, String)> = suggestions[0]
        .evidence
        .iter()
        .map(|e| {
            let value = serde_json::to_value(e).unwrap();
            (
                value["id"].as_str().unwrap().to_owned(),
                value["field"].as_str().unwrap().to_owned(),
            )
        })
        .collect();
    assert_eq!(
        evidence,
        [
            (uuid(1), "title".to_owned()),
            (uuid(100), "description".to_owned())
        ]
    );
}

#[test]
fn too_many_linked_reports_are_rejected_not_truncated() {
    let mut pool = vec![candidate(1, "CSV export", "")];
    let linked: Vec<Value> = (0..6)
        .map(|n| json!({"id": uuid(200 + n), "title": "t", "description": ""}))
        .collect();
    pool[0]["linked_reports"] = Value::Array(linked);
    let bytes = serde_json::to_vec(&request("CSV export", "", pool)).unwrap();
    assert_eq!(
        matcher::handle(&bytes).unwrap_err().category,
        ErrorCategory::InvalidRequest
    );
}

#[test]
fn oversized_request_is_rejected() {
    let bytes = serde_json::to_vec(&request("CSV", &"x".repeat(70_000), vec![])).unwrap();
    assert_eq!(
        matcher::handle(&bytes).unwrap_err().category,
        ErrorCategory::InvalidRequest
    );
}

fn run_binary(input: &[u8]) -> (i32, Value) {
    let mut child = Command::new(env!("CARGO_BIN_EXE_matcher"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    child.stdin.take().unwrap().write_all(input).unwrap();
    let output = child.wait_with_output().unwrap();
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(!stderr.contains("CSV"), "stderr must not echo input text");
    (
        output.status.code().unwrap(),
        serde_json::from_slice(&output.stdout).expect("stdout is one JSON document"),
    )
}

#[test]
fn binary_writes_one_document_and_exit_code() {
    let (code, document) = run_binary(&serde_json::to_vec(&valid_request()).unwrap());
    assert_eq!(code, 0);
    assert_eq!(document["status"], "ranked");
    assert_eq!(document["contract_version"], "1");

    let (code, document) = run_binary(b"{\"contract_version\":\"1\",\"title\":\"CSV\"}");
    assert_eq!(code, 2);
    assert_eq!(
        document,
        json!({"contract_version": "1", "status": "error", "error": "invalid_request"})
    );

    let (code, document) = run_binary(&vec![b' '; 70_000]);
    assert_eq!(code, 2);
    assert_eq!(document["error"], "invalid_request");
}
