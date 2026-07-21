#!/bin/bash
# Migration helper script for use in Docker container or locally
#
# Usage:
#   ./migrate.sh create "migration message"  # Create new migration
#   ./migrate.sh upgrade                     # Apply all migrations
#   ./migrate.sh downgrade                   # Rollback one migration
#   ./migrate.sh current                     # Show current revision
#   ./migrate.sh history                     # Show migration history
#   ./migrate.sh check                       # Check for pending migrations

set -e

COMMAND=${1:-help}

case $COMMAND in
  create)
    if [ -z "$2" ]; then
      echo "Error: Please provide a migration message"
      echo 'Usage: ./migrate.sh create "your migration message"'
      exit 1
    fi
    echo "Creating new migration: $2"
    alembic revision --autogenerate -m "$2"
    ;;

  upgrade)
    echo "Applying all pending migrations..."
    alembic upgrade head
    ;;

  downgrade)
    STEPS=${2:--1}
    echo "Rolling back $STEPS migration(s)..."
    alembic downgrade $STEPS
    ;;

  current)
    echo "Current database revision:"
    alembic current
    ;;

  history)
    echo "Migration history:"
    alembic history --verbose
    ;;

  check)
    echo "Checking for pending migrations..."
    CURRENT=$(alembic current 2>&1)
    HEAD=$(alembic heads 2>&1)

    if [[ "$CURRENT" == *"$HEAD"* ]] || [[ "$HEAD" == *"$CURRENT"* ]]; then
      echo "✓ Database is up to date"
      exit 0
    else
      echo "⚠ Database needs migration"
      echo "Current: $CURRENT"
      echo "Latest:  $HEAD"
      exit 1
    fi
    ;;

  help|*)
    cat << EOF
Migration helper script for Alembic database migrations.

Usage:
    ./migrate.sh create "migration message"  # Create new migration
    ./migrate.sh upgrade                     # Apply all migrations
    ./migrate.sh downgrade [steps]           # Rollback migration(s) (default: -1)
    ./migrate.sh current                     # Show current revision
    ./migrate.sh history                     # Show migration history
    ./migrate.sh check                       # Check for pending migrations

Examples:
    # Create a new migration after changing models
    ./migrate.sh create "add user_email column"

    # Apply all pending migrations
    ./migrate.sh upgrade

    # Rollback last migration
    ./migrate.sh downgrade

    # Rollback 2 migrations
    ./migrate.sh downgrade -2

    # View current database version
    ./migrate.sh current

    # View all migrations
    ./migrate.sh history
EOF
    ;;
esac
