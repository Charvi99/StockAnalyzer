#!/usr/bin/env python3
"""
Migration helper script for Alembic database migrations.

Usage:
    python migrate.py create "migration message"  # Create new migration
    python migrate.py upgrade                     # Apply all migrations
    python migrate.py downgrade                   # Rollback one migration
    python migrate.py current                     # Show current revision
    python migrate.py history                     # Show migration history
    python migrate.py check                       # Check for pending migrations
"""
import sys
import subprocess
import os


def run_command(cmd):
    """Run a shell command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    return result.returncode


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    # Change to backend directory if not already there
    if os.path.basename(os.getcwd()) != 'backend':
        backend_dir = os.path.join(os.path.dirname(__file__))
        if backend_dir:
            os.chdir(backend_dir)

    if command == 'create':
        if len(sys.argv) < 3:
            print("Error: Please provide a migration message")
            print('Usage: python migrate.py create "your migration message"')
            sys.exit(1)

        message = sys.argv[2]
        print(f"Creating new migration: {message}")
        return run_command(['alembic', 'revision', '--autogenerate', '-m', message])

    elif command == 'upgrade':
        print("Applying all pending migrations...")
        return run_command(['alembic', 'upgrade', 'head'])

    elif command == 'downgrade':
        steps = sys.argv[2] if len(sys.argv) > 2 else '-1'
        print(f"Rolling back {steps} migration(s)...")
        return run_command(['alembic', 'downgrade', steps])

    elif command == 'current':
        print("Current database revision:")
        return run_command(['alembic', 'current'])

    elif command == 'history':
        print("Migration history:")
        return run_command(['alembic', 'history', '--verbose'])

    elif command == 'check':
        print("Checking for pending migrations...")
        result = subprocess.run(['alembic', 'current'], capture_output=True, text=True)

        if result.returncode != 0:
            print("Error checking migrations")
            return 1

        current = result.stdout.strip()

        result = subprocess.run(['alembic', 'heads'], capture_output=True, text=True)
        head = result.stdout.strip()

        if current == head or head in current:
            print("✓ Database is up to date")
            return 0
        else:
            print(f"⚠ Database needs migration")
            print(f"Current: {current}")
            print(f"Latest:  {head}")
            return 1

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    sys.exit(main())
