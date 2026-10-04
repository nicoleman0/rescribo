You check labels in a synthetic test set for a tool that matches customer feedback reports to known product problems. Each test case is a report and the answer it is labelled with: one listed problem, or no match. Decide whether that label is right.

The label is right when a careful support engineer who knows the product would link the report to the expected problem and to no other listed problem, or, for "no match", to none of the listed problems. Reports may be paraphrased, vague, or mention misleading versions; judge what they describe, not their wording.

Reply with one JSON object and nothing else: {"right": true or false, "reason": "one sentence"}

Listed problems:
$problems

Test case:
$case
