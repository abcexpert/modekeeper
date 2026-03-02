# OUTREACH_CALL_20MIN

Buyer-facing 20-minute discovery call script for ModeKeeper.

Positioning: ModeKeeper is **verify-first** for Kubernetes efficiency:
**observe -> ROI -> plan/verify -> optional apply**.

Related buyer docs:
- [docs/BUYER_10MIN.md](BUYER_10MIN.md)
- [docs/BUYER_REQUEST_CHECKLIST.md](BUYER_REQUEST_CHECKLIST.md)
- [docs/PROOF_PACKS.md](PROOF_PACKS.md)

## 0) Call flow at a glance (20 minutes)

- 0:00-1:00 Opening
- 1:00-2:00 Agenda and outcomes
- 2:00-10:00 Discovery (context, pain, constraints)
- 10:00-13:00 Qualification (fit and urgency)
- 13:00-16:00 Objections + verify-first response
- 16:00-18:00 Pilot proposal
- 18:00-20:00 Confirm next steps

## 1) Opening (60 seconds)

Use this script:

> Thanks for joining. I will keep this practical and short.  
> In 20 minutes, we should answer three things:  
> 1) Is there measurable Kubernetes efficiency upside for your team?  
> 2) Can we prove value safely in read-only mode first?  
> 3) Do we have a clear pilot plan with owners and dates?  
> ModeKeeper works verify-first: we observe current behavior, quantify ROI, produce a plan and verification evidence, and only discuss apply if you explicitly want that later.

## 2) Agenda (say this at minute 1)

> Proposed agenda: quick context from you, your top efficiency goals and guardrails, fit check, then a concrete pilot proposal and next steps. Sound good?

## 3) Discovery questions (minutes 2-10)

Use these in order. Keep answers short and specific.

1. Scope: Which clusters and namespaces matter most right now?
2. Priority: Is your top objective cost reduction, stability, or both?
3. Pain: Which workloads feel overprovisioned or unstable today?
4. Baseline: Do you already track CPU/RAM/GPU utilization and saturation trends?
5. Incidents: Any recent throttling, OOM, latency spikes, or paging patterns tied to capacity settings?
6. Financial lens: Do you have internal unit costs, or should we start with a transparent pricing anchor?
7. Constraints: What is explicitly out of scope or "do not touch"?
8. Access model: Can you provide read-only Kubernetes access, or do you prefer running collection commands in your environment?
9. Governance: Who approves change windows if you later choose apply?
10. Success criteria: What must be true in 2-4 weeks for you to call this pilot successful?

Reference for intake details:
- [docs/BUYER_REQUEST_CHECKLIST.md](BUYER_REQUEST_CHECKLIST.md)

## 4) Qualification (minutes 10-13)

Use a simple pass/hold decision.

Pass now if all are true:
- Clear owner from Platform/SRE and a business stakeholder.
- Defined pilot scope (at least one cluster/namespace group).
- A measurable goal (cost, efficiency, stability, or incident reduction).
- Read-only data path is available.
- Timeline urgency within this quarter.

Hold if one or more are missing:
- No owner, no scope, or no measurable goal.
- Access blocked with no workaround.
- No ability to review results in the next 2-3 weeks.

## 5) Objection handling (minutes 13-16)

### "We cannot allow risky changes."

Response:
> That is exactly why we start verify-first. Initial work is read-only: observe, ROI, and plan/verify evidence. No mutations are required for value proof.

### "We do not trust black-box recommendations."

Response:
> We provide explicit assumptions, expected impact, and verification artifacts before any change discussion. You can review the plan as evidence, not as blind automation.

### "We do not have perfect cost data."

Response:
> We can still start with a pricing anchor and show linear rescaling so your finance rates can be applied later without redoing discovery.

### "This sounds like extra process overhead."

Response:
> The process is intentionally short: observe current state, quantify likely ROI, verify a safe plan, and decide. It reduces rework from unverified tuning.

Reference material for proof workflows:
- [docs/PROOF_PACKS.md](PROOF_PACKS.md)
- [docs/BUYER_10MIN.md](BUYER_10MIN.md)

## 6) Pilot proposal (minutes 16-18)

Use this structure live:

1. Scope: 1-2 clusters, agreed namespaces, 5-15 priority workloads.
2. Duration: 14 days total.
3. Phase 1 (Days 1-5): Observe + baseline + initial ROI estimate.
4. Phase 2 (Days 6-10): Plan/verify package with workload-level recommendations and safety checks.
5. Phase 3 (Days 11-14): Decision checkpoint; optional controlled apply planning only if approved.
6. Deliverables: baseline summary, ROI model + assumptions, plan/verify artifacts, decision readout.
7. Success metrics: target efficiency or spend reduction range, plus stability guardrail metrics.

## 7) Next steps (minutes 18-20)

Close with explicit commitments:

1. Confirm pilot owner(s) and communication channel.
2. Confirm pilot scope (clusters/namespaces/workloads).
3. Confirm data/access path (read-only preferred).
4. Confirm success metrics and decision date.
5. Schedule kickoff and weekly review now.

## 8) Follow-up email template (short)

Subject: ModeKeeper pilot proposal - verify-first Kubernetes efficiency

Hi {{Name}},

Thanks for the call today. Recap of what we aligned:

- Primary goal: {{cost/stability/both}}
- Pilot scope: {{clusters/namespaces/workloads}}
- Constraints: {{do-not-touch items, change policy}}
- Access path: {{read-only API or customer-run collection}}
- Success criteria: {{metrics + target range}}
- Decision date: {{date}}

Proposed pilot (14 days):
- Observe baseline and quantify ROI
- Produce plan/verify evidence package
- Optional apply planning only with explicit approval

Buyer references:
- [docs/BUYER_REQUEST_CHECKLIST.md](BUYER_REQUEST_CHECKLIST.md)
- [docs/PROOF_PACKS.md](PROOF_PACKS.md)
- [docs/BUYER_10MIN.md](BUYER_10MIN.md)

If this matches your view, reply "approved" and we will start kickoff scheduling.

Best,  
{{Your name}}
