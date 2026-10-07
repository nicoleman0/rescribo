# marketing-site Specification

## Purpose
Explain Rescribo's customer-feedback workflow publicly and direct visitors to the self-hosted project.

## Requirements

### Requirement: Public workflow explanation
The site SHALL explain Capture, Connect, and Follow up with copy sourced from the README and OpenSpec project context. It SHALL describe the intended shipped workflow in present tense rather than report development status. It SHALL describe Rescribo as self-hosted and link to its project repository. It MUST NOT offer a hosted service, application sign-in, pricing, billing, public signup, or unsupported adoption claims.

#### Scenario: Visitor reads the page
- **WHEN** a visitor opens the site
- **THEN** the page describes Slack or manual capture, human-approved GitHub issue publication, and employee follow-up without implying autonomous action or customer accounts

#### Scenario: Self-hosted adoption
- **WHEN** a visitor reads the About section
- **THEN** it describes Rescribo as self-hosted and provides a project repository link without an application Sign in link

#### Scenario: JavaScript is disabled
- **WHEN** a visitor opens the site without JavaScript
- **THEN** the product explanation and project repository link remain readable and usable

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

### Requirement: Optional canonical URL
The site MUST build without a configured marketing URL. Optional canonical metadata MUST use a supplied HTTPS URL. Invalid supplied URLs MUST fail the build with a clear configuration error.

#### Scenario: Configured canonical URL
- **WHEN** the site is built with a marketing URL
- **THEN** its static HTML contains canonical metadata for the supplied HTTPS URL

#### Scenario: No marketing URL
- **WHEN** the site is built without a marketing URL
- **THEN** the public page builds successfully and omits canonical metadata without displaying configuration messages

#### Scenario: Invalid supplied canonical URL
- **WHEN** a build receives a malformed or non-HTTPS canonical URL
- **THEN** the build fails with a clear error identifying the invalid configuration

### Requirement: Scroll-driven narrative
The site SHALL animate the 3D composition and workflow presentation in response to native page scrolling. Scroll progress MUST be reversible and MUST NOT trap scrolling or conceal essential content. Pause and reduced-motion preferences MUST also stop scroll-driven visual changes. Navigation and scrolling MUST remain usable without graphics or JavaScript.

#### Scenario: Scroll forward and backward
- **WHEN** a visitor scrolls down through the hero and workflow and then returns upward
- **THEN** the composition changes with scroll progress and returns toward its earlier pose while workflow content remains readable

#### Scenario: Motion is disabled
- **WHEN** motion is paused or reduced motion is requested and the visitor scrolls
- **THEN** decorative scroll animation stops while the visitor can still read and navigate all sections
