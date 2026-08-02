# Gravity OS guided Team demo

This runbook is for a 10–15 minute product demonstration to artist managers,
label owners, and small creative teams. It tells one release story: work enters a
shared workspace, the right people act on it, managers retain approval control,
and the activity history makes ownership visible.

Do not treat this document as evidence that production deployment has been
verified. Complete the preflight against the environment being demonstrated.

## Demo outcome

By the end of the walkthrough, the audience should have seen:

- one shared release plan instead of coordination across chats and spreadsheets;
- clear owner, admin, member, and viewer boundaries;
- task assignment, comments, mentions, and notifications in context;
- a member submitting work for review and a manager approving or rejecting it;
- the review note, reviewer, date, and related activity history; and
- a manager-facing queue of work that needs a decision.

## Environment preflight

Complete this checklist before inviting an audience. Record the deployed commit
SHA in the demo notes; do not assume a push completed both deployments.

- Confirm the product repository and production branch are
  `OlaMarcus09/GravityOS_app` and `main`, not the legacy `origin` repository.
- Confirm migrations through `0017_team_workflow_integrity.sql` are applied to
  the Supabase project used by the demo.
- In Render, confirm the API is built from the intended commit and `GET /health`
  returns HTTP 200 with `environment` set to `production`.
- Confirm Render has the Supabase variables, the exact production web origin in
  `CORS_ORIGINS`, the public web origin in `WEB_APP_URL`, and the verified admin
  account in `SUPER_ADMIN_EMAILS`. `WEB_APP_URL` is not currently declared in
  `render.yaml`, so verify the manually managed value explicitly.
- In Vercel, confirm the project root is `apps/web`, the production branch is
  `main`, and `NEXT_PUBLIC_API_URL` points to the Render origin. Also confirm the
  public Supabase URL and anon key are set for that same Supabase project.
- Confirm the production `/auth/invite` URL is allowlisted in Supabase Auth.
- Sign in, load Tasks, Team, Notifications, and Activity, and check the browser
  console/network panel for API, authentication, or CORS errors.
- Test the invitation email journey separately if it will be shown live. If mail
  delivery has not been verified, begin with accepted memberships and describe
  invitations without claiming delivery is production-verified.

Keep billing and mobile packaging out of this demo. They are deferred during the
current user-testing cycle.

## Demo workspace and accounts

Use dedicated demo accounts and separate browser profiles or private windows so
role changes are visible without repeatedly signing out. Never use production
customer accounts or place credentials in this repository.

Create a Team-plan workspace named **Northstar Artist Team** with these personas:

| Persona | Role | Purpose in the story |
| --- | --- | --- |
| Maya Cole, artist manager | Owner | Owns the workspace and makes the final release decision |
| David Okoro, label operations | Admin | Coordinates work and can review tasks |
| Teni James, creative producer | Member | Completes and submits campaign work |
| Aisha Bello, artist | Viewer | Follows progress without changing operational data |

For the cleanest approval demonstration, keep Maya or David available to review
Teni's submission. A person who submits a task must not review their own work;
another owner or admin should make the decision.

## Seed checklist

Seed through the product UI so notifications, approval events, and activity
records are created by normal application paths. Do not write approval columns
directly in Supabase.

Create one project:

- **MIDNIGHT SIGNAL — Single Release**
- Target date: three weeks after the demo date
- Description: “Lead single campaign, distribution delivery, and launch week.”

Create these tasks and assign them to the indicated personas:

| Task | Assignee | Starting state | Demo purpose |
| --- | --- | --- | --- |
| Approve final cover artwork | Teni | In progress | Submit and approve during the demo |
| Confirm DSP metadata and credits | David | To do | Show ownership and operational readiness |
| Deliver teaser cut to social team | Teni | To do | Add a comment and mention during the demo |
| Review release-day content calendar | Maya | Done | Show existing progress |
| Share private master with distributor | Teni | Rejected, with “Use the radio edit and add the ISRC” | Show review context and resubmission |

Before the session:

- add a comment from David on the teaser task asking Teni to confirm the vertical
  cut, and mention Teni;
- leave the resulting notification unread in Teni's account;
- submit **Approve final cover artwork** from Teni's account so it appears in the
  manager's Needs review queue, unless submitting it live is central to the pitch;
- ensure the rejected distributor task shows its reviewer, date, and note; and
- confirm Activity contains assignment, comment, mention, submission, and review
  events without unrelated setup noise dominating the first screen.

## 10–15 minute narrative

### 0:00–1:30 — Frame the operating problem

Open **Northstar Artist Team** as Maya.

Say: “A release usually lives across WhatsApp, email, spreadsheets, and somebody's
memory. Gravity OS gives the team one accountable operating layer without taking
creative control away from the manager or label.”

Show the workspace and release project. Point out the target date, visible task
owners, and current progress. Avoid touring every navigation item.

### 1:30–3:30 — Show roles and accountability

Open Team and introduce the four personas.

- Maya owns membership and final control.
- David can coordinate and review as an admin.
- Teni can do and submit work as a member.
- Aisha can follow the release as a viewer without accidentally changing it.

If time permits, briefly open the viewer profile and show that mutation controls
are unavailable or rejected. Do not spend the demo attempting every forbidden
action.

### 3:30–6:00 — Move work through collaboration

Switch to Teni and open Notifications. Follow David's mention to **Deliver teaser
cut to social team**, reply with a short update such as “Vertical cut is exported;
captions are being checked,” and return to Tasks.

Emphasize that the conversation remains attached to the work, while assignments,
mentions, and notifications bring the right person back to it.

If **Approve final cover artwork** was not pre-submitted, mark its work ready and
select **Submit**. Show the pending status and that the task is locked while it is
under review.

### 6:00–9:30 — Demonstrate manager approval control

Switch to Maya. Open the **Needs review** queue and select **Approve final cover
artwork**.

Show who submitted it, then approve it with a short note such as “Approved for
distribution and campaign use.” Point out the loading state and the resulting
reviewer, timestamp, and note. Explain that approved work remains locked against
casual edits.

Next open **Share private master with distributor**. Show its earlier rejection
note, then explain that Teni can correct and resubmit it while the review history
preserves the decision trail.

If the audience needs to see rejection live, use a disposable duplicate task,
reject it with a specific actionable note, then resubmit from Teni. Do not disturb
the primary approval story immediately before the demo.

### 9:30–11:30 — Close the accountability loop

Open Activity and trace the sequence: assignment or mention, member update,
approval submission, and manager decision. Then open Notifications to show how
the submitter is brought back after a decision.

Say: “The value isn't another task list. It is knowing who owns the next move,
what requires management attention, and why a release decision was made.”

### 11:30–15:00 — Tailor the close and invite feedback

For an artist manager, focus on fewer follow-ups, controlled approvals, and a
clear view of what might delay release day.

For a label owner, focus on repeatable operating standards across projects,
role boundaries, and an accountable decision history.

Ask two concrete discovery questions:

1. “Which release decision currently creates the most chasing or uncertainty for
   your team?”
2. “Who needs visibility into the work but should not be able to change it?”

Capture their language and objections. Do not promise billing, AI automation,
mobile apps, or workflows that are not present in the demonstrated build.

## Fallbacks during a live demo

- If a deployment is unavailable, stop and use screenshots or a local environment
  clearly labeled as local; do not imply production is healthy.
- If email delivery fails, use an already accepted membership and explain that
  the invitation delivery path is being verified.
- If one browser session expires, continue from another prepared persona rather
  than resetting credentials in front of the audience.
- If a notification is delayed, navigate directly to the task and use Activity to
  show the persisted event.
- If a seeded task was already reviewed, use the rejected task's resubmission path
  or a prepared disposable task instead of editing database approval fields.

## Reset checklist

Reset immediately after each session while the actions are still easy to recall.

- Return each browser profile to the intended persona and workspace.
- Remove any audience-specific names, comments, files, or sensitive examples.
- Restore the five seeded tasks to their documented assignees and starting story.
- Recreate the pending artwork review through Teni's normal **Submit** action.
- Restore the distributor task's rejected state through an owner/admin review with
  the standard note; never update approval fields directly.
- Recreate David's teaser comment/mention and leave Teni's notification unread if
  notification state can be reset cleanly. Otherwise use a fresh demo account or
  acknowledge the notification as previously read.
- Confirm the Needs review queue has exactly the intended demo item and no stale
  disposable tasks.
- Check Activity for accidental customer data or distracting setup events.
- Re-run the environment preflight, including API health and browser network/CORS
  checks, before the next external session.

For repeated demos, the safest reset is a dedicated disposable Team workspace per
session. Keep the persona names and seed checklist consistent, but use unique test
accounts and never reuse a real prospect's data.
