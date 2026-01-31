<p align="center">
  <img src="https://img.shields.io/badge/Claude_Code-Plugin-blueviolet?style=for-the-badge" alt="Claude Code Plugin"/>
  <img src="https://img.shields.io/badge/version-1.0.0-blue?style=for-the-badge" alt="Version"/>
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License"/>
</p>

<p align="center">
  <a href="README.md">English</a> | <a href="README.ko.md">한국어</a>
</p>

<h1 align="center">Synod</h1>

<p align="center">
  <strong>Claude Code를 위한 멀티 에이전트 심의 시스템</strong><br/>
  <em>Claude, Gemini, OpenAI 간의 구조화된 토론으로 더 나은 의사결정</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Claude-Anthropic-orange?style=flat-square" alt="Claude"/>
  <img src="https://img.shields.io/badge/Gemini-Google-blue?style=flat-square" alt="Gemini"/>
  <img src="https://img.shields.io/badge/GPT--4o-OpenAI-green?style=flat-square" alt="OpenAI"/>
</p>

---

## 왜 Synod인가?

> 단일 LLM은 **확증 편향**, **환각**, **과신** 문제를 겪습니다.
> Synod는 여러 AI 모델이 토론하고, 입장을 방어하고, 불확실성을 인정하도록 강제합니다.

```
┌─────────────────────────────────────────────────────────────────┐
│                         SYNOD 토론                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   라운드 1: SOLVER        라운드 2: CRITIC       라운드 3: DEFENSE
│   ┌─────────────┐          ┌─────────────┐        ┌─────────────┐
│   │   Gemini    │          │   Gemini    │        │   변호인    │
│   │   솔루션 A  │    →     │    비평     │   →    │  (Gemini)   │
│   └─────────────┘          └─────────────┘        └──────┬──────┘
│                                                          │
│   ┌─────────────┐          ┌─────────────┐        ┌──────▼──────┐
│   │   OpenAI    │          │   OpenAI    │        │    판사     │
│   │   솔루션 B  │    →     │    비평     │   →    │  (Claude)   │
│   └─────────────┘          └─────────────┘        └──────┬──────┘
│                                                          │
│                                                   ┌──────▼──────┐
│                                                   │    검사     │
│                                                   │  (OpenAI)   │
│                                                   └─────────────┘
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 빠른 시작

### 1. 설치

```bash
/plugin install quantsquirrel/claude-synod-debate
```

### 2. API 키 설정

```bash
export GEMINI_API_KEY="your-gemini-key"
export OPENAI_API_KEY="your-openai-key"
```

### 3. 토론 시작

```bash
/synod review  이 인증 플로우가 안전한가요?
/synod design  확장 가능한 마이크로서비스 아키텍처를 설계해주세요
/synod debug   이 레이스 컨디션이 왜 발생하나요?
```

---

## 기능

| 기능 | 설명 |
|------|------|
| **3라운드 구조화된 토론** | Solver → Critic → Defense/Prosecution |
| **신뢰도 점수** | 0-100 척도의 의미론적 포커스 (SID 방법론) |
| **신뢰 계산** | CortexDebate 공식: `(C × R × I) / S` |
| **반동조** | Free-MAD로 조기 합의 방지 |
| **세션 재개** | `/synod resume`으로 이전 토론 계속 |
| **5가지 전문 모드** | review, design, debug, idea, general |

---

## 모드

| 모드 | 용도 | 모델 | 라운드 |
|:----:|------|------|:------:|
| `review` | 코드 리뷰, 보안 분석 | Gemini Flash + GPT-4o | 3 |
| `design` | 아키텍처, 시스템 설계 | Gemini Pro + GPT-4o | 4 |
| `debug` | 문제 해결, 근본 원인 분석 | Gemini Flash + GPT-4o | 3 |
| `idea` | 브레인스토밍, 기능 아이디어 | Gemini Pro + GPT-4o | 4 |
| `general` | 일반 질문 | Gemini Flash + GPT-4o | 3 |

---

## 연구 기반

Synod는 피어 리뷰된 멀티 에이전트 토론 연구를 기반으로 합니다:

| 방법론 | 논문 | 기여 |
|--------|------|------|
| **ReConcile** | [ACL 2024](https://arxiv.org/abs/2309.13007) | 3라운드 수렴 패턴 |
| **AgentsCourt** | [2024](https://arxiv.org/abs/2408.08089) | 법정 스타일 적대적 토론 |
| **ConfMAD** | [2025](https://arxiv.org/abs/2502.06233) | 신뢰도 인식 소프트 디퍼 |
| **A-HMAD** | [AI & Ethics 2025](https://link.springer.com/article/10.1007/s44443-025-00353-3) | 인간과 유사한 심의 |

> 연구에 따르면 **3라운드 토론이 품질 향상의 95% 이상을 달성**하며, 이후로는 수익이 체감됩니다.

---

## 설치

### 사전 요구사항

- Claude Code CLI v1.0.0+
- Python 3.9+
- API 키: `GEMINI_API_KEY`, `OPENAI_API_KEY`

### 플러그인 설치 (권장)

```bash
/plugin install quantsquirrel/claude-synod-debate
```

### 수동 설치

```bash
git clone https://github.com/quantsquirrel/claude-synod-debate.git
cd synod
pip install -r requirements.txt
cp skills/*.md ~/.claude/commands/
chmod +x tools/*.py
export PATH="$PATH:$(pwd)/tools"
```

---

## 사용 예시

### 코드 리뷰
```bash
/synod review 이 재귀 함수의 성능 영향을 분석해주세요
```

### 아키텍처 설계
```bash
/synod design 리프레시 토큰을 포함한 JWT 인증 시스템을 설계해주세요
```

### 디버깅
```bash
/synod debug 이 테스트가 왜 불안정한가요? 로컬에서는 통과하지만 CI에서는 실패합니다
```

### 브레인스토밍
```bash
/synod idea 사용자 온보딩 전환율을 어떻게 개선할 수 있을까요?
```

### 이전 세션 재개
```bash
/synod resume                              # 가장 최근 세션
/synod resume synod-20260124-143022-a1b    # 특정 세션
```

---

## 출력 형식

각 에이전트는 구조화된 신뢰도 점수를 출력합니다:

```xml
<confidence score="85">
  <evidence>이 입장을 뒷받침하는 구체적인 증거</evidence>
  <logic>추론 체인</logic>
  <expertise>적용된 도메인 전문성</expertise>
  <can_exit>true</can_exit>
</confidence>

<semantic_focus>
1. 1차 주장
2. 2차 주장
3. 3차 주장
</semantic_focus>
```

### 점수 해석

| 점수 | 의미 | 조치 |
|:----:|------|------|
| **80+** | 높은 신뢰도 | 합의 준비 완료 |
| **60-79** | 중간 신뢰도 | 정제 필요 |
| **<60** | 낮은 신뢰도 | 추가 분석 필요 |

---

## 신뢰 점수 계산

Synod는 **CortexDebate** 공식을 사용하여 신뢰를 계산합니다:

```
T = min((C × R × I) / S, 2.0)
```

| 요소 | 설명 | 범위 |
|------|------|:----:|
| **C** (신뢰성) | 증거 품질 | 0-1 |
| **R** (신뢰도) | 논리적 일관성 | 0-1 |
| **I** (친밀성) | 문제 관련성 | 0-1 |
| **S** (자기 지향) | 편향 수준 (낮을수록 좋음) | 0.1-1 |

| 신뢰 수준 | 임계값 | 처리 |
|-----------|:------:|------|
| 높음 | T ≥ 1.5 | 1차 소스 |
| 좋음 | T ≥ 1.0 | 신뢰할 수 있는 입력 |
| 허용 가능 | T ≥ 0.5 | 주의하여 고려 |
| 제외 | T < 0.5 | 합성에서 제외 |

---

## 세션 관리

세션은 `~/.synod/sessions/`에 저장됩니다:

```
synod-YYYYMMDD-HHMMSS-xxx/
├── meta.json              # 세션 메타데이터
├── status.json            # 현재 상태
├── round-1-solver/        # Solver 출력
│   ├── gemini_response.json
│   └── openai_response.json
├── round-2-critic/        # Critic 출력
└── round-3-defense/       # Defense 출력
```

---

## 설정

### 환경 변수

```bash
# 필수
export GEMINI_API_KEY="your-gemini-key"
export OPENAI_API_KEY="your-openai-key"

# 선택
export SYNOD_SESSION_DIR="~/.synod/sessions"
export SYNOD_RETENTION_DAYS=30
```

### 커스텀 모델

`.claude/synod-config.json`에서 기본값 재정의:

```json
{
  "modes": {
    "review": { "solver": "gemini-2.0-flash", "critic": "gpt-4o" },
    "design": { "solver": "gemini-2.0-pro", "critic": "gpt-4-turbo" }
  }
}
```

---

## 문제 해결

| 문제 | 해결책 |
|------|--------|
| `API key not found` | `GEMINI_API_KEY`와 `OPENAI_API_KEY` 내보내기 |
| `Session directory error` | `mkdir -p ~/.synod/sessions` 실행 |
| `Command not found` | `/plugin install quantsquirrel/claude-synod-debate`로 설치 |
| `Timeout after retries` | 네트워크 및 API 서비스 상태 확인 |

### 타임아웃 처리

Synod는 우아한 성능 저하와 함께 자동 재시도를 포함합니다:

1. **첫 번째 타임아웃**: 지수 백오프로 재시도
2. **두 번째 타임아웃**: 모델 기능 다운그레이드
3. **세 번째 타임아웃**: 캐시된 응답 사용 또는 오류 반환

---

## 성능

| 지표 | 값 |
|------|-----|
| **토론 시간** | 2-5분 |
| **토큰 사용량** | 토론당 5,000-15,000 |
| **실행** | 라운드 내 병렬 처리 |
| **캐싱** | 최근 세션 캐시됨 |

---

## 기여하기

기여를 환영합니다!

```bash
git clone https://github.com/quantsquirrel/claude-synod-debate.git
cd synod
pip install -r requirements-dev.txt
pytest tests/
```

- [이슈 열기](https://github.com/quantsquirrel/claude-synod-debate/issues)
- [토론 참여](https://github.com/quantsquirrel/claude-synod-debate/discussions)

---

## 인용

```bibtex
@software{synod2026,
  title = {Synod: Multi-Agent Deliberation System for Claude Code},
  author = {quantsquirrel},
  year = {2026},
  url = {https://github.com/quantsquirrel/claude-synod-debate}
}
```

---

## 라이선스

MIT 라이선스 - 자세한 내용은 [LICENSE](LICENSE) 참조.

Copyright (c) 2026 quantsquirrel

---

<p align="center">
  <strong>다음 연구의 통찰력으로 구축됨</strong><br/>
  CortexDebate • Free-MAD • SID • ReConcile
</p>
