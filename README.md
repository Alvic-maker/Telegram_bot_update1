# Bot update pack (fixed)
This package contains:
- bot.py (fixed newline escaping and formatting)
- .github/workflows/main.yml (cron adjusted for VN timezone; ensure file is on default branch)
- requirements.txt

Important:
- Put these files into the repository root. The workflow file must be at .github/workflows/main.yml on the repository's default branch (usually 'main' or 'master').
- GitHub scheduled workflows run **only** on the repository's default branch.
- Make sure Actions are enabled for the repo and the workflow is not disabled.
