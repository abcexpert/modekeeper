# OUTBOUND_BATCH

First real ICP outreach operating doc for ModeKeeper public core.

Purpose: run the first outbound batch with consistent selection, prep, and first-contact execution.

Boundary source of truth:
- `docs/SNAPSHOT.md`
- `docs/OUTREACH_PACK.md`
- `docs/OUTREACH_MESSAGES.md`

## 1) ICP buckets

1. GPU/ML platform buyer
- Owns or strongly influences Kubernetes/GPU platform efficiency, capacity, or reliability outcomes.

2. Platform/SRE buyer
- Owns or strongly influences Kubernetes platform operations, reliability, and change risk controls.

3. Procurement/Security entry
- Controls security, risk, or procurement intake for infrastructure tooling evaluation.

## 2) Company/account selection criteria

Select accounts that meet all required criteria:
- Required: active Kubernetes usage with clear platform ownership.
- Required: plausible GPU or high-cost compute footprint, or explicit infra cost/risk pressure.
- Required: real need for read-only assessment before change (cost/risk visibility, review process, or control requirements).
- Required: can evaluate customer-managed execution in their own environment.

Prefer accounts with at least one:
- Existing platform/SRE governance process for infrastructure changes.
- Security/procurement review gate for new tooling.
- Visible signals of cost-efficiency or reliability initiatives.

## 3) Minimum research fields before outreach

Collect these fields per account before sending first contact:
- Company name and primary domain.
- ICP bucket choice (GPU/ML platform, Platform/SRE, or Procurement/Security entry).
- Why this account fits now (1 short line tied to public signals).
- Target person name.
- Target person role/title.
- Reason this person is a valid first-contact target (ownership or gate relevance).
- Kubernetes relevance signal (public evidence or statement).
- GPU/cost/risk relevance signal (public evidence or statement).
- Chosen template (`docs/OUTREACH_MESSAGES.md` section 1/2/3).
- Message variant (initial or follow-up).
- Date sent and channel.
- Reply status (`no reply`, `replied`, `not a fit`).

## 4) Template mapping by ICP

Use only the matching template in `docs/OUTREACH_MESSAGES.md`:
- ICP `GPU/ML platform buyer` -> section `1) GPU/ML platform buyer`.
- ICP `Platform/SRE buyer` -> section `2) Platform/SRE buyer`.
- ICP `Procurement/Security entry` -> section `3) Procurement/Security entry`.

Message boundary must stay inside `docs/OUTREACH_PACK.md` and `docs/SNAPSHOT.md` claims.

## 5) Valid first-contact target definition

A target is valid only if all are true:
- Person has direct ownership/influence for the chosen ICP bucket.
- Person can act on a read-only assessment conversation (not only general interest).
- Role is close enough to Kubernetes/GPU cost/risk review or procurement/security intake.
- Contact path is direct and specific (named person, role-aligned).

## 6) What to avoid in target selection

Do not select:
- Accounts without clear Kubernetes/platform relevance.
- Accounts with no credible GPU/cost/risk signal for this motion.
- Contacts with no decision, ownership, or gate influence for the ICP.
- Generic inboxes or non-specific contacts when named role owners are available.
- Targets that require claims outside current public boundary.

## 7) Operating sequence (first batch)

1. Research
- Fill all minimum research fields for an account.

2. Pick ICP
- Choose exactly one ICP bucket based on role + account need.

3. Choose template
- Use the mapped `docs/OUTREACH_MESSAGES.md` template only.

4. Send
- Send initial message with boundary-safe wording.

5. Track reply
- Log sent date/channel and reply status.
- On positive reply, use the matching follow-up template only.
