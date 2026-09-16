# AI, Actually

The normal workflow now happens in this conversation. Every Tuesday at 9 a.m. Mountain time, the agent prepares the previous week's positive AI news plus one AI fact and one data-center fact, reviews the evidence and presents the draft. Give feedback here; the agent revises it. Explicit approval of the final revision allows release preparation. Website and newsletter delivery integrations are deferred.

The local newsroom remains available for direct edits and reader previews. Source review and feedback must be current before approval. An approved release package contains the matching website, email and content snapshot with file hashes; it does not publish or send.

See [the editorial pipeline](editorial/pipeline.md) for agent operation and evidence records. The remaining setup instructions below apply when delivery integrations are connected.

A weekly publication with a local newsroom for research, editing and publishing. Python 3.11+; no Python packages required.

## Weekly routine
1. Run `python3 newsroom.py review` and open http://localhost:4317.
2. Click **Research a new draft**. Review sources, edit the fields, save and approve.
3. Click **Publish website** to commit and push the edition to your Amplify branch.
4. After deployment, click **Prepare Kit draft**, then review and send in Kit.

Website and email use the same content. Drafts and private research notes stay out of the website. Edits clear approval. Kit retries reuse the existing unsent draft.

The workspace includes a four-story draft and an expanded data-center explainer. Publish the reviewed explainer first, or remove its link from the issue. The original pilot stays published locally until you approve a replacement.

## One-time setup
- Set your HTTPS `site_url`, `contact_email`, chosen `publication_day`, and optional Kit `signup_url` in `publication.json`.
- Connect this repository and configured branch to AWS Amplify. `amplify.yml` builds `dist/`; remove any SPA catch-all rewrite because this is a multi-page website.
- Commit the initial application files before using the weekly publishing button. That button commits only the selected content file and generated website.
- Copy `.env.example` to `.env`, add `KIT_API_KEY`, and set your verified Kit sender and existing email template ID in `publication.json`. Keep Kit's address and unsubscribe footer in that template.
- Sign in to the Codex CLI on this machine. Drafting uses that account's usage. The editor runs locally, not on Amplify.

Default issue date: the most recent chosen weekday, including today. It covers the seven preceding complete days. You can select another past date. Research never overwrites existing editions.

## Useful commands
- `python3 newsroom.py draft`: research without opening the editor.
- `python3 newsroom.py draft --date YYYY-MM-DD --prompt`: export the prompt for another agent.
- `python3 newsroom.py check`: validate content.
- `python3 newsroom.py build`: rebuild locally; add `--production` to require public settings.
- `python3 -m unittest discover -s tests -v`: run workflow checks.

Content lives in `content/issues/` and `content/features/`; styling lives in `assets/`. `dist/` is generated; do not edit it directly. See [publishing details](editorial/publishing.md) for credentials and Kit recovery. AWS deployment and real Kit operations require your account configuration.

## Reader previews and fact cards
Use **View published website** for the locally built public site. Use **Open reader preview** beside the preview tabs to see the selected saved draft at full width, with the final reader layout, without publishing it. Select Email to open the email version; Kit supplies its final template and footer.

New editions include one AI fact and one data-center fact, with primary sources, scope and context. Edit these in the newsroom. Historical editions keep their original content. Automated checks require the source fields but cannot establish truth; review the evidence before approval.
