#!/usr/bin/env bash
# Run inside an existing Frappe v16 bench. No sudo, no deletion, no automatic seeding.
set -euo pipefail
site="${1:-studentcrm.local}"
if [[ ! -d apps/frappe || ! -d sites || ! -x env/bin/python ]]; then
  echo 'Run this script from your frappe-bench directory.' >&2; exit 1
fi
if [[ ! "$site" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]+$ ]]; then
  echo 'Invalid site name.' >&2; exit 1
fi
if [[ ! -f "sites/$site/site_config.json" ]]; then
  echo "Site $site does not exist. Create it with: bench new-site $site" >&2; exit 1
fi
env/bin/python -c 'import frappe; assert frappe.__version__.split(".")[0] == "16", "Frappe v16 is required"'
if [[ ! -d apps/student_crm ]]; then
  bench get-app --branch main https://github.com/anhquan27it/student_crm.git
fi
if ! bench --site "$site" list-apps --format json | env/bin/python -c 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if any("student_crm" in apps for apps in data.values()) else 1)'; then
  bench --site "$site" install-app student_crm
fi
bench --site "$site" migrate
if [[ ! -f apps/student_crm/frontend/.env ]]; then
  printf 'PORT=5173\nHOST=127.0.0.1\nFRAPPE_URL=http://127.0.0.1:8000\nFRAPPE_SITE=%s\n' "$site" > apps/student_crm/frontend/.env
fi
printf '\nInstalled for %s. To create synthetic data (new/demo site only):\n' "$site"
printf 'bench --site %s execute student_crm.demo.seed\n' "$site"
echo 'Terminal 1: bench start'
echo 'Terminal 2: cd apps/student_crm/frontend && npm start'
