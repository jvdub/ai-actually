# Weekly operation

Run `python3 newsroom.py draft` (uses your signed-in Codex CLI with live web search) or ask the agent to use `$draft-roundup`. No separate model API key is required by this project. Codex account usage and availability still apply.

Run `python3 newsroom.py review`. Edit the issue, inspect sources, save, and approve the exact text. Changes after approval require another approval.

Publish the reviewed issue with `python3 newsroom.py publish ISSUE --push`. The command builds the static site, stages only publication content and generated output, commits, and pushes to the configured Amplify branch. It does not send email. Build automation never drafts or sends emails.

Once the live issue is deployed, `python3 newsroom.py kit ISSUE` creates or updates one unsent Kit draft using the same issue content. Review and send in Kit. This intentionally leaves the audience and send-time decision in Kit; no recipient list is guessed. A local journal prevents duplicate drafts on ordinary retries and stops ambiguous creation attempts for reconciliation.

Setup once: set site_url and contact_email in publication.json, connect the Git repository and main branch in Amplify, set KIT_API_KEY in .env, and select an existing Kit email template and sender in publication.json. Keep Kit's unsubscribe/address footer in that template. Configure Kit signup_url separately when ready.

The local review server binds to localhost and is not part of the deployed site. Drafts, research notes, API keys and email output are excluded from the public build. Keep .newsroom/ backed up if you rely on its Kit draft IDs; do not run Kit sync from multiple machines at once. If its state is lost, reconcile the existing broadcast before creating another.


The default date is the most recent configured weekday, including today; dates with an incomplete reporting window are rejected. A Tuesday 09:00 America/Denver thread automation now owns weekly drafting. The commands also remain available on demand. Change the thread automation schedule as well as publication_day if changing the weekday. To change the weekday, update publication_day once.

A feature linked by an issue must be reviewed and published first. The initial repository setup must be committed before weekly publishing is enabled. Subsequent application/settings changes also need their own commit.

Kit content is generated from the saved issue. Make editorial edits in the newsroom before syncing; syncing again can replace edits made directly in an unsent Kit draft. Known API rejections can be retried after fixing configuration. An uncertain creation requires reconciliation: use python3 newsroom.py kit-adopt ISSUE BROADCAST_ID after finding the matching AI-Actually marker in Kit.
