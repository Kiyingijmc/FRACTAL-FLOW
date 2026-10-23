#!/usr/bin/env bash
set -euo pipefail

# Branch and repo configuration
BRANCH="feature/gui-control-surface"
BASE="main"
REPO="Kiyingijmc/FRACTAL-FLOW"
PR_TITLE="feat(gui): implement FRACTAL-FLOW operator control surface frontend and specification"
PR_BODY="## Overview
This PR introduces the **FRACTAL-FLOW Control Surface**, a low-latency, high-density operator instrument panel designed specifically for systematic multi-timeframe algorithmic trading.

Built in accordance with \`spec/control_surface_v1.yaml\` and \`docs/24_CONTROL_SURFACE_DESIGN_SYSTEM.md\`.

## Key Capabilities & Safety Invariants

1. **Separation of Simulation from Broker Authority (P0)**:
   - Clear amber operational badge: \`MODE: SIMULATION (OFF-BROKER SANDBOX)\` when running off-broker.
   - Simulation state updates are strictly decoupled from broker execution.
2. **Formal Command Lifecycle (P0)**:
   - Tracks and displays exact states: \`REQUESTED\` -> \`ACCEPTED\` -> \`DISPATCHED\` -> \`CONFIRMED\` / \`REJECTED\` with client-side idempotency keys.
3. **Auditable System Event Stream (P1)**:
   - Event-sourced journal ticker with source attribution (\`GATEWAY\`, \`JOURNAL\`, \`SIM_ENGINE\`) and delivery status.
4. **Signature Visual Devices**:
   - **Eleven-Gate Chain Strip (\`Q E R P L O T N K A X\`)**: Real-time evaluation of setup candidates against the 11 mandatory validity gates.
   - **Timeframe Cascade Indicator**: Active driving timeframe and hierarchy tracking (\`4H\` -> \`1H\` -> \`30M\` -> \`15M\` -> \`5M\` -> \`1M\`).
5. **Operator Ergonomics & Rapid Response**:
   - Keyboard hotkeys: \`T\` (Tighten stop), \`B\` (Move to breakeven), \`C\`/\`X\` (Close position), \`Esc\` (Return to POS).
   - Multi-symbol instance detector with dropdown selector.
   - Real-time closed trade statistics calculator in context panel.
   - Macroeconomic news and Gate-N embargo shield calendar tab.

## Verification
- Clean build with Vite and Tailwind v4 (\`npm run build\` passes with 0 errors).
- TypeScript strict lint (\`tsc --noEmit\` passes with 0 errors).
- Added GitHub Actions workflow \`.github/workflows/gui-ci.yml\` for automated verification on pull requests.
"

echo "=== FRACTAL-FLOW GUI Pull Request Creator ==="

# Check if GITHUB_TOKEN or GH_TOKEN is set
if [ -n "${GITHUB_TOKEN:-}" ]; then
  TOKEN="${GITHUB_TOKEN}"
elif [ -n "${GH_TOKEN:-}" ]; then
  TOKEN="${GH_TOKEN}"
else
  read -rsp "Enter your GitHub Personal Access Token (with repo scope): " TOKEN
  echo ""
fi

if [ -z "${TOKEN}" ]; then
  echo "Error: GitHub token is required to push and create a PR."
  exit 1
fi

echo "Pushing branch ${BRANCH} to https://github.com/${REPO}.git..."
git push "https://${TOKEN}@github.com/${REPO}.git" "${BRANCH}:${BRANCH}"

echo "Branch successfully pushed!"

# If gh is installed, use gh to create PR
if command -v gh >/dev/null 2>&1; then
  echo "Creating PR via GitHub CLI..."
  gh pr create --repo "${REPO}" --base "${BASE}" --head "${BRANCH}" --title "${PR_TITLE}" --body "${PR_BODY}"
else
  echo "Creating PR via GitHub REST API..."
  PAYLOAD=$(cat <<JSON
{
  "title": "${PR_TITLE}",
  "head": "${BRANCH}",
  "base": "${BASE}",
  "body": $(echo -n "${PR_BODY}" | jq -s -R .)
}
JSON
)
  RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Accept: application/vnd.github.v3+json" \
    https://api.github.com/repos/${REPO}/pulls \
    -d "${PAYLOAD}")

  PR_URL=$(echo "${RESPONSE}" | grep -o '"html_url": *"[^"]*"' | head -n 1 | cut -d '"' -f 4 || true)
  if [ -n "${PR_URL}" ]; then
    echo "Successfully created Pull Request: ${PR_URL}"
  else
    echo "API Response: ${RESPONSE}"
    echo "If PR creation returned a message, visit: https://github.com/${REPO}/compare/${BASE}...${BRANCH}"
  fi
fi
