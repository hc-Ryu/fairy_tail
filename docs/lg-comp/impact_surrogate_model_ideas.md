# Linear Compressor 밸브 Impact 고장모드 - Surrogate 모델 R² 개선 아이디어

> Synod 다중 에이전트 숙의 결과 (2026-03-12)
> 모드: idea | 신뢰도: 83.3%

---

## 문제 정의

- **대상:** Linear compressor 밸브의 impact 고장모드
- **목적:** 밸브 설계 파라미터 변화에 따른 최대 응력 변화를 나타내는 surrogate 모델 수립
- **현황:** Unique nodal 방식의 최대 응력을 QoI로 사용 시 R² ≈ 0
- **시도된 모델:** PDD, BNN, Kriging → 모두 결과 불량
- **시도된 QoI:** 단일 노드 최대 응력, 다중 노드 평균, 충돌 후 응력 적분(충격량) → 모두 불량

---

## 근본 원인 진단

### QoI 자체의 수학적 불연속성

"Unique nodal max stress"는 설계공간에서 **C0-불연속 함수**입니다.

- 설계변수가 연속적으로 변화하더라도, "최대응력이 발생하는 노드"가 불연속적으로 다른 위치로 jump합니다 (Node-jumping 현상)
- Kriging, BNN, PDD 등 모든 smooth surrogate는 불연속 함수를 피팅할 수 없습니다
- 샘플 수를 늘려도 해결되지 않습니다 → **Brute Force Fallacy**

**R² ≈ 0의 의미:** 데이터 평균값이 surrogate 모델보다 더 나은 예측값 → 모델이 noise만 학습 중

---

## 권장 아이디어 (우선순위 순)

### 1순위: QoI를 에너지/체적 기반으로 재정의

불연속 → 연속 변환이 핵심입니다. 단일 노드 값 대신 **공간 적분** 기반 QoI를 사용합니다.

| QoI | 설명 | 추천도 |
|-----|------|--------|
| **Stressed Volume** | von Mises 응력이 항복응력의 X%를 초과하는 체적 | ★★★★★ |
| **Strain Energy Density 상위 X% 적분** | 응력 집중 영역의 변형에너지 합산 | ★★★★ |
| **Critical Element 응력 평균** | 사전 정의된 위험 영역 요소의 평균 (고정 topology 기반) | ★★★ |
| **99th percentile 응력** | singular peak 필터링 효과 (구현 간단) | ★★★ |

**장점:**
- Node-jumping 문제가 근본적으로 해소됩니다
- 파단과 물리적으로 직접 연관 (에너지 = 파괴의 driving force)
- 기존 FEA 결과에서 후처리만 변경하면 적용 가능합니다

**실현 가능성:** High

---

### 2순위: 모달 특성을 중간 변수(Intermediate Feature)로 활용

설계변수 → **고유진동수** → 응력의 2단계 매핑으로 비선형성을 분리합니다.

**근거:**
- Impact 응답은 충격 pulse 주파수와 구조 고유진동수의 일치 여부에 크게 의존합니다
- Modal analysis는 impact 대비 비용이 100배 이상 저렴합니다
- 주파수 영역은 time-step phase 문제에 무관합니다

**적용 방법:**
1. 각 설계에 대해 Modal Analysis 수행
2. 1~5차 고유진동수 + 유효질량을 surrogate 입력 변수에 추가
3. (설계변수 + 모달 특성) → Kriging → QoI

**실현 가능성:** High (LS-DYNA, Abaqus 모두 modal 추출 간단)

---

### 3순위: POD/PCA 기반 응력장 분해 (Reduced-Order Model)

전체 응력장을 10~20개 모드로 압축하여 노드 노이즈를 필터링합니다.

**적용 방법:**
```
모든 FEA 결과의 응력장 → POD 분해 → 상위 10~20 모드 계수 추출
Surrogate가 계수를 예측 → 역변환으로 응력장 복원
복원된 응력장에서 QoI 추출
```

**장점:**
- 노드 단위 noise가 자동으로 필터링됩니다
- Deep Gaussian Process on POD coefficients = 고성능 조합
- Coefficients만 저장하면 되므로 저장 비용 부담이 적습니다

**단점:**
- 설계 topology 변화 시 reference mesh 정합 필요
- 추가 구현 필요 (pyROM, OpenTURNS 등 활용 가능)

**실현 가능성:** Medium

---

### 4순위: Multi-Fidelity Co-Kriging

저렴한 정적/준정적 해석으로 응력 추세를 파악하고, impact 해석은 "동적 보정계수" 학습에만 사용합니다.

- **저충실도(Low-fidelity):** 정적/준정적 해석 (빠르고 smooth한 response surface)
- **고충실도(High-fidelity):** Impact dynamics (비싸고 noisy)
- 동일 샘플 예산으로 더 정확한 surrogate 구성이 가능합니다

**실현 가능성:** Medium

---

## 즉시 적용 권장 순서

```
1단계 (즉시 시도) ──── 기존 FEA 결과에서 QoI 후처리만 변경
                        └─ Stressed Volume (von Mises > 0.8 × σ_yield) 계산
                        └─ R² 재확인 → 0.5 이상이면 방향 검증 완료

2단계 (보완) ─────────  모달 특성 추가
                        └─ 각 설계에 Modal Analysis 수행
                        └─ 고유진동수를 surrogate 입력에 추가

3단계 (고급) ─────────  POD + Deep Gaussian Process
                        └─ 1~2단계로도 R² 불충분한 경우 적용
```

---

## 주요 참고 키워드

실제 논문 검색 시 참고할 키워드입니다.

- `surrogate model impact stress QoI selection`
- `reduced order model valve FEA nonlinear`
- `stressed volume fatigue criterion surrogate`
- `proper orthogonal decomposition impact dynamics`
- `multi-fidelity kriging structural dynamics`

---

## 숙의 메타정보

| 항목 | 내용 |
|------|------|
| 세션 ID | synod-20260312-111457-f1e0cc |
| 모델 | Gemini flash (high thinking) + OpenAI gpt4o |
| Trust Score | Claude 2.0 / Gemini 2.0 / OpenAI 0.84 |
| 최종 신뢰도 | 83.3% |
| 핵심 합의 | QoI 불연속성이 R²≈0의 근본 원인 |
| 주요 쟁점 해결 | POD 저장 비용 → Coefficients만 저장으로 해결 |
