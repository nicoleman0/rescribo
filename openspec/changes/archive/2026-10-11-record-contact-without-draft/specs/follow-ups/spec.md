## ADDED Requirements

### Requirement: Contact without a message
A member SHALL be able to record a customer contact outcome on a follow-up that has no message draft. The follow-up detail MUST show the customer contact section for every delivery state, including when no message was prepared. Recording an outcome MUST NOT create, send, or cancel a message.

#### Scenario: Contact recorded before any message
- **WHEN** a member records "Customer contacted" on a follow-up with no prepared message
- **THEN** customer contact is `contacted`, delivery still shows "Not prepared", and the follow-up is listed under awaiting confirmation

#### Scenario: Completed without a message
- **WHEN** a member records `confirmed` on a contacted follow-up with no prepared message
- **THEN** the follow-up is listed under completed and no message exists

#### Scenario: Unsent draft is kept
- **WHEN** a member records an outcome on a follow-up whose message is still a draft
- **THEN** the draft is unchanged and can still be edited and sent

#### Scenario: Message prepared after contact
- **WHEN** a member opens a follow-up whose outcome is recorded and whose message was never prepared
- **THEN** the message section says customer contact is already recorded and still offers to prepare a message
