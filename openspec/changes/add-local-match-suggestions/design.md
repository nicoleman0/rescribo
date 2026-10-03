# Design

## Context

[ADR 0003](../../../docs/adr/0003-local-rust-matcher.md) is the design: Django owns retrieval, persistence, and workflow; a Rust subprocess ranks only the candidates it is given. It also fixes the JSON contract, limits, crate layout, CI, and the five implementation slices. This document does not restate it.

## Goals / Non-Goals

**Goals:** deliver ADR 0003 slices 1 to 5 as issues #22 (slice 1), #23 (slices 2 to 4), #24 (held-out evaluation), and #21 (slice 5).

**Non-Goals:** embeddings, hosted models, generative drafting, and automatic linking.

## Decisions

- One change covers all four issues because they share two capabilities. Each issue's PR completes its task group; the change is archived after #21 merges.
- The ten-candidate and 64 KiB limits are starting values. #22 confirms them against fixtures before the crate is built.

## Risks / Trade-offs

- [Lexical ranking misses paraphrases and negation] → Evidence is shown so a person judges; gates may keep suggestions hidden.
- [Evaluation on synthetic data may not match real language] → Report it as a limitation; keep synthetic and any redacted real data separate.

## Open Questions

- Precision/coverage gates and minimum sample size: the product owner sets these in #22, before held-out results are opened.
- Deployment OS/CPU targets and Rust MSRV: chosen with the deployment base image.
