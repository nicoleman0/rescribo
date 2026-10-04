//! Algorithm `lexical-1`: IDF-weighted token-set overlap between the report and each
//! candidate field. Ordered collections keep float sums, and so scores, repeatable.
//! Algorithm `lexical-2`: the same, but report clauses that say something works or is fixed
//! are left out, so a report naming a resolved problem does not match it.

use std::collections::{BTreeMap, BTreeSet};

use crate::config::Config;
use crate::contract::{
    AbstainReason, Candidate, Evidence, Field, MAX_SUGGESTIONS, Outcome, Record, Report, Request,
    Suggestion,
};
use crate::normalize::tokens;

/// lexical-2: a clause holding one of these words says its subject works.
const RESOLVED_WORDS: [&str; 7] = [
    "anymore", "fine", "fixed", "resolved", "worked", "working", "works",
];
/// lexical-2: two-word phrases with the same meaning.
const RESOLVED_PHRASES: [[&str; 2]; 1] = [["no", "longer"]];
/// lexical-2: words that start a new clause inside a sentence.
const CLAUSE_WORDS: [&str; 2] = ["but", "however"];

pub const ALGORITHM_VERSIONS: [&str; 2] = ["lexical-1", "lexical-2"];
/// Sorted, matching the order configs list weights in.
pub const FEATURES: [&str; 3] = ["linked_overlap", "summary_overlap", "title_overlap"];

type Bag = BTreeSet<String>;

fn bag(texts: &[&str]) -> Bag {
    texts.iter().flat_map(|text| tokens(text)).collect()
}

/// Inverse document frequency over the candidate pool, where each candidate is one document.
struct Weights {
    pool_size: f64,
    frequency: BTreeMap<String, usize>,
}

impl Weights {
    fn new(documents: &[Bag]) -> Weights {
        let mut frequency = BTreeMap::new();
        for document in documents {
            for token in document {
                *frequency.entry(token.clone()).or_insert(0) += 1;
            }
        }
        Weights {
            pool_size: documents.len() as f64,
            frequency,
        }
    }

    /// Always positive: a token in every candidate still counts a little.
    fn squared(&self, token: &str) -> f64 {
        let frequency = self.frequency.get(token).copied().unwrap_or(0) as f64;
        let idf = ((self.pool_size + 1.0) / (frequency + 0.5)).ln();
        idf * idf
    }

    fn norm(&self, bag: &Bag) -> f64 {
        bag.iter()
            .map(|token| self.squared(token))
            .sum::<f64>()
            .sqrt()
    }

    /// Report words found in no candidate cannot tell candidates apart, and would otherwise
    /// carry the highest weight and push every score down for long reports.
    fn report_norm(&self, report: &Bag) -> f64 {
        let in_pool: Bag = report
            .iter()
            .filter(|token| self.frequency.contains_key(*token))
            .cloned()
            .collect();
        self.norm(&in_pool)
    }

    /// Cosine similarity of the two sets under IDF weights, in [0, 1].
    fn overlap(&self, report: &Bag, report_norm: f64, field: &Bag) -> f64 {
        let field_norm = self.norm(field);
        if report_norm == 0.0 || field_norm == 0.0 {
            return 0.0;
        }
        let shared: f64 = report
            .intersection(field)
            .map(|token| self.squared(token))
            .sum();
        shared / (report_norm * field_norm)
    }
}

struct Scored<'a> {
    candidate: &'a Candidate,
    score: f64,
    features: BTreeMap<&'static str, f64>,
    evidence: Vec<Evidence>,
}

pub fn rank(request: &Request, config: &Config) -> Outcome {
    if request.candidates.is_empty() {
        return Outcome::Abstain {
            abstain_reason: AbstainReason::NoCandidates,
        };
    }
    let report = report_bag(&request.report, &config.algorithm_version);
    let documents: Vec<Bag> = request.candidates.iter().map(candidate_bag).collect();
    let weights = Weights::new(&documents);
    let report_norm = weights.report_norm(&report);

    let mut scored: Vec<Scored> = request
        .candidates
        .iter()
        .map(|candidate| score(candidate, &report, report_norm, &weights, config))
        .filter(|scored| scored.score > 0.0)
        .collect();
    scored.sort_by(|a, b| {
        b.score
            .total_cmp(&a.score)
            .then_with(|| a.candidate.id.cmp(&b.candidate.id))
    });

    let Some(top) = scored.first() else {
        return abstain(AbstainReason::BelowThreshold);
    };
    if top.score < config.min_score {
        return abstain(AbstainReason::BelowThreshold);
    }
    if scored
        .get(1)
        .is_some_and(|second| top.score - second.score < config.min_margin)
    {
        return abstain(AbstainReason::InsufficientMargin);
    }
    let suggestions = scored
        .into_iter()
        .filter(|scored| scored.score >= config.min_score)
        .take(MAX_SUGGESTIONS)
        .map(|scored| Suggestion {
            problem_id: scored.candidate.id.clone(),
            score: scored.score,
            features: scored.features,
            evidence: scored.evidence,
        })
        .collect();
    Outcome::Ranked { suggestions }
}

fn abstain(reason: AbstainReason) -> Outcome {
    Outcome::Abstain {
        abstain_reason: reason,
    }
}

fn report_bag(report: &Report, algorithm: &str) -> Bag {
    let texts = [report.title.as_str(), report.description.as_str()];
    match algorithm {
        "lexical-1" => bag(&texts),
        "lexical-2" => texts
            .iter()
            .flat_map(|text| clauses(text))
            .filter(|clause| !states_resolution(clause))
            .flatten()
            .collect(),
        other => unreachable!("config admits only known algorithms, not {other}"),
    }
}

/// Splits at sentence punctuation and semicolons, then at clause words. A colon does not split,
/// because what follows it usually explains the same statement. A full stop counts only before
/// whitespace or the end, so versions such as `v2.4.1` stay whole.
fn clauses(text: &str) -> Vec<Vec<String>> {
    let chars: Vec<char> = text.chars().collect();
    let mut segments = Vec::new();
    let mut start = 0;
    for (index, &character) in chars.iter().enumerate() {
        let boundary = match character {
            ';' | '!' | '?' | '\n' => true,
            '.' => chars.get(index + 1).is_none_or(|next| next.is_whitespace()),
            _ => false,
        };
        if boundary {
            segments.push(chars[start..index].iter().collect::<String>());
            start = index + 1;
        }
    }
    segments.push(chars[start..].iter().collect());
    let mut result = Vec::new();
    for segment in segments {
        let mut clause = Vec::new();
        for token in tokens(&segment) {
            if CLAUSE_WORDS.contains(&token.as_str()) && !clause.is_empty() {
                result.push(std::mem::take(&mut clause));
            }
            clause.push(token);
        }
        if !clause.is_empty() {
            result.push(clause);
        }
    }
    result
}

fn states_resolution(clause: &[String]) -> bool {
    clause
        .iter()
        .any(|token| RESOLVED_WORDS.contains(&token.as_str()))
        || clause.windows(2).any(|pair| {
            RESOLVED_PHRASES
                .iter()
                .any(|phrase| pair[0] == phrase[0] && pair[1] == phrase[1])
        })
}

fn candidate_bag(candidate: &Candidate) -> Bag {
    let mut texts = vec![candidate.title.as_str(), candidate.summary.as_str()];
    for linked in &candidate.linked_reports {
        texts.push(&linked.title);
        texts.push(&linked.description);
    }
    bag(&texts)
}

fn score<'a>(
    candidate: &'a Candidate,
    report: &Bag,
    report_norm: f64,
    weights: &Weights,
    config: &Config,
) -> Scored<'a> {
    let mut evidence = Vec::new();
    let mut field = |record, id: &str, field, bag: &Bag| {
        if !report.is_disjoint(bag) {
            evidence.push(Evidence {
                record,
                id: id.to_owned(),
                field,
            });
        }
    };

    let title = bag(&[&candidate.title]);
    let summary = bag(&[&candidate.summary]);
    field(Record::Problem, &candidate.id, Field::Title, &title);
    field(Record::Problem, &candidate.id, Field::Summary, &summary);
    let mut linked_overlap: f64 = 0.0;
    for linked in &candidate.linked_reports {
        let linked_title = bag(&[&linked.title]);
        let linked_description = bag(&[&linked.description]);
        field(
            Record::LinkedReport,
            &linked.id,
            Field::Title,
            &linked_title,
        );
        field(
            Record::LinkedReport,
            &linked.id,
            Field::Description,
            &linked_description,
        );
        let combined: Bag = linked_title.union(&linked_description).cloned().collect();
        linked_overlap = linked_overlap.max(weights.overlap(report, report_norm, &combined));
    }

    let features = BTreeMap::from([
        ("linked_overlap", linked_overlap),
        (
            "summary_overlap",
            weights.overlap(report, report_norm, &summary),
        ),
        (
            "title_overlap",
            weights.overlap(report, report_norm, &title),
        ),
    ]);
    let score = features
        .iter()
        .map(|(name, value)| config.weight(name) * value)
        .sum::<f64>();
    assert!(score.is_finite() && score >= 0.0, "score out of range");
    assert!(
        score == 0.0 || !evidence.is_empty(),
        "score without evidence"
    );
    Scored {
        candidate,
        score,
        features,
        evidence,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn config(algorithm: &str) -> Config {
        Config::parse(&format!(
            r#"{{"algorithm_version":"{algorithm}","config_version":"t","max_linked_reports":5,
            "weights":{{"linked_overlap":0.5,"summary_overlap":0.7,"title_overlap":1}},
            "min_score":0.2,"min_margin":0.05}}"#
        ))
        .expect("test config is valid")
    }

    fn request(title: &str, description: &str) -> Request {
        let candidate = |n: u32, title: &str, summary: &str| {
            serde_json::json!({"id": format!("00000000-0000-4000-8000-{n:012}"), "version": 1,
                "title": title, "summary": summary, "linked_reports": []})
        };
        serde_json::from_value(serde_json::json!({
            "contract_version": "1", "algorithm_version": "lexical-2", "config_version": "t",
            "report": {"id": "00000000-0000-4000-8000-000000000099", "version": 1,
                "title": title, "description": description},
            "candidates": [
                candidate(1, "CSV export times out", "Large invoice CSV exports never finish."),
                candidate(2, "Logo missing from PDF", "Uploaded SVG logos vanish from PDFs."),
            ],
        }))
        .expect("test request is valid")
    }

    fn words(clause: &[String]) -> String {
        clause.join(" ")
    }

    #[test]
    fn clauses_split_on_punctuation_and_clause_words_but_keep_versions() {
        let split: Vec<String> = clauses("Export is fine now, but v2.4.1 fails. Next: retry")
            .iter()
            .map(|clause| words(clause))
            .collect();
        assert_eq!(
            split,
            ["export is fine now", "but v2.4.1 fails", "next retry"]
        );
    }

    #[test]
    fn resolution_words_and_phrases_mark_a_clause() {
        let marked = |text: &str| states_resolution(&tokens(text));
        assert!(marked("CSV exports work fine now"));
        assert!(marked("logos no longer disappear"));
        assert!(marked("it isn't timing out anymore"));
        assert!(!marked("the CSV export never finishes"));
        assert!(!marked("no logo, longer wait"));
    }

    #[test]
    fn lexical_2_ignores_a_problem_the_report_calls_resolved() {
        let report = request(
            "CSV export is fine now",
            "Large invoice CSV exports no longer time out. The email subject resets.",
        );
        assert!(matches!(
            rank(&report, &config("lexical-1")),
            Outcome::Ranked { .. }
        ));
        assert_eq!(
            rank(&report, &config("lexical-2")),
            Outcome::Abstain {
                abstain_reason: AbstainReason::BelowThreshold
            }
        );
    }

    #[test]
    fn lexical_2_still_matches_a_plain_report() {
        let report = request(
            "CSV export times out",
            "Large invoice CSV exports never finish.",
        );
        let Outcome::Ranked { suggestions } = rank(&report, &config("lexical-2")) else {
            panic!("expected a ranking");
        };
        assert_eq!(
            suggestions[0].problem_id,
            "00000000-0000-4000-8000-000000000001"
        );
    }
}
