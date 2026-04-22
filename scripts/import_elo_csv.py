import csv
import sys
import argparse
import asyncio
from loguru import logger

# Add parent dir to path so we can import modules
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.m8_logger import FeedbackLogger

async def main():
    parser = argparse.ArgumentParser(description="Bulk import Elo match results from a CSV file.")
    parser.add_argument("csv_path", type=str, help="Path to the CSV file containing results")
    args = parser.parse_args()

    if not os.path.exists(args.csv_path):
        logger.error(f"CSV file not found: {args.csv_path}")
        return

    m8 = FeedbackLogger()
    success_count = 0
    fail_count = 0

    with open(args.csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            run_id = row.get("run_id")
            elo_outcome = row.get("elo_outcome")
            
            if not run_id or not elo_outcome:
                logger.warning(f"Skipping malformed row: {row}")
                continue
                
            if elo_outcome not in ["win", "loss"]:
                logger.warning(f"Invalid outcome for {run_id}: {elo_outcome}. Must be 'win' or 'loss'.")
                continue

            # Add to M8 feedback. Note: add_ai_student_feedback is synchronous.
            success = m8.add_ai_student_feedback(
                run_id=run_id,
                ai_student_scores={},  # Empty since we only have Elo
                critique_text="Bulk imported from real-world Elo arena match.",
                elo_outcome=elo_outcome
            )
            
            if success:
                success_count += 1
                logger.info(f"Successfully recorded Elo {elo_outcome} for run {run_id}")
            else:
                fail_count += 1
                logger.error(f"Failed to record run {run_id} (not found in M8 logs)")
                
    logger.success(f"Bulk import complete. Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    asyncio.run(main())
