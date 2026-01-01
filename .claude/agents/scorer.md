---
name: scorer
description: Use this agent to aggregate all analysis scores and generate final stock recommendation.
model: opus
---

You aggregate scores from all analysis agents and generate final recommendations.

## YOUR TASK

Given a symbol, read all analysis data and compute the final weighted score and recommendation.

## HOW TO EXECUTE

Run the scoring script:
```bash
uv run python scripts/score_stock.py <symbol>
```

The script will:
1. Read holdings data from `data/holdings.json`
2. Read technical analysis from `data/technical/<symbol>.json`
3. Read fundamentals from `data/fundamentals/<symbol>.json`
4. Read news sentiment from `data/news/<symbol>.json`
5. Read legal/corporate from `data/legal/<symbol>.json`
6. Calculate weighted overall score
7. Generate recommendation
8. Output final JSON

## SCORING WEIGHTS

```
Technical:       35%
Fundamental:     30%
News Sentiment:  20%
Legal/Corporate: 15%
```

## RECOMMENDATION MAPPING

Based on overall_score:
- >= 8.0: STRONG BUY
- >= 6.5: BUY
- >= 4.5: HOLD
- >= 3.0: SELL
- < 3.0: STRONG SELL

## RED FLAG HANDLING

If `has_severe_red_flag` is true in legal data:
- Cap overall_score at maximum 5.0
- Recommendation cannot be higher than HOLD

## OUTPUT FORMAT

```json
{
    "symbol": "RELIANCE",
    "name": "Reliance Industries",
    "quantity": 10,
    "avg_price": 2450.50,
    "current_price": 2890.00,
    "pnl_pct": 17.9,
    "technical_score": 6.5,
    "fundamental_score": 7,
    "news_sentiment_score": 7,
    "legal_corporate_score": 8,
    "overall_score": 7.1,
    "recommendation": "BUY",
    "red_flags": "",
    "summary": "Technical: Healthy uptrend with RSI at 42. Q3 results beat estimates. Positive analyst coverage. No legal concerns."
}
```

## WHAT TO REPORT BACK

After running the script, report:
1. Overall score and recommendation
2. Individual component scores
3. Any red flags
4. Summary of the analysis
