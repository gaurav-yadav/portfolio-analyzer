#!/usr/bin/env python3
"""
Portfolio Report Compiler - Compiles all stock scores into a comprehensive report.

Usage:
    uv run python scripts/compile_report.py

Output:
    Creates output/analysis_YYYYMMDD_HHMMSS.csv with:
    - Individual stock analysis rows
    - Portfolio health summary footer
"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.helpers import load_json


# Recommendation thresholds (matching score_stock.py)
THRESHOLDS = {
    "strong_buy": 8.0,
    "buy": 6.5,
    "hold": 4.5,
    "sell": 3.0,
}


def get_recommendation(score: float) -> str:
    """Map score to recommendation."""
    if score >= THRESHOLDS["strong_buy"]:
        return "STRONG BUY"
    elif score >= THRESHOLDS["buy"]:
        return "BUY"
    elif score >= THRESHOLDS["hold"]:
        return "HOLD"
    elif score >= THRESHOLDS["sell"]:
        return "SELL"
    else:
        return "STRONG SELL"


def get_portfolio_health_label(avg_score: float) -> str:
    """Get overall portfolio health assessment."""
    if avg_score >= 7.5:
        return "Excellent"
    elif avg_score >= 6.5:
        return "Good"
    elif avg_score >= 5.5:
        return "Fair"
    elif avg_score >= 4.5:
        return "Needs Attention"
    else:
        return "At Risk"


def get_overall_recommendation(distribution: dict, avg_score: float) -> str:
    """Generate overall portfolio recommendation based on distribution and score."""
    strong_buy = distribution.get("STRONG BUY", 0)
    buy = distribution.get("BUY", 0)
    hold = distribution.get("HOLD", 0)
    sell = distribution.get("SELL", 0)
    strong_sell = distribution.get("STRONG SELL", 0)

    total = strong_buy + buy + hold + sell + strong_sell
    if total == 0:
        return "No stocks analyzed"

    bullish_pct = (strong_buy + buy) / total * 100
    bearish_pct = (sell + strong_sell) / total * 100

    if avg_score >= 7.0 and bullish_pct >= 60:
        return "Portfolio is well-positioned. Consider adding to strong performers."
    elif avg_score >= 6.0 and bullish_pct >= 40:
        return "Portfolio is healthy. Monitor HOLD positions for opportunities."
    elif bearish_pct >= 40:
        return "Portfolio needs rebalancing. Review SELL/STRONG SELL positions."
    elif avg_score < 5.0:
        return "Portfolio is underperforming. Consider defensive adjustments."
    else:
        return "Portfolio is balanced. Regular monitoring recommended."


def compile_report() -> str:
    """
    Compile all stock scores into a comprehensive CSV report.

    Returns:
        Path to the generated report file
    """
    base_path = Path(__file__).parent.parent
    scores_dir = base_path / "data" / "scores"
    output_dir = base_path / "output"

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all score files
    score_files = list(scores_dir.glob("*.json"))

    if not score_files:
        print("No score files found in data/scores/", file=sys.stderr)
        sys.exit(1)

    # Load all scores
    all_scores = []
    for score_file in score_files:
        data = load_json(score_file)
        if data:
            all_scores.append(data)

    if not all_scores:
        print("No valid score data found", file=sys.stderr)
        sys.exit(1)

    # Sort by overall score descending
    all_scores.sort(key=lambda x: x.get("overall_score", 0), reverse=True)

    # Calculate portfolio statistics
    total_stocks = len(all_scores)
    scores_list = [s.get("overall_score", 0) for s in all_scores]
    avg_score = round(sum(scores_list) / len(scores_list), 2) if scores_list else 0

    # Count recommendations distribution
    distribution = {}
    for s in all_scores:
        rec = s.get("recommendation", "UNKNOWN")
        distribution[rec] = distribution.get(rec, 0) + 1

    # Find top and worst performers
    top_performer = all_scores[0] if all_scores else None
    worst_performer = all_scores[-1] if all_scores else None

    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"analysis_{timestamp}.csv"

    # Define CSV columns
    columns = [
        "symbol",
        "name",
        "quantity",
        "avg_price",
        "current_price",
        "pnl_pct",
        "rsi",
        "rsi_score",
        "macd_score",
        "trend_score",
        "bollinger_score",
        "adx_score",
        "volume_score",
        "technical_score",
        "fundamental_score",
        "news_sentiment_score",
        "legal_corporate_score",
        "overall_score",
        "recommendation",
        "summary",
        "red_flags",
    ]

    # Write CSV
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Header row
        writer.writerow(columns)

        # Data rows
        for stock in all_scores:
            row = []
            for col in columns:
                value = stock.get(col, "")
                # Format numeric values
                if col == "rsi" and value is not None:
                    value = round(value, 1) if isinstance(value, (int, float)) else value
                elif col == "current_price" and value:
                    value = round(value, 2) if isinstance(value, (int, float)) else value
                elif col in ["pnl_pct"] and value is not None:
                    value = f"{value}%" if isinstance(value, (int, float)) else value
                row.append(value)
            writer.writerow(row)

        # Empty row before footer
        writer.writerow([])

        # Portfolio Health Summary Footer
        writer.writerow(["=" * 20, "PORTFOLIO HEALTH SUMMARY", "=" * 20] + [""] * (len(columns) - 3))
        writer.writerow([])

        # Summary statistics
        writer.writerow(["Total Stocks Analyzed:", total_stocks])
        writer.writerow(["Portfolio Health Score:", f"{avg_score}/10"])
        writer.writerow(["Portfolio Health:", get_portfolio_health_label(avg_score)])
        writer.writerow([])

        # Recommendation distribution
        writer.writerow(["RECOMMENDATION DISTRIBUTION:"])
        for rec in ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]:
            count = distribution.get(rec, 0)
            pct = round(count / total_stocks * 100, 1) if total_stocks > 0 else 0
            bar = "*" * count
            writer.writerow([f"  {rec}:", f"{count} ({pct}%)", bar])
        writer.writerow([])

        # Top and worst performers
        if top_performer:
            writer.writerow([
                "Top Performer:",
                f"{top_performer.get('symbol')} ({top_performer.get('name')})",
                f"Score: {top_performer.get('overall_score')}/10",
                top_performer.get("recommendation"),
            ])
        if worst_performer and worst_performer != top_performer:
            writer.writerow([
                "Needs Attention:",
                f"{worst_performer.get('symbol')} ({worst_performer.get('name')})",
                f"Score: {worst_performer.get('overall_score')}/10",
                worst_performer.get("recommendation"),
            ])
        writer.writerow([])

        # Overall recommendation
        overall_rec = get_overall_recommendation(distribution, avg_score)
        writer.writerow(["OVERALL RECOMMENDATION:", overall_rec])
        writer.writerow([])

        # Timestamp
        writer.writerow(["Report Generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])

    return str(output_file)


def print_summary(output_file: str, all_scores: list):
    """Print a summary of the report to stdout."""
    total = len(all_scores)
    if total == 0:
        print("No stocks analyzed.")
        return

    scores_list = [s.get("overall_score", 0) for s in all_scores]
    avg_score = round(sum(scores_list) / len(scores_list), 2)

    distribution = {}
    for s in all_scores:
        rec = s.get("recommendation", "UNKNOWN")
        distribution[rec] = distribution.get(rec, 0) + 1

    print("\n" + "=" * 60)
    print("PORTFOLIO ANALYSIS REPORT")
    print("=" * 60)
    print(f"\nReport saved to: {output_file}")
    print(f"\nTotal Stocks Analyzed: {total}")
    print(f"Portfolio Health Score: {avg_score}/10 ({get_portfolio_health_label(avg_score)})")
    print("\nRecommendation Distribution:")
    for rec in ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]:
        count = distribution.get(rec, 0)
        pct = round(count / total * 100, 1) if total > 0 else 0
        print(f"  {rec}: {count} ({pct}%)")

    print(f"\nOverall: {get_overall_recommendation(distribution, avg_score)}")
    print("=" * 60 + "\n")


def main():
    base_path = Path(__file__).parent.parent
    scores_dir = base_path / "data" / "scores"

    # Load scores for summary display
    score_files = list(scores_dir.glob("*.json"))
    all_scores = []
    for score_file in score_files:
        data = load_json(score_file)
        if data:
            all_scores.append(data)

    # Sort by overall score descending
    all_scores.sort(key=lambda x: x.get("overall_score", 0), reverse=True)

    try:
        output_file = compile_report()
        print_summary(output_file, all_scores)
    except Exception as e:
        print(f"Error compiling report: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
