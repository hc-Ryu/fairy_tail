---
description: Cancel active Synod deliberation session
allowed-tools: [Bash]
---

# Cancel Synod Session

Run `synod-run cancel` (Git Bash: `synod-run.bat cancel`).
It marks the latest session in `.omc/synod/` as cancelled; partial results stay in the session directory.

Report the printed result to the user. If it reports no active session, say "활성 Synod 세션이 없습니다."
