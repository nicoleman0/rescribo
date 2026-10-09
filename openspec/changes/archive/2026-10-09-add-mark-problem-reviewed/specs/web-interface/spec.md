# Spec Delta

## ADDED Requirements

### Requirement: Mark reviewed from the next step
The next-step banner of a problem that needs review, including a "Not planned" banner, SHALL offer a Mark reviewed action. After it succeeds, the banner MUST show the next step for the problem's state without a page reload, and a failed attempt MUST explain what went wrong and keep the banner. Problem activity SHALL read "marked the problem reviewed" for this action, and entries that set the flag MUST still read "flagged the problem for review".

#### Scenario: Mark reviewed
- **WHEN** a member chooses Mark reviewed on the banner of a fixed problem that needs review
- **THEN** the banner changes to the success tone for the available fix, the Needs review badge is gone, and activity shows the member marked the problem reviewed

#### Scenario: Flagged problem that is not planned
- **WHEN** a problem in `not_planned` is flagged for review
- **THEN** the "Not planned" banner keeps its heading and offers Mark reviewed, and after it succeeds the Needs review badge is gone

#### Scenario: Someone else already reviewed it
- **WHEN** a member chooses Mark reviewed after another member already marked the problem reviewed
- **THEN** an error explains the problem changed, and the page shows the current problem without the review flag

#### Scenario: Older flag entries
- **WHEN** a problem's activity holds an entry from before this change that set the review flag
- **THEN** that entry still reads "flagged the problem for review"
