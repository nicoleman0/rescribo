Invent a name and the problem list for this fictional product: $product

A problem is one known defect or gap that engineering tracks. Customer-facing staff (sales, support, account managers) link incoming customer reports to problems.

Write $listed_count listed problems and $unlisted_count unlisted problems.

Listed problems:
- Each has a short title and a summary of one to four sentences that states the symptom and, where known, the cause or affected area.
- Arrange $pair_count pairs of confusable problems. The two problems in a pair share visible symptoms and vocabulary but have different causes, for example two different reasons an export fails. Set `confusable_with` on both to the other's key. Every other problem has `confusable_with: null`.
- Mention a product version or release in some summaries, where the problem started or was partly fixed.
- Give each problem zero to three linked reports: earlier customer reports already attached to it. Write them as staff paste them from Slack or a support ticket. Vary their length from one line to about 200 words.

Unlisted problems:
- Plausible problems in the same product, clearly distinct from every listed problem. They are used to write reports that must match nothing.

Reply in this shape:
{"product_name": "...",
 "problems": [{"key": "P1", "title": "...", "summary": "...", "confusable_with": "P2", "linked_reports": [{"title": "...", "description": "..."}]}],
 "unlisted": [{"title": "...", "summary": "..."}]}
