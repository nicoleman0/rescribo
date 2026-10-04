//! Algorithm `lexical-1`: IDF-weighted token-set overlap between the report and each
//! candidate field. Ordered collections keep float sums, and so scores, repeatable.

use std::collections::{BTreeMap, BTreeSet};

use crate::config::Config;
use crate::contract::{
    AbstainReason, Candidate, Evidence, Field, MAX_SUGGESTIONS, Outcome, Record, Request,
    Suggestion,
};
use crate::normalize::tokens;

pub const ALGORITHM_VERSION: &str = "lexical-1";
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
    let report = bag(&[&request.report.title, &request.report.description]);
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
