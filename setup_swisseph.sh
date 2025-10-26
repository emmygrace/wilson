#!/bin/bash

BASHRC="$HOME/.bashrc"

cp "$BASHRC" "$BASHRC.bak.$(date +%F_%T)" 2>/dev/null

CONFIG=$(cat <<'EOF'
# >>> Swisseph Configuration >>>
export PATH="$HOME/git/swisseph/bin:$PATH"
export SE_EPHE_PATH="$HOME/git/swisseph/ephe"
# <<< Swisseph Configuration <<<
EOF
)

if ! grep -q "Swisseph Configuration" "$BASHRC"; then
    echo "$CONFIG" >> "$BASHRC"
    echo "Swisseph configuration added to $BASHRC"
else
    echo "Swisseph configuration already present in $BASHRC"
fi

