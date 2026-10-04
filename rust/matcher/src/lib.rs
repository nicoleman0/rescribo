//! Ranks a supplied candidate set for one report. No I/O beyond the caller's bytes.

pub mod config;
pub mod contract;
pub mod normalize;
pub mod rank;

use contract::{CONTRACT_VERSION, Rejection, Response};

/// Validates request bytes and ranks them.
pub fn handle(input: &[u8]) -> Result<Response, Rejection> {
    let (request, config) = contract::parse_request(input)?;
    let outcome = rank::rank(&request, config);
    Ok(Response {
        contract_version: CONTRACT_VERSION,
        algorithm_version: request.algorithm_version,
        config_version: request.config_version,
        outcome,
    })
}
