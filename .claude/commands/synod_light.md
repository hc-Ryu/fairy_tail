---
description: "Multi-agent deliberation with Claude, Gemini, and OpenAI"
argument-hint: "[mode] <prompt> | [mode] --select <prompt> | resume [session-id]"
allowed-tools: ["Read", "Write", "Bash", "Glob", "Grep", "Task"]
---

# /synod Command - Multi-Agent Deliberation System

## CRITICAL: ALWAYS ASK FOR MODEL SELECTION FIRST

**Before doing ANY processing, you MUST display the model selection prompt and wait for user input.**

---

## Phase 0: Model Selection (MANDATORY - DO THIS FIRST)

### Step 0.1: Parse Input

```
Extract from user input:
- MODE: first word if matches (review|design|debug|idea|general), else "general"
- PROBLEM: remaining text
```

### Step 0.2: STOP AND ASK - Model Selection Prompt

**YOU MUST DISPLAY THIS AND WAIT FOR USER RESPONSE:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 [Synod] 모드: {MODE}

📋 모델 선택 방식:

  1️⃣  자동 선택 (권장)
      └─ Gemini: {DEFAULT_GEMINI} | OpenAI: {DEFAULT_OPENAI}
  
  2️⃣  수동 선택 - 직접 모델을 선택합니다

👉 선택하세요 (1 또는 2): 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Default models by mode:**
| Mode | Gemini | OpenAI |
|------|--------|--------|
| review | flash | o3 |
| design | pro | o3 |
| debug | flash | o3 |
| idea | pro | gpt4o |
| general | flash | gpt4o |

### Step 0.3: Handle User Response

**If user selects 1 (자동):**
- Use default models for the mode
- Proceed to Phase 1

**If user selects 2 (수동):**
Display Gemini selection:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 Gemini 모델 선택:

  1️⃣  gemini-2.0-flash    ⚡ 빠름, 저렴
  2️⃣  gemini-2.0-pro      🧠 고급 추론
  3️⃣  gemini-2.5-flash    ⚡ 최신, 빠름
  4️⃣  gemini-2.5-pro      🧠 최신, 고급

👉 선택 (1-4): 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Then display OpenAI selection:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔵 OpenAI 모델 선택:

  1️⃣  gpt-4o       ⚡ 빠름, 저렴
  2️⃣  o3           🧠 고급 추론
  3️⃣  o3-mini      💰 비용 효율

👉 선택 (1-3): 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 0.4: Confirm and Proceed

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 설정 완료:

  🟢 Gemini:  {SELECTED_GEMINI}
  🔵 OpenAI:  {SELECTED_OPENAI}
  🟣 Claude:  claude-sonnet (orchestrator)

📝 문제: {PROBLEM}

세션 시작...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Phase 1-4: Execution (After Model Selection)

### Step 1: Parse Input

```
INPUT: {user's full input after /synod}

Extract:
- MODE: first word if matches (review|design|debug|idea|general), else "general"
- SELECT_FLAG: true if "--select" present
- PROBLEM: remaining text after mode and flags
```

### Step 2: Model Selection Flow

**If SELECT_FLAG is false (자동 선택):**
```
Display:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 [Synod] 모드: {MODE}
📋 모델 선택 방식을 선택하세요:

  1️⃣  자동 선택 (권장) - 모드에 최적화된 모델 조합
      └─ Gemini: {DEFAULT_GEMINI} | OpenAI: {DEFAULT_OPENAI}
  
  2️⃣  수동 선택 - 직접 모델을 선택합니다

선택 (1 또는 2, 기본값 1): 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**If SELECT_FLAG is true OR user selects option 2:**
```
Display Gemini Selection:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 Gemini 모델 선택:

  1️⃣  gemini-2.0-flash    ⚡ 빠름, 저렴
  2️⃣  gemini-2.0-pro      🧠 고급 추론
  3️⃣  gemini-2.5-flash    ⚡ 최신, 빠름
  4️⃣  gemini-2.5-pro      🧠 최신, 고급

선택 (1-4, 기본값 {DEFAULT}): 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Display OpenAI Selection:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔵 OpenAI 모델 선택:

  1️⃣  gpt-4o       ⚡ 빠름, 저렴
  2️⃣  o3           🧠 고급 추론
  3️⃣  o3-mini      💰 비용 효율

선택 (1-3, 기본값 {DEFAULT}): 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 3: Default Model Configuration by Mode

| Mode | Gemini Default | OpenAI Default | Gemini Thinking | OpenAI Reasoning |
|------|---------------|----------------|-----------------|------------------|
| review | flash (1) | o3 (2) | high | medium |
| design | pro (2) | o3 (2) | high | high |
| debug | flash (1) | o3 (2) | high | high |
| idea | pro (2) | gpt4o (1) | high | - |
| general | flash (1) | gpt4o (1) | medium | - |

### Step 4: Confirm Selection

```
Display:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 모델 설정 완료:

  🟢 Gemini:  {SELECTED_GEMINI}  (thinking: {THINKING_LEVEL})
  🔵 OpenAI:  {SELECTED_OPENAI}  (reasoning: {REASONING_LEVEL})
  🟣 Claude:  claude-3.5-sonnet  (orchestrator)

📝 문제: {PROBLEM_SUMMARY}
🔄 라운드: {TOTAL_ROUNDS}

세션 시작 중...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Model Mapping Reference

```python
GEMINI_MODELS = {
    "1": "flash",
    "2": "pro", 
    "3": "2.5-flash",
    "4": "2.5-pro"
}

OPENAI_MODELS = {
    "1": "gpt4o",
    "2": "o3",
    "3": "o3-mini"
}
```

---

## Phase 1-4: Execution

After model selection, proceed with the standard Synod phases:

1. **Phase 1: Solver Round** - Execute with selected models
2. **Phase 2: Critic Round** - Cross-validation
3. **Phase 3: Defense Round** - Adversarial debate
4. **Phase 4: Synthesis** - Final output

### Execution Commands

```bash
# Gemini execution with selected model
gemini-3 --model {SELECTED_GEMINI} --thinking {THINKING_LEVEL} \
         --temperature 0.7 < prompt.txt

# OpenAI execution with selected model
openai-cli --model {SELECTED_OPENAI} --reasoning {REASONING_LEVEL} \
           --temperature 0.7 < prompt.txt
```

---

## Quick Examples

```bash
/synod review 코드 리뷰
# → 모델 선택 프롬프트 표시
# → 사용자가 1 또는 2 선택
# → 세션 진행
```

---

## Session State

모델 선택 정보는 `meta.json`에 저장:

```json
{
  "session_id": "synod-20260131-143052-a1b",
  "mode": "review",
  "model_config": {
    "gemini": {
      "model": "flash",
      "thinking": "high",
      "selection": "manual"
    },
    "openai": {
      "model": "o3",
      "reasoning": "medium",
      "selection": "manual"
    }
  },
  "problem_summary": "..."
}
```

---

## Cost Estimation Display

수동 선택 시 예상 비용 표시:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 예상 비용:

  현재 선택:  Gemini Pro + o3
  예상 비용:  ~$0.35-0.50 / 세션
  
  비용 절약 옵션:
  └─ Gemini Flash + gpt-4o → ~$0.10-0.15 / 세션
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
