# Agent-owned weekly publication

The user delegates research, drafting, evidence review, presentation and revisions to the agent. The goal is to win over AI skeptics through real positive developments and accurate context. Do not inflate the upside, dismiss legitimate concerns or treat weak announcements as demonstrated benefit.

## Weekly run
The thread automation runs Tuesday at 09:00 America/Denver. Use the scheduled issue date and seven preceding complete calendar days. A late run uses the latest scheduled date; report that it is late rather than silently shifting the window. Never overwrite an existing issue, feedback or pending edition. Check pipeline.py status and the recorded prepared revision and conversation history first.

Read editorial/brief.md. Choose the research method freely: research directly with available tools, or use newsroom.py draft. Prefer primary evidence and seek counterevidence; verify consequential claims against underlying research rather than press-release wording alone. Produce the issue and two facts. Review the complete draft against its sources in a separate editorial pass, including dates, actual AI contribution, benefit, limits, quantitative scope and possible repeats. Remove unsupported claims. If only a few strong items qualify, use fewer. Sources and source-check dates must be real.

## Evidence record
Save editorial/reviews/ISSUE.json tied to publication.fingerprint(issue):
- revision: full content fingerprint
- reviewer: honest identity, e.g. AI editorial review (never invent independent human review)
- checked_at: actual ISO timestamp
- verdict: ready or needs_revision
- unresolved: array of remaining material concerns
- checks: one entry for every story:0, story:1, etc. and fact:0, fact:1; a feature uses feature.
Each check has verdict (supported or needs_revision), basis (specific assessment of what the evidence supports and the limits), and sources_checked (the direct URLs actually opened and assessed). Refer to source passages/sections in basis; do not store copyrighted articles. A ready record means assessed support, not certainty or independent verification. Mechanical validation checks completeness and revision alignment, not truth.

Run python3 pipeline.py check-review ISSUE. Approval requires a current ready report covering every item and no unresolved feedback. Do not create a ready record just to satisfy the check.

## Present and revise
Run python3 pipeline.py present ISSUE to create a private Markdown review packet and immutable content snapshot. Present the actual draft in this conversation, with source links, both facts, any material concern and a reader preview when the local server is available. The generated packet is ready to present; it does not prove the user saw it. Check the conversation before deciding a prepared revision has already been presented.

Record user feedback using pipeline.py feedback ISSUE --file FILE. Preserve their wording, revise the draft, recheck changed claims, then record how it was addressed with resolve-feedback. Present the revised issue and briefly explain material changes. Feedback and edits invalidate approval. Do not construe praise, silence, or approval of the pipeline as approval of an edition. A user approval applies to the clearly identified final revision and any linked new explainer.

## Approval and delivery
After explicit user approval, use newsroom.py approve ISSUE (and the approved new feature, if any), then pipeline.py prepare-release ISSUE. This creates a snapshot of website files, email HTML/text and a manifest with hashes. The source issue remains reviewed; packaging does not publish or send.

AWS and Kit delivery are deferred at the user's request. Do not add credentials, create a send schedule, send mail, or claim delivery until those integrations are configured. Future integration must publish the approved snapshot, verify the live issue and links, and then send exactly one newsletter to the configured audience. Persist provider IDs and actual delivery receipts; reconcile uncertain results before retries. Existing Kit functionality creates an unsent draft only. Stop and report partial success if either delivery fails. Any change to approved content requires renewed approval.

## Local operation
The same conversation handles feedback and approvals between scheduled runs. Scheduling needs the Codex app/local project to be available; this is not an always-on AWS service. Localhost reader links work while newsroom.py review is running. The review packet is also a saved Markdown file, so the draft survives preview restarts.

This creates a delivery risk: a Tuesday run can be missed when the computer is off, asleep, disconnected, or Codex is not running. Until an always-on runner is added, detect the most recent scheduled issue when the thread resumes, prepare any missing draft, and clearly label it as a late catch-up. Future mitigation should move research and draft generation to an always-on environment while preserving the same approval gate and never auto-publishing a missed edition.
