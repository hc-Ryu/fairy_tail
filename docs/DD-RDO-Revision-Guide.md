# DD-RDO 논문 수정사항 가이드

> 두 Synod 리뷰 세션(synod-20260212-161743, synod-20260212-170526)의 결과를 통합 정리
> 종합 신뢰도: 84% (6개 AI 모델 × 2세션, 총 12회 외부 API 호출)

---

## 수정사항 요약

| # | 심각도 | 대상 섹션 | 수정 내용 | 상태 |
|---|--------|----------|-----------|------|
| 1 | **필수** | Section 4.2, Eq.(2) | 표기 오류 수정 | [ ] |
| 2 | **필수** | Section 4.2 서두 | σ ∝ d 가정 명시 | [ ] |
| 3 | **필수** | score_space_transformation.pdf | Jacobian 항 보충 | [ ] |
| 4 | **권장** | Abstract / Introduction | "data-driven" 용어 재정의 | [ ] |
| 5 | **권장** | Section 4.2 | 적용 조건 3가지 명시 | [ ] |
| 6 | **권장** | score_space_transformation.pdf | 가우시안 밀도 예제 추가 | [ ] |
| 7 | **선택** | Section 4.2 | d_k 하한 설정 명시 | [ ] |
| 8 | **선택** | Section 7 (Conclusion) | 오차 전파 및 한계 서술 | [ ] |

---

## 1. [필수] Equation (2) 표기 수정

**위치**: DD-RDO.pdf, Section 4.2 "Score function for Design variables", Step 1

**현재 (오류)**:
$$\nabla_z \log f_Z(\mathbf{z};\mathbf{g}) = \nabla_x \log f_X(\mathbf{x};\mathbf{d}) \quad \cdots (2)$$

좌변은 z에 대한 미분, 우변은 x에 대한 미분으로 서로 다른 연산자를 등호로 연결. 6/6 모델 합의.

**수정안 A** (정확한 관계식으로 교체):
$$\nabla_z \log f_Z(\mathbf{z};\mathbf{g}) = \text{diag}(1/\mathbf{r}) \cdot \nabla_x \log f_X(\mathbf{x};\mathbf{d}) \quad \cdots (2)$$

**수정안 B** (중간 단계임을 명시):
기존 식 유지 + 아래 문구 추가:
> "여기서 좌변과 우변의 gradient 연산자는 각각 다른 변수 공간에 대한 것이며, 이는 log f_Z(z;g) = log f_X(x;d) − Σlog rᵢ 관계에서 상수항을 제거한 결과이다. Chain rule을 적용하면..."

**영향**: 후속 chain rule 결과 ∇_x log f_X = diag(r) · ∇_z log f_Z는 정확하므로 최종 공식에 영향 없음. 독자 이해도 개선 목적.

---

## 2. [필수] σ ∝ d 가정 명시

**위치**: DD-RDO.pdf, Section 4.2 서두 (Score function for Design variables 시작 부분)

**현재**: 가정이 명시적으로 서술되어 있지 않음. Section 2.3에서 scaling을 도입하지만, 이 scaling이 성립하기 위한 조건이 불명확.

**추가할 내용**:
```
본 절의 score space transformation은 다음 가정에 기반한다:

가정 4.1: 각 확률변수 X_k의 표준편차 σ_k는 설계변수 d_k에 비례한다.
즉, σ_k = α_k · d_k (α_k > 0은 상수).

이 가정 하에서 Z_k = X_k/d_k의 분포는 d에 무관하게 고정되며,
이는 score space transformation equation의 유도에 필수적이다.
```

**근거**: σ ∝ d가 아닌 경우(LogNormal with fixed σ, 일정 노이즈 플로어 등)에서 변환 공식이 부정확해짐. 3/3 모델, 2세션 모두 합의.

---

## 3. [필수] score_space_transformation.pdf에 Jacobian 항 보충

**위치**: score_space_transformation.pdf, Section 3 이후 (새로운 Section 3.1 또는 Section 4)

**현재**: 문서는 일반 함수 f(x)에 대해 sensitivity = -(x₀/d₁)·f'(x₀)를 유도. 이는 DD-RDO 공식의 **Shape 성분만** 포함.

**누락된 내용**: 확률밀도 함수에 적용 시 필요한 Jacobian(Volume) 성분

**추가할 절**:
```
3.1 확률밀도 함수에의 적용

확률변수 X의 밀도 p_X(x)를 Y = rX로 스케일링하면, 확률 보존에 의해:
p_Y(y) = (1/r) · p_X(y/r)

따라서 log-density는:
log p_Y(y) = log p_X(y/r) − log r

f = log p_X로 설정하면 본 문서의 결과에 추가 항이 발생한다:

(1) Shape 성분 (본 문서 Section 3의 결과):
    ∂/∂d₂ [log p_X(d₁/d₂ · y)]|_{d₂=d₁} = -(x₀/d₁) · S_X(x₀)

(2) Volume 성분 (Jacobian):
    ∂/∂d₂ [−log(d₂/d₁)]|_{d₂=d₁} = −1/d₁

합산하면 완전한 score space transformation:
    S_d(x₀) = −(1/d₁)(1 + x₀ · S_X(x₀))

이는 DD-RDO 논문의 Score Space Transformation Equation과 일치한다.
```

**추가 예제 (가우시안)**:
```
예제 2: f(x) = log N(x; d₁, σ²)

f'(x) = −(x − d₁)/σ², d₁ = 2, σ = 0.3, x₀ = 2.5

Shape: −(2.5/2) · (−(2.5−2)/0.09) = −1.25 · (−5.556) = 6.944
Volume: −1/2 = −0.5
합산: 6.944 + (−0.5) = 6.444

검증: S_d = −(1/2)(1 + 2.5 · (−5.556)) = −(0.5)(1 − 13.889) = 6.444 ✓
```

---

## 4. [권장] "Data-driven" 용어 재정의

**위치**: DD-RDO.pdf, Abstract 및 Section 1 (Introduction)

**현재**: "data-driven method"로 기술되어, 분포에 대한 사전 가정이 전혀 없는 것처럼 읽힘.

**문제**: Score space transformation 자체가 σ_k ∝ d_k 구조를 전제하므로, 완전한 distribution-free가 아님.

**수정안**:

| 현재 표현 | 수정 제안 |
|-----------|-----------|
| "data-driven method" | "semi-parametric data-driven method" |
| "no presumed distribution forms" | "no presumed parametric distribution forms, under proportional variance structure" |
| "분포 정보가 불완전하거나 미지인 상황" | "분포의 해석적 형태가 미지이나, 분산-평균 비례 구조가 성립하는 상황" |

---

## 5. [권장] 적용 조건 3가지 명시

**위치**: DD-RDO.pdf, Section 4.2 또는 Section 6 (Practical Example) 서두

**추가할 내용**:
```
Score Space Transformation Equation의 적용 조건:

(C1) d_k > 0: 설계변수가 양수 (1/d_k 발산 방지)
(C2) σ_k = α_k · d_k: 표준편차가 평균에 비례 (Z 분포의 d-불변성)
(C3) 유한 모멘트: E[X_k], Var[X_k]가 존재 (score function의 well-definedness)

조건 (C3)에 의해 Cauchy, Pareto(β≤2) 등 heavy-tailed 분포는 적용 대상에서 제외된다.
```

---

## 6. [권장] 가우시안 밀도 예제 추가

**위치**: score_space_transformation.pdf, Section 5 (Example)에 추가

**목적**: 기존 f(x)=x² 예제는 밀도 함수가 아니어서 Jacobian 항의 필요성이 드러나지 않음. 가우시안 밀도 예제를 통해 Shape + Volume = DD-RDO 공식임을 수치적으로 검증.

**내용**: 수정사항 #3의 "예제 2" 참조.

---

## 7. [선택] d_k 하한 설정 명시

**위치**: DD-RDO.pdf, Section 6 (Practical Example) 또는 Section 2.2

**추가할 내용**:
```
수치 안정성을 위해 설계변수에 하한을 설정한다:
d_{k,L} ≥ ε > 0 (예: ε = 0.01)

이는 Score Space Transformation Equation의 1/d_k 항에 의한
수치적 발산을 방지한다.
```

**근거**: d_k → 0에서 S_d → ∞로 발산. 최적화 알고리즘의 설계변수 범위 제약으로 자연스럽게 해결되나, 명시적 언급이 논문의 완결성을 높임.

---

## 8. [선택] 오차 전파 및 한계 서술 보강

**위치**: DD-RDO.pdf, Section 7 (Conclusion)

**현재**: "instability in training the neural network" 언급만 있음.

**보강할 내용**:
```
본 방법의 한계:

(1) Score matching 추정 오차의 전파: Neural network으로 추정한
    S_X(x)의 오차 δ가 변환 후 (x/d) · δ로 증폭될 수 있다.
    특히 |x/d| >> 1인 분포의 꼬리 영역에서 증폭이 심화됨.

(2) σ ∝ d 가정의 범위: 본 방법은 변동계수(CV = σ/d)가
    일정한 분포에 적합하다. 일정 분산(σ = const) 또는
    비선형 σ(d) 관계를 가진 문제에는 확장이 필요하다.

(3) 다변량 상관관계: 현재 Score Space Transformation은
    대각 스케일링(diagonal scaling)만 다루며, 비대각 공분산
    구조에 대한 확장이 향후 과제이다.
```

---

## 수정 우선순위 로드맵

```
Phase 1 (필수 - 수학적 정확성):
  ├─ #1 Eq.(2) 표기 수정
  ├─ #2 σ ∝ d 가정 명시
  └─ #3 Jacobian 항 보충 (score_space_transformation.pdf)

Phase 2 (권장 - 논문 완결성):
  ├─ #4 "data-driven" 용어 재정의
  ├─ #5 적용 조건 명시
  └─ #6 가우시안 예제 추가

Phase 3 (선택 - 실무 보완):
  ├─ #7 d_k 하한 명시
  └─ #8 한계 서술 보강
```

---

*통합 리뷰 기반: Synod v1.0.1 × 2세션*
*DD-RDO Review (83%) + Score Space Transformation Review (85%)*
