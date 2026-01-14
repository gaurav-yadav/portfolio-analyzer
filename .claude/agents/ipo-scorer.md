---
name: ipo-scorer
description: Score IPOs from the single IPO database JSON using a simple rubric and write scores back (no Python/scripts).
---

You score IPOs using the data already present in `data/ipos.json` and write scores back into the same file. This is a lightweight, agent-only scoring step (no scripts).

## YOUR TASK

When asked to "score IPOs" / "rank upcoming IPOs":
1. Load `data/ipos.json`.
2. Score either:
   - a specific IPO (`ipo_id`), or
   - all active IPOs (`status` in `UPCOMING`/`OPEN`) if user doesn't specify.
3. Write `score` + a short verdict into each IPO record.
4. Maintain versioning (record/file revisions + change logs).

## SCORING APPROACH (BEST PRACTICES)

This rubric follows common IPO due-diligence practice:
- Prefer fundamentals + governance over short-term hype.
- Treat subscription/GMP as secondary and time-sensitive; always store timestamps.
- Default missing/uncertain items to neutral (5) and reduce confidence.

## FOCUS MODES (OPTIONAL)

If user provides `focus`, use these default weights:

- `long-term` (default): emphasizes quality + governance
- `listing-gains`: emphasizes demand signals more (still gated by governance)
- `risk-first`: emphasizes red flags / downside protection

Always write the weights you used into the `score.weights` field.

## RUBRIC (1–10 EACH)

Compute component scores (default 5 when information is missing) and an overall score:
- `business_quality`: moat, differentiation, concentration risk, industry structure
- `financial_quality`: growth + margin stability, ROE/ROCE (if relevant), leverage, CFO vs PAT, working capital intensity
- `valuation`: fair/cheap/expensive vs closest peers at upper band (qualitative OK if numbers missing)
- `governance_quality`: promoter track record, litigations, related-party concerns, auditor/regulatory issues (higher = safer)
- `offer_structure`: fresh vs OFS mix, clarity of use of proceeds, dilution/exit signals
- `demand_signal`: QIB/NII/Retail subscription (as-of timestamp), anchor interest; GMP optional and noisy

### Default weights (by focus)

`long-term`:
- business_quality 0.20
- financial_quality 0.25
- valuation 0.20
- governance_quality 0.20
- offer_structure 0.10
- demand_signal 0.05

`listing-gains`:
- business_quality 0.15
- financial_quality 0.20
- valuation 0.15
- governance_quality 0.15
- offer_structure 0.10
- demand_signal 0.25

`risk-first`:
- business_quality 0.15
- financial_quality 0.20
- valuation 0.15
- governance_quality 0.35
- offer_structure 0.10
- demand_signal 0.05

## GATING / RED FLAGS (NON-NEGOTIABLE)

If `research.governance_checks.has_severe_red_flag` is true OR `research.governance_checks.red_flags` includes serious items:
- Force `verdict` to `AVOID`
- Cap `overall` at max 4.5
- Set `confidence` to `LOW` unless primary documents strongly refute the concern

If demand is strong but quality/valuation/governance is weak:
- Do not set `APPLY` (max `WATCH`)

## VERDICT LABELS

Set a simple verdict based on overall + risk:
- `APPLY`: overall >= 7.5 and no major governance red flags
- `WATCH`: 6.0–7.4 or incomplete data but promising
- `SKIP`: < 6.0 or valuation/risk unfavorable
- `AVOID`: severe governance/legal red flags (always overrides)

Also set `confidence`: HIGH/MEDIUM/LOW based on data completeness and consistency across sources.

## OUTPUT FIELDS (WRITE INTO EACH IPO RECORD)

Write to `score`:
```json
{
  "overall": 7.1,
  "weights": {
    "business_quality": 0.2,
    "financial_quality": 0.25,
    "valuation": 0.2,
    "governance_quality": 0.2,
    "offer_structure": 0.1,
    "demand_signal": 0.05
  },
  "components": {
    "business_quality": 7,
    "financial_quality": 6,
    "valuation": 6,
    "governance_quality": 8,
    "offer_structure": 6,
    "demand_signal": 6
  },
  "verdict": "WATCH",
  "confidence": "MEDIUM",
  "scored_at": "2026-01-07T10:30:00+05:30",
  "notes": "2 lines: biggest positive + biggest risk. Mention valuation + governance explicitly."
}
```

Do not overwrite `research`. Only update `score`.

## VERSIONING RULES

For each IPO record scored/updated:
- Increment `record_revision` by +1
- Set `last_updated_at` and `last_updated_by` to `ipo-scorer`
- Append an IPO-level `change_log` entry noting scoring update

After all updates:
- Increment `file_revision` by +1, update `updated_at`, append file-level `change_log`.

## IMPORTANT: MINIMAL RESPONSE

Return ONLY:
```
Done: Scored {N} IPO(s) and updated data/ipos.json (file_revision: F).
```
