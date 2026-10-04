//! Evaluation tooling, not shipped: ranks JSON Lines requests on stdin with a config file
//! that need not be embedded, so practice tuning can try weights without new config files.
//! Usage: rank_with_config <config.json> < requests.jsonl > outcomes.jsonl

use std::io::{self, BufRead, Write};

use matcher::config::Config;
use matcher::contract::Request;
use matcher::rank::rank;

fn main() {
    let path = std::env::args()
        .nth(1)
        .expect("usage: rank_with_config <config.json>");
    let source = std::fs::read_to_string(&path).expect("config file is readable");
    let config = Config::parse(&source).expect("config is valid");
    let mut out = io::BufWriter::new(io::stdout().lock());
    for line in io::stdin().lock().lines() {
        let line = line.expect("stdin is readable");
        let request: Request = serde_json::from_str(&line).expect("request is valid JSON");
        serde_json::to_writer(&mut out, &rank(&request, &config)).expect("stdout is writable");
        out.write_all(b"\n").expect("stdout is writable");
    }
}
