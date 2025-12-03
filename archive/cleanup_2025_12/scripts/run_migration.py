#!/usr/bin/env python
"""
Master Migration Script for P&ID Search Enhancement

Orchestrates the complete migration process:
1. Backup current data
2. Re-extract tags with new schema
3. Re-index to OpenSearch
4. Validate migration
5. Report results

Run with: python scripts/migration/run_migration.py
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from loguru import logger


def run_script(script_path: Path, description: str) -> bool:
    """
    Run a migration script and capture result

    Args:
        script_path: Path to script
        description: Description for logging

    Returns:
        True if success, False if failed
    """
    logger.info("=" * 70)
    logger.info(f"STEP: {description}")
    logger.info("=" * 70)
    logger.info(f"Running: {script_path}")

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        # Print output
        if result.stdout:
            print(result.stdout)

        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode == 0:
            logger.info(f"✓ {description} - COMPLETED")
            return True
        else:
            logger.error(f"✗ {description} - FAILED (exit code: {result.returncode})")
            return False

    except Exception as e:
        logger.error(f"✗ {description} - EXCEPTION: {e}")
        return False


def confirm_migration():
    """Ask user to confirm migration"""
    print("\n" + "=" * 70)
    print("P&ID SEARCH ENHANCEMENT MIGRATION")
    print("=" * 70)
    print("\nThis migration will:")
    print("  1. Backup current P&ID tags data")
    print(
        "  2. Re-extract all tags with new schema (UNIT/PREFIX/SUFFIX/VARIANT/ANNOTATION)"
    )
    print("  3. Delete and recreate OpenSearch tags index")
    print("  4. Validate the migration")
    print("\nEstimated time: 20-45 minutes")
    print("\n⚠️  WARNING: This is a HARD MIGRATION (index will be rebuilt)")
    print("   Backup will be created for rollback if needed.")
    print("\n" + "=" * 70)

    response = input("\nProceed with migration? (yes/no): ").strip().lower()

    return response in ["yes", "y"]


def main():
    """Main migration orchestration"""
    start_time = datetime.now()

    # Confirm migration
    if not confirm_migration():
        logger.info("Migration cancelled by user")
        return

    logger.info(f"\nMigration started at: {start_time.isoformat()}")

    # Define migration steps
    steps = [
        {
            "script": PROJECT_ROOT / "scripts/migration/backup_pid_data.py",
            "description": "Backup current data",
            "critical": True,
        },
        {
            "script": PROJECT_ROOT / "scripts/migration/reextract_tags.py",
            "description": "Re-extract tags with new schema",
            "critical": True,
        },
        {
            "script": PROJECT_ROOT / "scripts/migration/reindex_tags.py",
            "description": "Re-index to OpenSearch",
            "critical": True,
        },
        {
            "script": PROJECT_ROOT / "scripts/migration/validate_migration.py",
            "description": "Validate migration",
            "critical": False,  # Validation can fail but migration might still be OK
        },
    ]

    # Run migration steps
    results = []

    for i, step in enumerate(steps, 1):
        logger.info(f"\n\n[STEP {i}/{len(steps)}]")

        success = run_script(step["script"], step["description"])

        results.append(
            {
                "step": step["description"],
                "success": success,
                "critical": step["critical"],
            }
        )

        if not success and step["critical"]:
            logger.error(f"\n❌ CRITICAL STEP FAILED: {step['description']}")
            logger.error("Migration aborted!")
            logger.error("\nTo rollback, run:")
            logger.error("  python scripts/migration/restore_backup.py")
            sys.exit(1)

    # Migration complete
    end_time = datetime.now()
    duration = end_time - start_time

    logger.info("\n" + "=" * 70)
    logger.info("MIGRATION COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Started: {start_time.isoformat()}")
    logger.info(f"Ended: {end_time.isoformat()}")
    logger.info(f"Duration: {duration}")
    logger.info("\nSteps:")

    for result in results:
        status = "✓ PASS" if result["success"] else "✗ FAIL"
        critical = " (CRITICAL)" if result["critical"] else ""
        logger.info(f"  {status} - {result['step']}{critical}")

    # Check if all critical steps passed
    critical_failures = [r for r in results if not r["success"] and r["critical"]]

    if critical_failures:
        logger.error("\n❌ Migration completed with CRITICAL failures!")
        logger.error("Consider running rollback:")
        logger.error("  python scripts/migration/restore_backup.py")
        sys.exit(1)
    else:
        logger.info("\n✅ Migration completed successfully!")
        logger.info("\nNext steps:")
        logger.info(
            "  1. Review validation report: artifacts/migration/validation_report.json"
        )
        logger.info("  2. Run manual tests (see README_MIGRATION.md)")
        logger.info("  3. Monitor production queries")
        logger.info("\nIf issues arise, rollback with:")
        logger.info("  python scripts/migration/restore_backup.py")


if __name__ == "__main__":
    main()
