#!/bin/bash
# Simple wrapper for ML training commands

cd "$(dirname "$0")/.."

# Run command in ml-training container
docker-compose run --rm ml-training "$@"
