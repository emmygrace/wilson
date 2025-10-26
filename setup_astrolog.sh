#!/usr/bin/env bash

ASTROLOG_PATH="$HOME/git/astro"
ASTR770_PATH="$HOME/git/astro/source"
ASTR_PATH="$HOME/git/astro/ephem"

cat << EOF >> "$HOME/.bashrc"

export ASTROLOG="$ASTROLOG_PATH"
export ASTR770="$ASTR770_PATH"
export ASTR="$ASTR_PATH"
EOF

source "$HOME/.bashrc"

if [[ -n "$ASTROLOG" && -n "$ASTR770" && -n "$ASTR" ]]; then
  echo "Environment variables set successfully:"
  echo "  ASTROLOG=$ASTROLOG"
  echo "  ASTR770=$ASTR770"
  echo "  ASTR=$ASTR"
  exit 0
else
  echo "Error: one or more environment variables are not set." >&2
  exit 1
fi

