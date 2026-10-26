# Spec Delta

## ADDED Requirements

### Requirement: Problem detail touch targets on phones
At phone width, every standalone link on problem detail SHALL keep a 44px touch target. A standalone link is one that is not part of a sentence: a linked report title, the activity entry that folds several report links and the report links it reveals, the GitHub issue link, the release and fix evidence links, and the links offered after creating an issue or when GitHub is not connected. A link inside running text MAY stay at text height. Desktop width MUST keep its compact layout.

#### Scenario: Standalone links at phone width
- **WHEN** a member opens a problem with a confirmed fix, a linked release, a linked GitHub issue, and several reports linked together, at phone width
- **THEN** each linked report title, the folded activity entry, the release link, and the GitHub issue link are at least 44px tall and the page does not scroll horizontally

#### Scenario: Folded report links
- **WHEN** a member opens the folded "linked N reports" activity entry at phone width
- **THEN** each report link it reveals is at least 44px tall

#### Scenario: Links inside a sentence
- **WHEN** an activity entry reads "moved" a report "here from" another problem at phone width
- **THEN** the report and problem links stay at text height inside the sentence

#### Scenario: Desktop width
- **WHEN** a member opens the same problem at desktop width
- **THEN** the links keep their text height
