#!/usr/bin/env bash
# Fetches upstream BMSim at the tested commit and applies the integration hooks.
# BMSim itself is NOT redistributed in this repository; see THIRD_PARTY_NOTICES.md.
set -euo pipefail
cd "$(dirname "$0")"
BMSIM_URL="https://github.com/BMSimulator/BMSim.git"
BMSIM_COMMIT="7c6af2a"

if [ ! -d vendor/BMSim ]; then
    git clone "$BMSIM_URL" vendor/BMSim
fi
git -C vendor/BMSim checkout -q "$BMSIM_COMMIT"
if git -C vendor/BMSim apply --check ../../patches/bmsim_hooks.patch 2>/dev/null; then
    git -C vendor/BMSim apply ../../patches/bmsim_hooks.patch
    echo "BMSim $BMSIM_COMMIT patched with integration hooks."
else
    echo "Patch already applied (or BMSim has local changes); leaving vendor/BMSim as is."
fi
