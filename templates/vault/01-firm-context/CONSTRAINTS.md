---
type: firm-context
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [constraints, security, compliance]
status: evolving
---

# Firm Constraints

> This file is read by every agent before starting any PoC task.
> Constraints are not blockers — they are design inputs.
> If a constraint prevents a PoC from being effective, document it clearly so it can be escalated to stakeholders.

---

## How to use this file

**Agents**: Before proposing any architecture or tooling, check every section below. Flag any conflicts in the PoC note under a `## Constraint Conflicts` section. Never silently work around a constraint — surface it.

**Humans**: Update this file as you learn more. Mark items as `confirmed`, `suspected`, or `to-verify` so agents know how much weight to give each constraint.

---

## 1. Data Privacy & PII

**Status**: to-verify

- _Describe your organization's PII handling requirements here_
- _e.g. Client PII must not be sent to external AI APIs_
- _e.g. All AI processing involving client data must use anonymized or synthetic datasets_

**To verify**:
- [ ] Exact definition of PII at this organization
- [ ] Whether anonymized data is permitted in external APIs
- [ ] Data retention rules for AI-generated outputs

---

## 2. Cloud & SaaS Tool Restrictions

**Status**: to-verify

- _Describe approved and restricted cloud tools_
- _e.g. New SaaS tools require IT security review before use_
- _e.g. Vendor approval process: describe or link_

**Known approved tools**: _fill in as confirmed_

**Known restricted tools**: _fill in as confirmed_

**To verify**:
- [ ] Approved cloud vendors list
- [ ] Whether your AI provider qualifies as approved or requires review
- [ ] Self-hosted model options as fallback for restricted environments

---

## 3. AI Usage Policies

**Status**: to-verify

- _Describe your organization's formal or informal AI usage policies_
- _e.g. AI outputs must be reviewed by a human before client use_
- _e.g. AI must not make autonomous decisions on client accounts_

**To verify**:
- [ ] Whether a formal AI policy exists and who owns it
- [ ] Disclosure requirements for AI use in client-facing work

---

## 4. Regulatory Compliance

**Status**: to-verify

_List applicable regulatory frameworks for your organization and industry._

- _e.g. GDPR: data processing requirements_
- _e.g. SOX: audit implications for financial reporting_
- _e.g. Industry-specific regulations_

**To verify**:
- [ ] Which regulations the organization is actually subject to
- [ ] Whether compliance team needs to review AI PoCs before stakeholder presentation

---

## Hard Constraints (never design around these)

These are non-negotiable regardless of stakeholder approval:

- [ ] _Add confirmed hard constraints here as you identify them_
