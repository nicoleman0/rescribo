# web-interface Specification

## Purpose

Defines the product screens and the shared behaviour every screen must have: states, accessibility, and draft safety.

## Requirements

### Requirement: Product screens
The web app SHALL provide sign-in and invite acceptance, inbox, problems list, problem detail, follow-ups, and settings screens.

#### Scenario: Problem detail
- **WHEN** a member opens a problem
- **THEN** it shows the editable summary, linked reports with provenance, the GitHub link or create flow, fix review, activity, and report reassignment

#### Scenario: Follow-ups queue
- **WHEN** a member opens follow-ups
- **THEN** they are grouped as needs approval, delivery failed or uncertain, awaiting contact, awaiting confirmation, and completed

### Requirement: Asynchronous states
Every asynchronous screen and section SHALL have loading, empty, error, and retry states.

#### Scenario: Load failure
- **WHEN** a list request fails
- **THEN** the section shows an error with a retry action

### Requirement: Read retries never write
A retry on a failed read SHALL refetch only that query. It MUST NOT publish an issue, confirm a fix, delete data, or send a message. Writes are retried only by an explicit user action.

#### Scenario: Retry after error
- **WHEN** a member presses retry on a failed problem detail load
- **THEN** only the read requests repeat

### Requirement: Accessible forms
Forms SHALL have labels, full keyboard operation, visible focus, and inline errors.

#### Scenario: Keyboard only
- **WHEN** a member completes manual capture using only the keyboard
- **THEN** every field and action is reachable and focus is always visible

### Requirement: Draft preservation
Unsaved input SHALL survive recoverable failures, including conflicts and network errors.

#### Scenario: Conflict on save
- **WHEN** a save returns a conflict
- **THEN** the member's edits remain on screen alongside the current data

### Requirement: Responsive layout
The layout SHALL be desktop-first and remain usable at narrow mobile widths without horizontal page scrolling.

#### Scenario: Phone width
- **WHEN** the inbox is opened at phone width
- **THEN** navigation and report actions are usable without horizontal scrolling

### Requirement: Bounded polling
Background state SHALL refresh with bounded polling. Websockets are not required.

#### Scenario: Delivery in progress
- **WHEN** a follow-up is queued
- **THEN** the screen polls until the delivery reaches a final state or the polling limit
