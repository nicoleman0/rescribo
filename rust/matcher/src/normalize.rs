//! Tokenizer. Rules: backend/matching/README.md; fixtures: backend/matching/normalization.json.

/// Splits text into lowercase tokens, keeping duplicates and order.
pub fn tokens(text: &str) -> Vec<String> {
    // Lowercase the whole string first so context-dependent mappings (final sigma) apply.
    let chars: Vec<char> = text.to_lowercase().chars().collect();
    let mut tokens = Vec::new();
    let mut current = String::new();
    for (index, &character) in chars.iter().enumerate() {
        if character.is_alphanumeric() {
            current.push(character);
            continue;
        }
        let previous = index.checked_sub(1).map(|before| chars[before]);
        let next = chars.get(index + 1).copied();
        match character {
            '\'' | '\u{2019}'
                if previous.is_some_and(char::is_alphanumeric)
                    && next.is_some_and(char::is_alphanumeric) => {}
            '.' if previous.is_some_and(|c| c.is_ascii_digit())
                && next.is_some_and(|c| c.is_ascii_digit()) =>
            {
                current.push('.');
            }
            _ => {
                if !current.is_empty() {
                    tokens.push(std::mem::take(&mut current));
                }
            }
        }
    }
    if !current.is_empty() {
        tokens.push(current);
    }
    tokens
}
