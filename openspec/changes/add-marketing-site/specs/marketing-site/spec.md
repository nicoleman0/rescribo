# Marketing site

## Purpose

Explain Rescribo's existing customer-feedback workflow publicly and let existing members reach the application without loading its authenticated bundle.

## ADDED Requirements

### Requirement: Public workflow explanation
The site SHALL explain Capture, Connect, and Follow up with copy sourced from the README and OpenSpec project context. It SHALL describe the intended shipped workflow in present tense rather than report development status. It MUST NOT offer pricing, billing, public signup, or unsupported adoption claims.

#### Scenario: Visitor reads the page
- **WHEN** a visitor opens the site
- **THEN** the page describes Slack or manual capture, human-approved GitHub issue publication, and employee follow-up without implying autonomous action or customer accounts

#### Scenario: JavaScript is disabled
- **WHEN** a visitor opens the site without JavaScript
- **THEN** the product explanation and configured sign-in link remain readable and usable

### Requirement: Accessible visual enhancement
The site SHALL provide an interactive 3D visual without making it necessary for reading or navigation. The site MUST retain a static visual when WebGL is unavailable, initialization fails, or the graphics context is lost.

#### Scenario: Pointer interaction
- **WHEN** a visitor moves their pointer over the 3D composition
- **THEN** the composition responds without capturing page scrolling or blocking links

#### Scenario: Graphics unavailable
- **WHEN** WebGL initialization fails or the graphics context is lost
- **THEN** the static visual remains visible and the page content and navigation remain usable

### Requirement: Motion control
The site SHALL respect reduced-motion preferences, provide a keyboard-accessible pause control for continuous motion, and suspend animation when the page or visual is not visible.

#### Scenario: Reduced motion
- **WHEN** reduced motion is requested initially or while the page is open
- **THEN** continuous animation and pointer-driven motion stop and the composition remains static

#### Scenario: Pause and resume
- **WHEN** a visitor pauses motion
- **THEN** continuous and pointer-driven motion stop until the visitor resumes, subject to reduced-motion preferences

### Requirement: Responsive accessible content
The site SHALL support keyboard navigation, visible focus, semantic landmarks, sufficient contrast, and layouts from 320px phone widths through desktop. Content MUST remain usable at 200% zoom without horizontal page scrolling.

#### Scenario: Narrow viewport
- **WHEN** the site is opened at 320px width or 200% zoom
- **THEN** content and controls remain readable, reachable, and contained within the viewport

### Requirement: Optional application destination
The site MUST remain public without an application URL. When configured, the site SHALL provide a Sign in link to the supplied HTTPS destination. When no destination is configured, it MUST omit that link. Optional canonical metadata MUST use a supplied HTTPS URL. Invalid supplied URLs MUST fail the build with a clear configuration error.

#### Scenario: Configured destination
- **WHEN** an existing member selects Sign in on a configured site
- **THEN** the browser opens the supplied application sign-in URL

#### Scenario: No application destination
- **WHEN** the site is built without an application URL
- **THEN** the public page builds successfully and omits the Sign in link without displaying configuration messages

#### Scenario: Invalid supplied destination
- **WHEN** a build receives a malformed or non-HTTPS application or canonical URL
- **THEN** the build fails with a clear error identifying the invalid configuration
