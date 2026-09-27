#!/usr/bin/env bash
set -e

OUTPUT_ZIP="${1:-repository.zip}"

echo "Generating $OUTPUT_ZIP using git archive..."
git archive --format=zip -o "$OUTPUT_ZIP" HEAD

echo "Done. Created $OUTPUT_ZIP successfully."
