# Buyer Request Checklist (Pilot Intake) — ModeKeeper

ModeKeeper helps Platform/SRE/FinOps teams quantify and improve Kubernetes efficiency across:

**observe → evaluate/ROI → plan/verify → (optional) apply**

Core principle: **verify-first** — prove and validate before recommending, and only perform changes with explicit approval.

---

## 1) What we ask from you (minimum to start)

### 1.1. People / Owners
- [ ] Pilot technical owner (Platform/SRE) — name, role, contact
- [ ] FinOps/Finance contact (for pricing/billing, if available) — contact
- [ ] Security/Compliance contact (if your process requires) — contact

### 1.2. Pilot scope
- [ ] Environment: prod / stage / dev
- [ ] Clusters: names / count
- [ ] Namespaces: list
- [ ] Critical workloads: Deployments / StatefulSets / Jobs (list)
- [ ] Exclusions: what must not be touched and why (regulatory, legacy, freeze windows)

### 1.3. Goals & success criteria
Pick 1–3 primary goals:
- [ ] Reduce infrastructure spend (target): __%
- [ ] Reduce overprovisioning (CPU/RAM): __%
- [ ] Improve stability (OOM / throttling / latency / errors): which metrics
- [ ] Reduce incidents/pages: what is counted
- [ ] Standardize resource management (requests/limits/HPA/VPA): what “good” looks like

---

## 2) Data & access (read-only by default)

### 2.1. Kubernetes (read-only)
- [ ] Read-only access to the Kubernetes API (preferred):
  - view namespaces/workloads/pods/events
  - view current requests/limits/HPA/VPA (if present)
  - no mutation permissions
- [ ] Alternative (restricted environments): you run our read-only collector in your environment and share the outputs (we provide the exact command/instructions).

### 2.2. Metrics (recommended, not a hard blocker)
Check what exists:
- [ ] Prometheus / VictoriaMetrics / Thanos (or other metrics backend)
- [ ] Kubernetes metrics (metrics-server / kube-state-metrics)
- [ ] Logs/traces (optional): Loki/ELK/Jaeger/Tempo, etc.
- [ ] Metrics retention: __ days (ideally 7–14+)

### 2.3. Cost inputs (optional, improves ROI accuracy)
- [ ] You have unit rates (GPU-hour, vCPU-hour, GB-RAM-hour, storage) — yes/no
- [ ] You have billing export (cloud billing / internal chargeback) — yes/no
- [ ] If exact prices are not available — OK: we use a transparent **pricing anchor** and provide a linear rescaling formula for your rates.

---

## 3) Constraints & change policy (important)

### 3.1. Risk profile and guardrails
- [ ] What must not be changed: list
- [ ] Allowed recommendation types:
  - [ ] requests/limits
  - [ ] HPA/VPA (if you use them)
  - [ ] PDB/anti-affinity/topology spread (only if in scope)
- [ ] Change windows and approval process: maintenance windows, approvers

### 3.2. Security requirements
- [ ] Execution constraints: air-gapped / restricted egress / proxy / allowlist
- [ ] Artifact/report handling: formats, storage requirements, retention

---

## 4) What you receive (pilot deliverables)

### 4.1. Evaluate / ROI package
- [ ] Baseline usage profile (CPU/RAM/GPU/Pods/Nodes) over time
- [ ] Hotspots and inefficiencies (overprovisioning, pressure signals, waste patterns)
- [ ] ROI estimate with assumptions (including a pricing-anchor rescaling formula)

### 4.2. Plan / Verify package
- [ ] Per-workload recommended plan (what/why/expected impact)
- [ ] Verify checks: safety gates, invariants, compatibility, “before/after” criteria
- [ ] Deterministic artifacts: reports + integrity checks (checksums) + reproducible transcript

### 4.3. (Optional) Controlled Apply (PRO)
Only with explicit approval and in your change windows:
- [ ] Guarded apply with pre-checks and post-verification
- [ ] Rollback plan and stop conditions

---

## 5) What you do NOT need
- You do not need to grant admin permissions to quantify ROI: **read-only is enough**.
- During evaluate/plan we **do not mutate** your cluster.
- You can start without prices: ROI will include a pricing anchor and rescaling.

---

## 6) Kickoff questions (copy/paste)
1) Which 5–10 workloads are most expensive or most critical?
2) What matters more right now: **cost** or **stability/SLO**?
3) How many days of metrics history are available?
4) Any hard “do-not-touch” constraints (compliance/regulatory freezes)?
5) Who approves changes and what are the allowed windows?
