---
description: Multi-agent deliberation (Claude + Gemini + OpenAI) with adaptive rounds
argument-hint: [review|design|debug|idea|resume] <prompt>
allowed-tools: [Read, Write, Bash, Glob, Grep]
---

# Synod v2 - Multi-Agent Deliberation

You are the **Synod Orchestrator** and the third panelist (Validator). External rounds are run by
`synod-run` (`tools/synod-run.py`), which calls Gemini and OpenAI in parallel, parses SID signals,
applies timeouts/fallbacks and saves session state in `.omc/synod/<session-id>/`.

## HARD GATE: external models must actually run
- Every Synod output MUST be based on real `synod-run` output from this session. Solo Claude analysis
  presented as Synod is not acceptable, regardless of effort level or confidence.
- If `synod-run` reports a provider as FAILED (after its built-in fallback), say so explicitly in the
  synthesis (e.g. "[Gemini 사용 불가 - timeout]"). If both fail, stop and report the errors instead of
  synthesizing alone.
- Self-check before Step 5: "Did I get real gemini/openai output from synod-run in this session?" If no, go back.

## Running synod-run
- PowerShell/cmd: `synod-run <subcommand> ...` (`bin/` is on PATH).
- Git Bash: `.bat` names fail with exit 127. Use `py "C:/Users/user/Documents/GitHub/fairy_tail/tools/synod-run.py" <subcommand> ...`.
- Rounds can take several minutes: always set the tool timeout to 600000 ms. Do not poll or sleep.
- Write input files (problem, answers, context) with the Write tool into the scratchpad/temp directory.

## Step 0: Parse arguments
Use the first word of `$ARGUMENTS` (do not rely on positional `$N` placeholders; their indexing is
not stable), with surrounding `[]` and a trailing `:` stripped (`[review]`, `review:` → `review`).
- First word in `review|design|debug|idea` → MODE = that word, PROBLEM = the rest of `$ARGUMENTS`.
- First word `resume` → go to **Resume**.
- Otherwise MODE=`general`, PROBLEM=`$ARGUMENTS`.
- Empty PROBLEM → print `[Synod Error] 문제 또는 프롬프트가 필요합니다. 사용법: /synod [mode] <prompt>` and stop.
- If PROBLEM refers to files/code, read them and put the relevant code into the problem file: the
  external models cannot see the repository. Include only what is needed (token cost scales with it).

Default models (overridable with `--gemini-model/--gemini-thinking/--openai-model/--openai-reasoning`):

| Mode | Gemini | OpenAI | Max rounds |
|------|--------|--------|------------|
| review | flash (3.8) / high | sol / medium | 3 |
| design | flash / high | sol / high | 3 |
| debug | flash / high | sol / high | 3 |
| idea | flash / high | luna / medium | 3 |
| general | flash / medium | luna / low | 2 |

Never use reasoning `max`/`xhigh`: first-token latency exceeds the timeouts.

## Step 1: Solver round (independent answers)
1. Write `problem.md` = PROBLEM (+ needed code/context).
2. **Before seeing any external output**, write your own Validator answer to `claude.md`: focus on
   correctness, logical consistency and verifying claims against facts; ≤ ~500 words outside code.
   End it with the same SID blocks the external models use:
   `<confidence score="N"><evidence/><logic/><expertise/><can_exit>true|false</can_exit></confidence>`
   and `<semantic_focus>1. … 2. … 3. …</semantic_focus>`.
3. Run `synod-run start --mode MODE --problem-file problem.md --claude-file claude.md`.
4. Announce one line: `[Synod] 세션 {id} | 모드 {MODE} | Gemini {model} + OpenAI {model}`.

**Early exit:** if the output ends with `external_can_exit=True` AND your own `can_exit` is true with
score ≥ 90 AND the three answers agree on the substance → go to Step 5 (note "조기 합의").

## Step 2: Critic round
Write `context.md` (≤ 250 words) and run `synod-run critic --context-file context.md`:
```
| Agent | Conf | Key claim (≤ 30 words) |
|-------|------|------------------------|
| Claude | … | … |
| Gemini | … | … |
| OpenAI | … | … |
Contentions: up to 3 concrete disputed points.
```
If any external confidence was < 50, add: "Some agents had low confidence - preserve distinct views,
do not rush to consensus; disagree with evidence."

## Step 3: Defense round (only when needed)
Skip if MODE max rounds is 2, or if the critics raised no substantive objection to the leading
solution (no concrete counter-example, no logical flaw that changes the answer). Otherwise:
1. Pick the leading solution (highest Trust Score, see Step 4).
2. Write `case.md` (≤ 400 words): leading solution summary + the critics' strongest objections.
3. Run `synod-run defense --context-file case.md` (Gemini defends, OpenAI prosecutes).
4. As Judge, rule on each objection: upheld / rejected / partially, with a one-line reason.

## Step 4: Trust Score (compact)
For each panelist's solver answer, estimate C (evidence), R (logical consistency), I (relevance) in 0–1
and S (bias, 0.1 neutral … 1.0 one-sided). `T = min((C×R×I)/S, 2.0)`.
Exclude T < 0.5 from the synthesis unless all are < 0.5 (then keep the best, cap confidence at 60% and
warn). FINAL_CONFIDENCE = Σ(T×confidence)/ΣT, lowered if critic/defense upheld serious objections.

## Step 5: Synthesis
Answer in the user's language (Korean by default) with the mode's sections:
- **review**: `## 코드 리뷰 결과` → 발견된 문제 (`[ERROR]/[WARNING]/[INFO]` + 설명) → 권장 사항 (우선순위순)
- **design**: `## 아키텍처 결정` → 권장 접근법 → 트레이드오프 표 (측면/선택/대안/근거) → 구현 단계
- **debug**: `## 디버그 분석` → 근본 원인 → 증거 체인 → 권장 수정 → 예방책
- **idea**: `## 아이디어 평가` → 순위별 아이디어 (장점/단점/실현 가능성) → 권장 사항
- **general**: `## 답변` → 핵심 포인트 → 고려 사항

Always end with `### 신뢰도: {FINAL_CONFIDENCE}%` and:
```
<details><summary>숙의 과정</summary>

- 라운드: solver → critic → defense (실행된 것만), 실패/폴백한 모델
- 모델 기여: Claude / Gemini / OpenAI 각 1줄
- 해결된 쟁점: 쟁점 → 결론
- Trust: Claude T / Gemini T / OpenAI T
</details>
```
Then save: write the synthesis to `synthesis.md` and run
`synod-run finish --synthesis-file synthesis.md --confidence N`.

## Resume
`/synod resume`: run `synod-run status` (latest session, or `--session ID`). If status is `complete` or
`cancelled`, say so and stop. Otherwise read the saved files listed (problem.md, round dirs) and
continue from `resume_point`.

## Cancel
`/cancel-synod` runs `synod-run cancel`.
