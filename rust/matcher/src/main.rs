//! Reads one request on stdin and writes one JSON document on stdout.
//! Exit 0 for a ranking or abstention, 2 for a rejected request, 1 for an I/O failure.

use std::io::{self, Read, Write};
use std::process::ExitCode;

use matcher::contract::MAX_REQUEST_BYTES;

fn main() -> ExitCode {
    let mut input = Vec::new();
    // One byte past the limit is enough to reject an oversized request.
    let limit = MAX_REQUEST_BYTES as u64 + 1;
    if io::stdin().take(limit).read_to_end(&mut input).is_err() {
        eprintln!("matcher: could not read stdin");
        return ExitCode::from(1);
    }
    let (document, code) = match matcher::handle(&input) {
        Ok(response) => (serde_json::to_vec(&response), 0),
        Err(rejection) => {
            eprintln!("matcher: {}", rejection.detail);
            (serde_json::to_vec(&rejection.document()), 2)
        }
    };
    let written = document
        .map_err(io::Error::other)
        .and_then(|bytes| io::stdout().lock().write_all(&bytes));
    if written.is_err() {
        eprintln!("matcher: could not write stdout");
        return ExitCode::from(1);
    }
    ExitCode::from(code)
}
