//! Versioned ranking configs, embedded at build time from backend/matching/configs/.
//! Python reads the same files to know which versions this build supports.

use std::collections::BTreeMap;
use std::sync::OnceLock;

use serde::Deserialize;

use crate::rank::{ALGORITHM_VERSION, FEATURES};

/// Every file in backend/matching/configs/. A test fails if one is missing here.
pub const SOURCES: &[&str] = &[include_str!(
    "../../../backend/matching/configs/lexical-1.0.json"
)];

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Config {
    pub algorithm_version: String,
    pub config_version: String,
    /// Retrieval sends at most this many linked reports per candidate; more is rejected.
    pub max_linked_reports: usize,
    pub weights: BTreeMap<String, f64>,
    /// The top candidate must score at least this, or the matcher abstains.
    pub min_score: f64,
    /// The top candidate must lead the next one by at least this, or the matcher abstains.
    pub min_margin: f64,
}

impl Config {
    pub fn parse(source: &str) -> Result<Config, String> {
        let config: Config = serde_json::from_str(source).map_err(|error| error.to_string())?;
        if config.algorithm_version != ALGORITHM_VERSION {
            return Err(format!(
                "{}: unknown algorithm {}",
                config.config_version, config.algorithm_version
            ));
        }
        if !config.weights.keys().map(String::as_str).eq(FEATURES) {
            return Err(format!(
                "{}: weights must name exactly {FEATURES:?}",
                config.config_version
            ));
        }
        let numbers = config
            .weights
            .values()
            .chain([&config.min_score, &config.min_margin]);
        if !numbers
            .into_iter()
            .all(|value| value.is_finite() && *value >= 0.0)
        {
            return Err(format!(
                "{}: weights and thresholds must be finite and non-negative",
                config.config_version
            ));
        }
        Ok(config)
    }

    pub fn weight(&self, feature: &str) -> f64 {
        self.weights[feature]
    }
}

fn all() -> &'static [Config] {
    static CONFIGS: OnceLock<Vec<Config>> = OnceLock::new();
    CONFIGS.get_or_init(|| {
        // Embedded build data; a bad file is a build defect, covered by tests.
        SOURCES
            .iter()
            .map(|source| Config::parse(source).expect("embedded config is valid"))
            .collect()
    })
}

pub fn find(algorithm_version: &str, config_version: &str) -> Option<&'static Config> {
    all().iter().find(|config| {
        config.algorithm_version == algorithm_version && config.config_version == config_version
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embedded_configs_parse_and_are_unique() {
        let versions: Vec<&str> = all().iter().map(|c| c.config_version.as_str()).collect();
        let mut unique = versions.clone();
        unique.sort();
        unique.dedup();
        assert_eq!(versions.len(), unique.len());
    }

    #[test]
    fn rejects_wrong_features_and_negative_numbers() {
        let base = r#"{"algorithm_version":"lexical-1","config_version":"x","max_linked_reports":1,
            "weights":{"linked_overlap":1,"summary_overlap":1,"title_overlap":1},
            "min_score":0.1,"min_margin":0.1}"#;
        assert!(Config::parse(base).is_ok());
        assert!(Config::parse(&base.replace("linked_overlap", "other")).is_err());
        assert!(Config::parse(&base.replace("\"min_score\":0.1", "\"min_score\":-0.1")).is_err());
        assert!(Config::parse(&base.replace("lexical-1\"", "lexical-9\"")).is_err());
    }
}
