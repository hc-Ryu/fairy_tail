# B-pillar 설계를 위한 제약 인식 그래프 신경망(CGNN) 아키텍처

## 1. 개요 및 문제 정의

### 1.1 문제 배경
자동차 B-pillar는 차량의 측면 충돌 안전성을 담당하는 핵심 구조 부재입니다. 설계 시 다음과 같은 상충하는 요구사항을 동시에 만족해야 합니다:

- **강도 목표**: 특정 전소성 모멘트(Full Plastic Moment, Mp) 값을 달성하여 충격 에너지 흡수성능 확보
- **간섭 방지**: 다층 단면 구조(Inner/Reinforcement/Outer 파트)에서 부품 간 겹침 현상 제거
- **경량화**: 단면 두께와 형상을 최적화하여 전체 면적 최소화
- **형태 보존**: 기본 골격을 유지하면서 제약 조건 만족

### 1.2 제안 방법론: CGNN (Constraint-aware Graph Neural Network)
본 아키텍처는 다음과 같은 특징을 가집니다:

1. **그래프 기반 표현**: B-pillar 단면을 노드(좌표)와 엣지(연결)로 구성된 그래프로 모델링
2. **조건부 생성**: FiLM(Feature-wise Linear Modulation) 기법으로 목표 Mp 조건을 신경망에 주입
3. **물리 기반 역전파**: 미분 가능한 PNA 솔버로 암묵적 함수 정리(Implicit Function Theorem, IFT)를 통해 물리량 기반 그래디언트 계산
4. **다목적 최적화**: 강도, 형태, 간섭 방지, 경량화를 포함한 5개 손실 함수를 가중 결합

---

## 2. 전체 설계 프로세스

### 2.1 시스템 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        입력 데이터 준비 단계                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  노드 특징 (x)                 엣지 특징 (edge_attr)                    │
│  ├─ 좌표 (x, y)               ├─ 선분 길이 (L)                         │
│  ├─ 고정 플래그 (is_fixed)    ├─ 각도 (θ)                             │
│  ├─ 파트 ID (part_id)         ├─ 층 ID (section_id)                   │
│  ├─ 층 ID (section_id)        └─ 플랜지 여부 (flange)                 │
│  ├─ 두께 (t)                                                            │
│  └─ 항복강도 (fy)             목표 전소성 모멘트: target_mp [1, 1]    │
│                                                                          │
└─────────────────┬───────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   신경망 기반 변위 예측 단계 (CGDN)                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │  1. Node Encoder: [6] → [128]                           │           │
│  │     입력 노드 특징을 숨겨진 표현으로 변환               │           │
│  └──────────────────────┬───────────────────────────────────┘           │
│                         │                                               │
│  ┌──────────────────────▼───────────────────────────────────┐           │
│  │  2. FiLM Generator: target_mp [1, 1] → (γ, β) [1, 128] │           │
│  │     목표 Mp를 조건 파라미터로 변환                      │           │
│  └──────────────────────┬───────────────────────────────────┘           │
│                         │                                               │
│  ┌──────────────────────▼───────────────────────────────────┐           │
│  │  3. Message-Passing Blocks (4 iterations)               │           │
│  │     ├─ GATv2Conv: 주변 노드 정보 집계                   │           │
│  │     ├─ FiLM Modulation: γ ⊙ h + β (조건 주입)          │           │
│  │     ├─ LayerNorm: 안정성 증대                           │           │
│  │     ├─ GELU: 비선형 활성화                              │           │
│  │     └─ Residual: 기본 정보 보존                         │           │
│  └──────────────────────┬───────────────────────────────────┘           │
│                         │                                               │
│  ┌──────────────────────▼───────────────────────────────────┐           │
│  │  4. Coordinate Decoder: [128] → [2]                    │           │
│  │     ├─ 예측 변위: Δx, Δy                               │           │
│  │     ├─ 클리핑: |Δ| ≤ 50mm (안정성)                     │           │
│  │     └─ 고정점 제약: is_fixed 노드는 Δ = 0              │           │
│  └──────────────────────┬───────────────────────────────────┘           │
│                         │                                               │
└─────────────────────────┼───────────────────────────────────────────────┘
                          │
                          ▼ new_coords = x[:, :2] + delta_coords
┌─────────────────────────────────────────────────────────────────────────┐
│                    물리 기반 평가 및 역전파 단계                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │  A. Implicit PNA Solver (층별 반복)                     │           │
│  │     ├─ Bisection: 인장력 = 압축력 평형점 탐색          │           │
│  │     ├─ IFT: 암묵적 함수 정리로 y_pna에 대한 그래디언트│           │
│  │     └─ 전소성 모멘트: Mp = Σ A·fy·|y - y_pna|         │           │
│  └──────────────────────┬───────────────────────────────────┘           │
│                         │                                               │
│  ┌──────────────────────▼───────────────────────────────────┐           │
│  │  B. 제약 손실 함수 계산 (5개)                           │           │
│  │     ├─ L_phys: |Mp_pred - Mp_target|² / Mp_target²     │           │
│  │     ├─ L_smooth: 노드 간 거리 변화 제곱                │           │
│  │     ├─ L_collision: 파트 간 Y좌표 간섭 검사            │           │
│  │     ├─ L_mass: 단면적 최소화 (Σ L·t)                   │           │
│  │     └─ L_fix: 고정점 변위 억제 (hard constraint)       │           │
│  └──────────────────────┬───────────────────────────────────┘           │
│                         │                                               │
│  ┌──────────────────────▼───────────────────────────────────┐           │
│  │  C. 가중 손실 합산                                      │           │
│  │     Loss = w_phys·L_phys + w_smooth·L_smooth           │           │
│  │            + w_collision·L_collision + w_mass·L_mass   │           │
│  │            + w_fix·L_fix                                │           │
│  └──────────────────────┬───────────────────────────────────┘           │
│                         │                                               │
└─────────────────────────┼───────────────────────────────────────────────┘
                          │
                          ▼ loss.backward()
┌─────────────────────────────────────────────────────────────────────────┐
│                      신경망 가중치 업데이트                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ∂Loss / ∂w를 계산하고 옵티마이저로 가중치 w 갱신                      │
│                                                                          │
│  → 다음 배치로 반복                                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 훈련 루프의 세부 단계 (train_step 함수)

#### **단계 1: 데이터 준비 및 특징 추출**
```
입력: data (PyTorch Geometric Data 객체)
  ├─ data.x: [N, 7] → [x, y, is_fixed, part_id, section_id, t, fy]
  ├─ data.edge_index: [2, E]
  ├─ data.edge_attr: [E, 4]
  └─ target_mps: dict {section_id → target_mp_value}

처리:
  is_fixed_mask = data.x[:, 2].bool()           # 고정점 식별
  part_ids = data.x[:, 3]                       # 파트 ID (1=Outer, 2=Reinf, 3=Inner)
  section_ids = data.x[:, 4]                    # 층 ID (1, 2, 3 등)
  t = data.x[:, 5]                              # 두께 [N]
  fy = data.x[:, 6]                             # 항복강도 [N]

층별 목표 Mp 텐서 생성:
  target_mp_node = [N, 1] 텐서
  └─ 각 노드를 자신이 속한 층의 목표 Mp로 초기화
```

#### **단계 2: 신경망 순전파 (Forward Pass)**
```
입력: 
  x [N, 6]: 노드 특징 (고정점 정보 제외)
  edge_index, edge_attr: 그래프 연결
  target_mp_node [N, 1]: 층별 목표 Mp
  is_fixed_mask [N, 1]: 고정점 마스크

CGDN 모델 실행:
  new_coords, delta_coords = model(x, edge_index, edge_attr, 
                                    target_mp_node, is_fixed_mask)

반환값:
  new_coords [N, 2]: 변형된 좌표 = x[:, :2] + delta_coords
  delta_coords [N, 2]: 예측된 변위
```

#### **단계 3: 층별 물리량 계산 (Layer-wise Physics)**
```
각 층 section ∈ {1, 2, 3, ...}에 대해:

1) 층 내 노드만 추출:
   coords_section = new_coords[section_mask, :2]
   t_section = t[section_mask]
   fy_section = fy[section_mask]

2) Implicit PNA Solver 호출:
   pred_mp_section = calculate_mpl(coords_section, t_section, 
                                    fy_section, None)
   
   내부 동작:
   ├─ Bisection으로 y_pna 탐색 (30회)
   ├─ 전소성 모멘트 계산: Mp = Σ A·fy·|y - y_pna|
   └─ IFT로 ∂Mp/∂coords 계산 (역전파용)

3) 목표 대비 오차 계산:
   target_mp_section = target_mps[section_id]
   l_phys_section = (pred_mp_section - target_mp_section)² / target_mp_section²
   
   l_phys_total += l_phys_section

최종: l_phys_total = (1 / num_sections) × Σ l_phys_section
```

#### **단계 4: 제약 손실 함수 계산 (Multi-objective Loss)**
```
A. 형상 매끄러움 손실 (Smoothness):
   L_smooth = mean(||coords[src] - coords[dst]||²)
   
   역할: 연결된 노드 사이 거리 변화를 최소화하여 단면 형태의 급격한 변화 방지

B. 간섭 방지 손실 (Collision):
   각 층 lvl에 대해:
   
   조건 1: Inner(p_id=3) vs Reinf(p_id=2) 검사
   └─ gap_3_2 = max(0, max(y_inner) - min(y_reinf) + margin)
      L_collision += gap_3_2²
   
   조건 2: Reinf(p_id=2) vs Outer(p_id=1) 검사
   └─ gap_2_1 = max(0, max(y_reinf) - min(y_outer) + margin)
      L_collision += gap_2_1²
   
   조건 3: Reinf가 없는 층에서 Inner vs Outer 직접 검사
   └─ gap_3_1 = max(0, max(y_inner) - min(y_outer) + margin)
      L_collision += gap_3_1²
   
   margin = 0.5mm (최소 안전 간격)
   
   역할: 내부 파트가 외부 파트를 침범하지 못하도록 강제

C. 경량화 손실 (Mass):
   seg_len = ||coords[src] - coords[dst]||  # 각 선분 길이
   area = Σ (seg_len × t[src])
   
   L_mass = area
   
   역할: 전체 단면적(무게 대리변수)을 최소화

D. 고정점 보존 손실 (Fixed Constraint):
   if is_fixed_mask.any():
       L_fix = Σ ||delta_coords[fixed_nodes]||
   else:
       L_fix = 0
   
   역할: 고정점의 변위를 억제하여 기본 골격 유지 강제
```

#### **단계 5: 최종 손실 및 역전파**
```
가중 손실 합산:
Loss = w_phys × L_phys
     + w_smooth × L_smooth
     + w_mass × L_mass
     + w_collision × L_collision
     + w_fix × L_fix

기본 가중치:
  w_phys = 1000.0       # 강도 목표 달성이 최우선
  w_smooth = 0.01       # 미세 조정 역할
  w_mass = 0.0001       # 경량화는 부차적
  w_collision = 50.0    # 간섭 방지는 중요한 하드 제약
  w_fix = 100.0         # 형태 보존도 중요

역전파:
  loss.backward()       # 자동 미분으로 ∂Loss/∂(모든 파라미터) 계산
  optimizer.step()      # 그래디언트 기반 가중치 업데이트

반환 통계:
  {
    "loss": 최종 손실값
    "pred_mp": [n_sections] 각 층의 예측 Mp 값
    "l_phys": 물리 손실
    "l_smooth": 매끄러움 손실
    "l_mass": 경량화 손실
    "l_collision": 간섭 손실
    "l_fix": 고정점 손실
    "new_coords": 최종 좌표 (역전파용 그래프에서 분리)
  }
```

---

## 3. 핵심 물리 엔진: ImplicitPNASolver

### 3.1 PNA (Plastic Neutral Axis) 개념

B-pillar의 강도는 전소성 모멘트(Full Plastic Moment)로 평가됩니다. 이는 다음과 같이 정의됩니다:

**전소성 모멘트 정의:**
$$M_p = \sum_{i=1}^{N} A_i \cdot f_y^i \cdot d_i$$

여기서:
- $A_i$: i번째 노드의 단위 길이 단면적 (= 두께 $t_i$)
- $f_y^i$: i번째 노드의 항복강도
- $d_i$: i번째 노드와 소성 중립축(PNA) 사이의 거리 = $|y_i - y_{PNA}|$

**PNA의 물리적 의미:**
PNA는 인장력과 압축력이 정확히 평형을 이루는 수평선입니다:

$$F_{tension} = F_{compression}$$

$$\sum_{y_i > y_{PNA}} t_i \cdot f_y^i \cdot (y_i - y_{PNA}) = \sum_{y_i < y_{PNA}} t_i \cdot f_y^i \cdot (y_{PNA} - y_i)$$

### 3.2 Forward Pass: Bisection Method로 PNA 탐색

```python
알고리즘: ImplicitPNASolver.forward(coords, t, fy, edge_index, n_iter=30)

입력:
  coords [N, 2]:     노드 좌표 (x, y)
  t [N, 1]:         두께
  fy [N, 1]:        항복강도
  edge_index:       사용하지 않음 (인터페이스 유지)
  n_iter = 30:      이분탐색 반복 횟수

처리:

1. 초기화 (no_grad 블록):
   y = coords[:, 1]           # 모든 노드의 Y좌표
   y_lo = min(y)              # 탐색 범위 하한
   y_hi = max(y)              # 탐색 범위 상한

2. 이분탐색 (30회 반복):
   while iteration < 30:
       y_mid = (y_lo + y_hi) / 2
       
       # 인장력 계산 (PNA 위의 노드들)
       F_tens = Σ t[i]·fy[i]·max(0, y[i] - y_mid)
       
       # 압축력 계산 (PNA 아래의 노드들)
       F_comp = Σ t[i]·fy[i]·max(0, y_mid - y[i])
       
       # 이진 판정
       if F_tens > F_comp:
           y_lo = y_mid      # PNA가 y_mid보다 위에 있음
       else:
           y_hi = y_mid      # PNA가 y_mid보다 아래에 있음

3. 최종 PNA:
   y_pna = (y_lo + y_hi) / 2  # 수렴된 중립축

4. 전소성 모멘트 계산:
   d = |coords[:, 1] - y_pna|         # 각 노드의 중립축 거리
   area = t.squeeze(-1)                # 단면적
   M_p = Σ area[i] · fy[i] · d[i]
   
   반환: M_p (scalar tensor)

메모리 저장 (역전파용):
   ctx.save_for_backward(coords, t, fy, y_pna.unsqueeze(0), edge_index)
```

**이분탐색 수렴 분석:**
- 초기 범위: [min(y), max(y)]
- 각 반복에서 범위가 절반으로 축소
- 30회 반복 후 오차: (max(y) - min(y)) / 2^30 ≈ 0 (매우 정밀)
- 계산 복잡도: O(30 × N) = O(N)

### 3.3 Backward Pass: 암묵적 함수 정리(IFT)를 통한 그래디언트 계산

#### **문제 정의:**
이분탐색 알고리즘은 미분 불가능합니다. 따라서 직접 미분할 수 없으므로, 암묵적 함수 정리(Implicit Function Theorem, IFT)를 사용합니다.

**평형 조건 (암묵적 함수):**
$$g(y_{PNA}, \text{coords}) = F_{tens} - F_{comp} = 0$$

이를 전개하면:
$$g(y_{PNA}, y_1, y_2, \ldots, y_N) = \sum_{i: y_i > y_{PNA}} t_i f_y^i (y_i - y_{PNA}) - \sum_{i: y_i < y_{PNA}} t_i f_y^i (y_{PNA} - y_i) = 0$$

#### **IFT 적용:**
암묵적 함수 정리에 의해, $g = 0$을 만족하는 implicit function $y_{PNA}(y_1, \ldots, y_N)$에 대해:

$$\frac{\partial y_{PNA}}{\partial y_i} = -\frac{\partial g / \partial y_i}{\partial g / \partial y_{PNA}}$$

#### **각 편미분 항 계산:**

**1) $\partial g / \partial y_{PNA}$ 계산:**

평형식 $g = \sum t_i f_y^i \cdot \text{clamp}(y_i - y_{PNA}, 0) - \sum t_i f_y^i \cdot \text{clamp}(y_{PNA} - y_i, 0)$

를 $y_{PNA}$로 미분하면:

$$\frac{\partial g}{\partial y_{PNA}} = -\sum_{y_i > y_{PNA}} t_i f_y^i - \sum_{y_i < y_{PNA}} t_i f_y^i = -\sum_i t_i f_y^i$$

이 값은 항상 **음수**입니다 (안정성).

```python
dg_dy_pna = -torch.sum(t_flat * fy_flat)  # scalar, always < 0
```

**2) $\partial g / \partial y_i$ 계산:**

i번째 노드가 인장 상태 ($y_i > y_{PNA}$)일 때:
$$\frac{\partial g}{\partial y_i} = +t_i f_y^i$$

i번째 노드가 압축 상태 ($y_i < y_{PNA}$)일 때:
$$\frac{\partial g}{\partial y_i} = -t_i f_y^i$$

부호를 통일하면 ($s_i = \text{sign}(y_i - y_{PNA})$):
$$\frac{\partial g}{\partial y_i} = s_i \cdot t_i \cdot f_y^i$$

```python
s = torch.sign(y - y_pna)          # [N]: +1 또는 -1
dg_dy = s * t_flat * fy_flat       # [N]
```

**3) IFT 공식:**
$$\frac{\partial y_{PNA}}{\partial y_i} = -\frac{s_i \cdot t_i \cdot f_y^i}{-\sum_j t_j f_y^j} = \frac{s_i \cdot t_i \cdot f_y^i}{\sum_j t_j f_y^j}$$

```python
dy_pna_dy = -dg_dy / (dg_dy_pna + 1e-12)  # [N], 수치 안정성을 위해 epsilon 추가
```

#### **전소성 모멘트의 기울기 계산:**

$M_p = \sum_i A_i f_y^i |y_i - y_{PNA}|$를 $y_i$로 미분하면:

**직접 항 (Direct effect):**
$$\frac{\partial M_p}{\partial y_i}\bigg|_{\text{direct}} = A_i f_y^i \cdot \text{sign}(y_i - y_{PNA}) = t_i f_y^i \cdot s_i$$

**간접 항 (Indirect effect via PNA):**

PNA가 이동하면 모든 노드의 거리 $d_i$가 변합니다:

$$\frac{\partial M_p}{\partial y_i}\bigg|_{\text{indirect}} = \sum_j \frac{\partial M_p}{\partial y_{PNA}} \cdot \frac{\partial y_{PNA}}{\partial y_i}$$

여기서:
$$\frac{\partial M_p}{\partial y_{PNA}} = -\sum_j t_j f_y^j \cdot \text{sign}(y_j - y_{PNA}) = -\sum_j t_j f_y^j \cdot s_j$$

따라서:
$$\frac{\partial M_p}{\partial y_i}\bigg|_{\text{indirect}} = -\sum_j t_j f_y^j s_j \cdot \frac{\partial y_{PNA}}{\partial y_i}$$

```python
direct = t_flat * fy_flat * s                           # [N]
indirect = -torch.sum(t_flat * fy_flat * s) * dy_pna_dy  # [N]
dMp_dy = direct + indirect
```

#### **최종 그래디언트 전파:**

```python
def backward(ctx, grad_output):
    # 모든 저장된 텐서 복원
    coords, t, fy, y_pna_buf, edge_index = ctx.saved_tensors
    y_pna = y_pna_buf.squeeze(0)
    
    # 위의 모든 계산 수행
    dg_dy_pna = -torch.sum(t_flat * fy_flat)
    dg_dy = s * t_flat * fy_flat
    dy_pna_dy = -dg_dy / (dg_dy_pna + 1e-12)
    
    direct = t_flat * fy_flat * s
    indirect = -torch.sum(t_flat * fy_flat * s) * dy_pna_dy
    dMp_dy = direct + indirect
    
    # 좌표에 대한 그래디언트
    grad_coords = torch.zeros_like(coords)
    grad_coords[:, 1] = grad_output * dMp_dy  # Y 방향만 (X는 영향 없음)
    
    # 체인룰: ∂Loss/∂coords = ∂Loss/∂M_p × ∂M_p/∂coords
    return grad_coords, None, None, None, None
```

**물리적 해석:**

- **직접 항**: 개별 노드가 직접 모멘트 계산에 기여하는 정도
- **간접 항**: 노드 이동이 PNA 위치를 변경시켜 다른 모든 노드의 기여도를 간접적으로 변화시키는 정도

이 두 항을 모두 고려함으로써 정확한 민감도 분석이 가능하고, 그래디언트 기반 최적화가 올바르게 동작합니다.

---

## 4. 신경망 아키텍처: CGDN (Constraint-aware Graph Deformation Network)

### 4.1 전체 구조 개요

CGDN은 다음 4개 주요 모듈로 구성됩니다:

```
CGDN(in_channels=6, hidden_channels=128, num_parts=4, heads=4, edge_dim=4)

1. Node Encoder
   ├─ Linear(6 → 128)
   ├─ LayerNorm(128)
   └─ GELU
   
   역할: 입력 노드 특징을 고차원 latent space로 매핑

2. FiLM Generator
   ├─ Linear(1 → 64)
   ├─ GELU
   └─ Linear(64 → 256)  # = 2 × hidden_channels
   
   역할: 목표 Mp를 조건 파라미터(γ, β)로 변환

3. Message-Passing Blocks (×4 iterations)
   └─ CGDNBlock
      ├─ GATv2Conv: (128, 128/4, heads=4, edge_dim=4)
      ├─ FiLM Modulation: γ ⊙ h + β
      ├─ LayerNorm(128)
      ├─ GELU
      └─ Residual Connection
   
   역할: 그래프 신경망으로 이웃 정보 집계 및 조건 주입

4. Coordinate Decoder
   ├─ Linear(128 → 64)
   ├─ GELU
   └─ Linear(64 → 2)  # Δx, Δy
   
   역할: 숨겨진 표현을 좌표 변위로 디코딩
```

### 4.2 세부 모듈 분석

#### **Module 1: FiLMGenerator**

Feature-wise Linear Modulation (FiLM)은 조건 정보를 신경망에 주입하는 기법입니다.

```python
class FiLMGenerator(nn.Module):
    def __init__(self, hidden_channels=128):
        self.net = nn.Sequential(
            nn.Linear(1, 64),           # target_mp [B, 1] → [B, 64]
            nn.GELU(),
            nn.Linear(64, 256),         # [B, 64] → [B, 256]
        )
    
    def forward(self, target_mp):
        out = self.net(target_mp)                    # [B, 256]
        gamma, beta = torch.chunk(out, 2, dim=-1)   # [B, 128] each
        return gamma, beta
```

**기능:**
1. 스칼라 입력 (목표 Mp 값)을 받아 64차원 중간 표현으로 확장
2. 최종적으로 128차원의 스케일(γ)과 시프트(β) 파라미터 생성
3. 이는 모든 메시지 패싱 블록에서 일관되게 적용됨

**FiLM 조정 연산:**
$$h'_i = \gamma_j \odot h_i + \beta_j$$

여기서:
- $h_i \in \mathbb{R}^{128}$: i번째 노드의 숨겨진 표현
- $\gamma_j, \beta_j \in \mathbb{R}^{128}$: j번째 조건(층)의 FiLM 파라미터
- $\odot$: 원소별 곱셈(element-wise multiplication)

**의미:** 같은 목표 Mp를 가진 노드들은 동일한 γ, β로 조정되므로, 조건부 학습이 가능합니다.

#### **Module 2: CGDNBlock (Message-Passing Block)**

```python
class CGDNBlock(nn.Module):
    def __init__(self, hidden_channels=128, heads=4, edge_dim=4):
        self.conv = GATv2Conv(
            hidden_channels,           # 입력 차원
            hidden_channels // heads,  # 128 / 4 = 32 per head
            heads=4,
            edge_dim=4,
            concat=True,              # 출력: 4 × 32 = 128
        )
        self.norm = LayerNorm(hidden_channels)
    
    def forward(self, h, edge_index, edge_attr, gamma, beta):
        h_res = h                           # 잔차 연결용
        
        # 1. GATv2 합성곱 (주변 노드 정보 수집)
        h = self.conv(h, edge_index, edge_attr)  # [N, 128]
        
        # 2. FiLM 조건 주입
        h = gamma * h + beta                # [N, 128]
        
        # 3. 정규화
        h = self.norm(h)                    # [N, 128]
        
        # 4. 활성화
        h = F.gelu(h)                       # [N, 128]
        
        # 5. 잔차 연결
        h = h + h_res                       # [N, 128]
        
        return h
```

**각 연산의 역할:**

1. **GATv2Conv (Graph Attention Network v2)**
   
   입력: 노드 특징 h [N, 128], 엣지 정보 edge_attr [E, 4]
   
   연산:
   ```
   i번째 노드에 대해:
   
   1. 쿼리, 키, 값 생성:
      q_i = W_q · h_i
      k_j = W_k · h_j  (모든 j ∈ neighbors(i))
      v_j = W_v · h_j
   
   2. 엣지 특징 포함 주의력 가중치:
      α_ij = softmax_j(
        (q_i · k_j^T) / √d_k + MLP_edge(edge_attr[i,j])
      )
   
   3. 집계:
      h'_i = concat_{head=1}^{4} (Σ_j α_ij · v_j^{(head)})
   ```
   
   출력: [N, 128] (4개 헤드 × 32차원 = 128차원)

2. **FiLM 조정**
   
   조건부 정보(목표 Mp)를 노드 특징에 주입합니다.
   
   의미: 각 노드가 자신의 층의 목표 강도를 "인식"하게 함

3. **LayerNorm**
   
   $\text{LayerNorm}(h) = \gamma_{norm} \cdot \frac{h - \mu}{\sqrt{\sigma^2 + \epsilon}} + \beta_{norm}$
   
   역할: 활성화 값의 분포를 정규화하여 학습 안정성 향상

4. **GELU 활성화**
   
   $\text{GELU}(x) = x \cdot \Phi(x)$
   
   ($\Phi$: 표준 정규분포의 누적분포함수)
   
   역할: 부드러운 비선형 변환으로 표현력 증대

5. **잔차 연결**
   
   $h_{\text{out}} = h_{\text{processed}} + h_{\text{in}}$
   
   역할:
   - 깊은 네트워크에서도 기울기 전파 개선
   - 원본 정보 보존으로 과도한 변환 방지
   - 학습 수렴 가속화

#### **Module 3: CGDN.forward (전체 순전파)**

```python
def forward(self, x, edge_index, edge_attr, target_mp, is_fixed_mask):
    """
    x: [N, 6] = [x, y, is_fixed, part_id, t, fy]
    edge_index: [2, E]
    edge_attr: [E, 4]
    target_mp: [N, 1] (노드별 목표 Mp)
    is_fixed_mask: [N, 1] (고정점 여부)
    """
    
    # 단계 1: 노드 인코딩
    h = self.node_encoder(x)  # [N, 6] → [N, 128]
    
    # 단계 2: FiLM 파라미터 생성
    gamma, beta = self.film_gen(target_mp)  # [N, 1] → 2 × [N, 128]
    
    # 단계 3: 메시지 패싱 (4회 반복)
    for block in self.blocks:  # 4개의 CGDNBlock
        h = block(h, edge_index, edge_attr, gamma, beta)
    
    # 단계 4: 변위 디코딩
    delta_coords = self.decoder(h)  # [N, 128] → [N, 2]
    
    # 단계 5: 안정성 제약
    delta_coords = torch.clamp(delta_coords, -50.0, 50.0)  # 최대 50mm 변위
    
    # 단계 6: 고정점 제약 (hard constraint)
    delta_coords = delta_coords * (~is_fixed_mask).float()  # 고정점: Δ = 0
    
    # 단계 7: 최종 좌표 계산
    new_coords = x[:, :2] + delta_coords  # [N, 2]
    
    return new_coords, delta_coords
```

**그래프 연산의 흐름:**

```
입력 좌표: x[:, :2] = [N, 2]
     ↓
노드 인코더: h = [N, 128]
     ↓ (목표 Mp 조건)
FiLM 생성: γ, β = [N, 128]
     ↓
메시지 패싱 (4×):
  ├─ GATv2Conv: 이웃 정보 수집 + 엣지 특징 반영
  ├─ FiLM: 목표 Mp 재조정
  ├─ Norm + GELU: 정규화 및 비선형화
  └─ Residual: 정보 보존
     ↓
디코더: Δx, Δy = [N, 2]
     ↓
제약 적용:
  ├─ 클리핑: |Δ| ≤ 50mm
  └─ 고정점: is_fixed = True → Δ = 0
     ↓
최종 좌표: x[:, :2] + Δ = [N, 2]
```

---

## 5. 손실 함수 아키텍처

### 5.1 물리 손실 (L_phys): 강도 목표 달성

```python
# 층별로 계산
for section in unique_sections:
    coords_section = new_coords[section_mask, :2]  # 해당 층의 노드
    t_section = t[section_mask]
    fy_section = fy[section_mask]
    
    # PNA 솔버로 전소성 모멘트 계산
    pred_mp_section = calculate_mpl(coords_section, t_section, 
                                     fy_section, None)
    
    # 목표값과의 상대 오차
    target_mp_section = target_mps[section_id]
    l_phys_section = ((pred_mp_section - target_mp_section) 
                      / target_mp_section) ** 2
    
    l_phys_total += l_phys_section

# 평균화
l_phys = l_phys_total / num_sections
```

**정리:**
$$L_{phys} = \frac{1}{n_{sections}} \sum_{s} \left( \frac{M_p^{pred}_s - M_p^{target}_s}{M_p^{target}_s} \right)^2$$

**특징:**
- 상대 오차 사용: 절대값의 크기 차이에 불변
- 각 층별 독립 계산: 다층 구조에 맞춤
- 역전파: IFT를 통해 정확한 그래디언트 제공

### 5.2 형상 매끄러움 손실 (L_smooth): 형태 변화 억제

```python
def compute_smoothness_loss(new_coords, edge_index):
    src, dst = edge_index
    
    # 각 선분의 길이 변화 계산
    diff = new_coords[src] - new_coords[dst]  # [E, 2]
    distances = torch.norm(diff, dim=1)        # [E]
    
    # 거리 변화의 제곱 평균
    return torch.mean(distances ** 2)
```

**정리:**
$$L_{smooth} = \frac{1}{|E|} \sum_{(i,j) \in E} \|c_i - c_j\|^2$$

여기서:
- $E$: 엣지 집합
- $c_i, c_j$: i, j 노드의 좌표

**물리적 의미:**
- 연결된 노드 사이의 거리가 크면 손실이 커짐
- 평탄하고 매끄러운 형상을 선호
- 갑작스러운 굽힘이나 찌그러짐 방지

**응용:**
곡률 제약에 가까운 역할 수행. 매우 낮은 가중치(0.01)로 미세 조정.

### 5.3 간섭 방지 손실 (L_collision): 파트 간 겹침 제거

```python
def compute_collision_loss(new_coords, part_ids, section_ids, margin=0.5):
    total_loss = 0.0
    
    for lvl in unique_sections:
        lvl_mask = (section_ids == lvl)
        y_lvl = new_coords[lvl_mask, 1]        # 해당 층의 Y좌표
        p_lvl = part_ids[lvl_mask]             # 해당 층의 파트 ID
        
        mask_1 = (p_lvl == 1)  # Outer
        mask_2 = (p_lvl == 2)  # Reinforcement
        mask_3 = (p_lvl == 3)  # Inner
        
        # 케이스 1: Inner vs Reinf 간 간섭
        if mask_2.any() and mask_3.any():
            # Inner의 최대 Y < Reinf의 최소 Y (+ margin)
            gap_3_2 = torch.clamp(
                y_lvl[mask_3].max() - y_lvl[mask_2].min() + margin,
                min=0.0
            )
            total_loss += gap_3_2 ** 2
            
            # Reinf vs Outer 간 간섭
            gap_2_1 = torch.clamp(
                y_lvl[mask_2].max() - y_lvl[mask_1].min() + margin,
                min=0.0
            )
            total_loss += gap_2_1 ** 2
        
        # 케이스 2: Reinf가 없는 층 (예: 상단)
        elif mask_3.any() and mask_1.any():
            gap_3_1 = torch.clamp(
                y_lvl[mask_3].max() - y_lvl[mask_1].min() + margin,
                min=0.0
            )
            total_loss += gap_3_1 ** 2
    
    return total_loss
```

**수식:**

일반화된 형태:
$$L_{collision} = \sum_{lvl} \sum_{\text{pairs}} \text{clamp}(\max(y_{\text{inner}}) - \min(y_{\text{outer}}) + m, 0)^2$$

여기서:
- $m = 0.5$mm: 최소 안전 간격 (margin)
- "Inner < Outer"의 Y좌표 순서 강제

**동작 메커니즘:**

```
Y축 방향 예시:

초기 상태:
  Inner:  [100, 120]
  Outer:   [80, 110]     ← 겹침!
  gap = 120 - 80 - 0.5 = 39.5 mm
  손실 = 39.5² = 1560

최적화 후:
  Inner:  [110, 130]
  Outer:   [50, 100]     ← 분리됨
  gap = 110 - 50 - 0.5 = 59.5 mm > 0 (만족)
  손실 = 0
```

**특징:**
- **Soft constraint**: clamp로 양수 위반만 벌칙
- **계층적 구조**: 각 층에서 독립적으로 검사
- **안전 마진**: 제조 공차 고려 (margin=0.5mm)

### 5.4 경량화 손실 (L_mass): 단면적 최소화

```python
def compute_mass_loss(new_coords, t, edge_index):
    src, dst = edge_index
    
    # 각 선분의 길이
    seg_len = torch.norm(new_coords[src] - new_coords[dst], dim=1)  # [E]
    
    # 선분 시작점의 두께
    t_src = t[src].squeeze(-1)  # [E]
    
    # 전체 단면적 (무게의 프록시)
    area = torch.sum(seg_len * t_src)
    
    return area
```

**정리:**
$$L_{mass} = \sum_{(i,j) \in E} L_{i,j} \cdot t_i$$

여기서:
- $L_{i,j} = \|c_i - c_j\|$: 선분 길이
- $t_i$: 선분 시작점의 두께
- 합산: 전체 단면적 (체적, 무게에 비례)

**주의 사항:**
- 절대값이 아닌 손실 값 자체 → 최소화하려면 경량화
- 낮은 가중치(0.0001) 설정으로 보조적 목표화

### 5.5 고정점 보존 손실 (L_fix): 형태 고정

```python
fixed_nodes = is_fixed_mask.squeeze()  # [N] bool

if fixed_nodes.any():
    # 고정점의 변위 크기 합산
    l_fix = torch.sum(torch.norm(delta_coords[fixed_nodes], dim=1))
else:
    l_fix = torch.tensor(0.0, device=x.device)
```

**정리:**
$$L_{fix} = \sum_{i \in \text{Fixed}} \|\Delta c_i\|_2$$

여기서:
- "Fixed": is_fixed=True인 노드 집합
- $\Delta c_i = c_i^{new} - c_i^{old}$: 변위 벡터

**특징:**
- **하드 제약과의 이중 적용**:
  1. 모델의 decoder에서 고정점 변위를 0으로 강제
  2. 손실 함수에서 추가 페널티 (보험)
- **목표**: 기본 골격(예: 용접점)을 절대 변형 안 함

### 5.6 최종 통합 손실 함수

```python
w_phys = 1000.0        # 강도 (최우선)
w_smooth = 0.01        # 매끄러움 (미세 조정)
w_mass = 0.0001        # 경량화 (부차)
w_collision = 50.0     # 간섭 (중요 제약)
w_fix = 100.0          # 형태 (중요 제약)

Loss = (w_phys * L_phys 
      + w_smooth * L_smooth
      + w_mass * L_mass
      + w_collision * L_collision
      + w_fix * L_fix)
```

**가중치 설정 논리:**

| 손실 함수 | 가중치 | 우선순위 | 이유 |
|----------|--------|---------|------|
| L_phys | 1000.0 | ★★★★★ | 안전성 목표가 최우선. 무엇보다 중요 |
| L_collision | 50.0 | ★★★★ | 제조 불가능한 설계 방지 (하드 제약) |
| L_fix | 100.0 | ★★★★ | 용접점 변형 방지 (구조 안정성) |
| L_smooth | 0.01 | ★★ | 형태 완성도 개선 (미세 조정) |
| L_mass | 0.0001 | ★ | 경량화 (이미 강도 충족 후 최적화) |

**다목적 최적화 전략:**

```
훈련 초기 (1-100 epoch):
  → 주로 L_phys, L_collision이 활성
  → 구조적으로 가능한 설계 탐색

훈련 중기 (100-500 epoch):
  → L_phys 감소하면서 L_smooth 영향 증가
  → 형태 개선 시작

훈련 후기 (500+ epoch):
  → L_mass로 경량화 최적화
  → 모든 제약 동시 만족 추구
```

---

## 6. 훈련 루프: train_step 함수의 세부 실행

### 6.1 입력 데이터 구조

```python
data: PyTorch Geometric Data 객체
  ├─ x [N, 7]: 노드 특징
  │   ├─ x[:, 0]: 좌표 X
  │   ├─ x[:, 1]: 좌표 Y
  │   ├─ x[:, 2]: 고정 플래그 (0/1)
  │   ├─ x[:, 3]: 파트 ID (1=Outer, 2=Reinf, 3=Inner)
  │   ├─ x[:, 4]: 층 ID (1, 2, 3, ...)
  │   ├─ x[:, 5]: 두께 t
  │   └─ x[:, 6]: 항복강도 fy
  │
  ├─ edge_index [2, E]: 그래프 연결성
  │   ├─ edge_index[0, :]: source 노드 인덱스
  │   └─ edge_index[1, :]: destination 노드 인덱스
  │
  └─ edge_attr [E, 4]: 엣지 속성
      ├─ edge_attr[:, 0]: 선분 길이
      ├─ edge_attr[:, 1]: 각도
      ├─ edge_attr[:, 2]: 층 ID
      └─ edge_attr[:, 3]: 플랜지 여부

target_mps: dict
  └─ {section_id: Mp_target_value, ...}
     예: {1: 50000, 2: 55000, 3: 48000}  (단위: N·mm)
```

### 6.2 특징 추출 및 노드별 목표 Mp 생성

```python
def train_step(model, data, optimizer, target_mps, ...):
    model.train()
    optimizer.zero_grad()
    
    # 데이터 추출
    x = data.x                    # [N, 7]
    edge_index = data.edge_index  # [2, E]
    edge_attr = data.edge_attr    # [E, 4]
    
    # 특징 분해
    is_fixed_mask = x[:, 2].bool().unsqueeze(1)  # [N, 1]
    part_ids = x[:, 3]                           # [N]
    section_ids = x[:, 4]                        # [N]
    t = x[:, 5].unsqueeze(1)                      # [N, 1]
    fy = x[:, 6].unsqueeze(1)                     # [N, 1]
    
    unique_sections = torch.unique(section_ids)  # 층 개수
    
    # 핵심: 노드별 목표 Mp 텐서 생성
    target_mp_node = torch.zeros((x.shape[0], 1), 
                                  dtype=torch.float32, 
                                  device=x.device)
    
    for section in unique_sections:
        section_mask = (section_ids == section)
        section_int = int(section.item())
        # 같은 층에 속하는 모든 노드에 해당 층의 목표 Mp 할당
        target_mp_node[section_mask] = target_mps[section_int]
    
    # 결과 예:
    # target_mps = {0: 50000, 1: 55000, 2: 48000}
    # target_mp_node = [50000, 50000, ..., 55000, 55000, ..., 48000, ...]
```

**의의:**
- FiLM이 [N, 1] 입력 받을 수 있도록 노드별 확장
- PyTorch 브로드캐스팅으로 각 노드가 "자신의 목표 Mp"를 인식

### 6.3 신경망 순전파

```python
# CGDN 모델 실행
new_coords, delta_coords = model(
    x[:, :2],           # 실제 사용하는 입력은 좌표와 특징들을 재조합
    edge_index, 
    edge_attr, 
    target_mp_node,     # 노드별 목표 Mp [N, 1]
    is_fixed_mask       # 고정점 마스크 [N, 1]
)

# 반환값
new_coords [N, 2]:    # 변형된 좌표
delta_coords [N, 2]:  # 예측된 변위

# 실제 CGDN.forward 입력은:
# x: 재조합된 [N, 6] = [x, y, is_fixed, part_id, t, fy]
#    (수정: CGDN의 실제 입력 확인 필요)
```

**주의:** 코드에서 x 전달 방식 재검토 필요 (forward 서명과 호출 일관성)

### 6.4 층별 물리 계산

```python
l_phys_total = torch.tensor(0.0, device=x.device)
pred_mp_sections = []

for section in unique_sections:
    # 1. 층 내 노드만 선택
    section_mask = (section_ids == section)
    coords_section = new_coords[section_mask]  # [n_i, 2]
    t_section = t[section_mask]                # [n_i, 1]
    fy_section = fy[section_mask]              # [n_i, 1]
    
    # 2. Implicit PNA Solver 호출
    #    이 함수는 다음을 수행:
    #    - 이분탐색으로 y_pna 찾기
    #    - Mp = Σ A·fy·|y - y_pna| 계산
    #    - 역전파 시 IFT 적용
    pred_mp_section = calculate_mpl(
        coords_section, 
        t_section, 
        fy_section, 
        None  # edge_index 사용 안 함
    )
    
    # 3. 목표값과 비교
    section_int = int(section.item())
    target_mp_section = torch.tensor(
        target_mps[section_int], 
        dtype=torch.float32, 
        device=x.device
    )
    
    # 4. 상대 오차 제곱
    l_phys_section = (
        (pred_mp_section - target_mp_section) / target_mp_section
    ) ** 2
    
    # 5. 누적
    l_phys_total += l_phys_section.squeeze()
    pred_mp_sections.append(pred_mp_section.item())

# 평균화 (층 개수로 나누기)
num_sections = len(unique_sections)
l_phys_total = l_phys_total / num_sections
pred_mp_sections = np.array(pred_mp_sections)
```

**계산 복잡도:**
- 층의 개수: n_sections
- 각 층의 노드: 평균 N / n_sections
- 각 층의 이분탐색: 30 × N/n_sections = O(N)
- 전체: O(n_sections × N) = O(N)

### 6.5 제약 손실 함수 계산

```python
# A. 매끄러움 손실
l_smooth = compute_smoothness_loss(new_coords, edge_index)

# B. 간섭 방지 손실
l_collision = compute_collision_loss(new_coords, part_ids, section_ids, margin=0.5)

# C. 경량화 손실
l_mass = compute_mass_loss(new_coords, t, edge_index)

# D. 고정점 보존 손실
fixed_nodes = is_fixed_mask.squeeze()
if fixed_nodes.any():
    l_fix = torch.sum(torch.norm(delta_coords[fixed_nodes], dim=1))
else:
    l_fix = torch.tensor(0.0, device=x.device)

# E. 최종 가중 손실
loss = (w_phys * l_phys_total
      + w_smooth * l_smooth
      + w_mass * l_mass
      + w_collision * l_collision
      + w_fix * l_fix)
```

### 6.6 역전파 및 가중치 업데이트

```python
# 1. 자동 미분으로 모든 그래디언트 계산
loss.backward()

# 내부 동작:
# ├─ L_phys의 역전파:
# │  └─ ImplicitPNASolver.backward() 호출
# │     ├─ IFT로 ∂M_p/∂y 계산
# │     └─ 이를 ∂Loss/∂(GNN 파라미터)로 전파
# │
# ├─ L_smooth, L_collision, L_mass, L_fix의 역전파:
# │  └─ 표준 자동 미분
# │
# └─ 모든 손실의 합:
#    └─ ∂Loss/∂w = Σ ∂(w_i × L_i)/∂w

# 2. 옵티마이저로 파라미터 업데이트
optimizer.step()

# 예를 들어 SGD의 경우:
# w ← w - learning_rate × ∂Loss/∂w
```

### 6.7 반환 값

```python
return {
    "loss": loss.item(),                    # 최종 손실값 (스칼라)
    "pred_mp": pred_mp_sections,            # [n_sections] 각 층의 예측 Mp
    "l_phys": l_phys_total.item(),          # 물리 손실 기여도
    "l_smooth": l_smooth.item(),            # 매끄러움 손실 기여도
    "l_mass": l_mass.item(),                # 경량화 손실 기여도
    "l_collision": l_collision.item(),      # 간섭 손실 기여도
    "l_fix": l_fix.item() if isinstance(l_fix, torch.Tensor) else l_fix,
    "new_coords": new_coords.detach(),      # 최종 좌표 (역전파 그래프 제거)
}
```

**통계 활용:**
- 훈련 과정 모니터링: 각 손실 기여도 추적
- 수렴 판정: loss < threshold인지 확인
- 제약 만족 검증: l_collision, l_fix이 0 근처인지 확인

---

## 7. 코드 실행 흐름 종합

### 7.1 초기화 단계

```python
# 1. 모델 생성
model = CGDN(
    in_channels=6,
    hidden_channels=128,
    num_parts=4,        # GATv2 블록 4개
    heads=4,            # 어텐션 헤드 4개
    edge_dim=4,         # 엣지 특징 4차원
    max_displacement=50.0
)

# 2. 옵티마이저 설정
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

# 3. 데이터 준비
data = Data(
    x=torch.tensor(..., dtype=torch.float32),
    edge_index=torch.tensor(..., dtype=torch.long),
    edge_attr=torch.tensor(..., dtype=torch.float32)
)

target_mps = {
    0: 50000,   # 1층 목표 Mp
    1: 55000,   # 2층 목표 Mp
    2: 48000    # 3층 목표 Mp
}
```

### 7.2 훈련 루프

```python
num_epochs = 1000

for epoch in range(num_epochs):
    stats = train_step(
        model, 
        data, 
        optimizer, 
        target_mps,
        w_phys=1000.0,
        w_smooth=0.01,
        w_mass=0.0001,
        w_collision=50.0,
        w_fix=100.0
    )
    
    # 모니터링
    if epoch % 10 == 0:
        print(f"Epoch {epoch}")
        print(f"  Loss: {stats['loss']:.4f}")
        print(f"  L_phys: {stats['l_phys']:.4f}")
        print(f"  L_collision: {stats['l_collision']:.4f}")
        print(f"  Pred Mp: {stats['pred_mp']}")
```

### 7.3 추론 단계

```python
model.eval()
with torch.no_grad():
    new_coords, delta_coords = model(
        x, edge_index, edge_attr, target_mp_node, is_fixed_mask
    )
    
    # 최종 검증
    for section in unique_sections:
        coords_section = new_coords[section_mask]
        pred_mp = calculate_mpl(coords_section, t_section, fy_section, None)
        target_mp = target_mps[section_int]
        
        error = abs(pred_mp - target_mp) / target_mp * 100
        print(f"Section {section}: {pred_mp:.0f} N·mm (target: {target_mp:.0f}), "
              f"Error: {error:.2f}%")
```

---

## 8. 학습 안정성 및 고려사항

### 8.1 수치 안정성 (Numerical Stability)

#### **문제점 1: IFT에서 0으로 나누기**
```python
dy_pna_dy = -dg_dy / (dg_dy_pna + 1e-12)  # ← epsilon 추가
```

- dg_dy_pna는 항상 음수지만, 수치 계산 오류 가능
- epsilon = 1e-12 추가로 0 나누기 방지

#### **문제점 2: 이분탐색 미수렴**
```python
for _ in range(n_iter):  # n_iter = 30
    y_mid = 0.5 * (y_lo + y_hi)
    # ...
```

- 30회 반복 후 오차 < 1e-10 (머신 입실론 수준)
- 충분히 정밀하지만, 매우 큰 범위에서는 문제 가능
- 해결: y 좌표 정규화 (예: [-100, 100] 범위로 스케일링)

#### **문제점 3: 그래디언트 폭발**
```python
loss.backward()
# ∂Loss/∂w이 매우 커질 수 있음
```

- 해결: 그래디언트 클리핑
```python
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
optimizer.step()
```

### 8.2 하이퍼파라미터 민감도

| 파라미터 | 기본값 | 영향 | 조정 방향 |
|---------|-------|------|---------|
| w_phys | 1000.0 | 강도 목표 달성도 | 목표 못 맞추면 ↑ |
| w_collision | 50.0 | 간섭 제거 정도 | 겹침 생기면 ↑ |
| w_fix | 100.0 | 고정점 고정성 | 형태 변하면 ↑ |
| w_smooth | 0.01 | 형태 완성도 | 찌그러지면 ↑ |
| w_mass | 0.0001 | 경량화 강도 | 비용 중요하면 ↑ |
| max_displacement | 50mm | 최대 변위 | 범위 벗어나면 ↑ |
| learning_rate | 0.001 | 학습 속도 | 진동하면 ↓ |

### 8.3 수렴 판정 기준

```python
# 종료 조건
if (l_phys < 0.01 and          # 물리 오차 < 1%
    l_collision < 0.1 and       # 간섭 거의 없음
    l_fix < 1.0):               # 고정점 고정됨
    print("수렴 완료")
    break
```

---

## 9. 결론 및 아키텍처 요약

### 9.1 핵심 기여 (Key Innovations)

1. **물리 인식 신경망 (Physics-Aware GNN)**
   - 미분 가능한 PNA 솔버 통합
   - IFT로 정확한 역전파 가능
   - 물리 제약을 손실함수에 명시적으로 포함

2. **조건부 생성 (Conditional Generation)**
   - FiLM으로 목표 Mp를 신경망에 주입
   - 같은 모델으로 다양한 목표값 처리

3. **다목적 최적화 (Multi-objective Optimization)**
   - 강도, 형태, 경량화, 간섭, 형태 보존을 동시 최적화
   - 가중치로 우선순위 조정 가능

4. **하드 제약 (Hard Constraints)**
   - 고정점 마스킹으로 절대 보존 강제
   - 변위 클리핑으로 안정성 보장

### 9.2 아키텍처 요약

```
┌──────────────────────────────────────────────────────────────┐
│                   CGNN (입력 → 출력)                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  입력:                                                       │
│    └─ 그래프: x [N, 6], edge_index [2, E], edge_attr [E, 4] │
│       조건: target_mp [N, 1]                                 │
│                                                              │
│  처리:                                                       │
│    1. Node Encoder: x [N, 6] → h [N, 128]                  │
│    2. FiLM Gen: target_mp [N, 1] → γ,β [N, 128]            │
│    3. GATv2×4: h [N, 128] → h' [N, 128] (조건 주입)         │
│    4. Decoder: h' [N, 128] → Δc [N, 2]                     │
│                                                              │
│  제약:                                                       │
│    ├─ 클리핑: |Δc| ≤ 50mm                                  │
│    └─ 마스킹: is_fixed → Δc = 0                            │
│                                                              │
│  출력:                                                       │
│    └─ c_new = c_old + Δc [N, 2]                           │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                   물리 검증 및 역전파                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Implicit PNA Solver (층별)                              │
│     └─ y_pna (이분탐색) → M_p 계산                          │
│                                                              │
│  2. 손실 함수 (5개)                                          │
│     ├─ L_phys: 강도 (w=1000)                               │
│     ├─ L_smooth: 형상 (w=0.01)                             │
│     ├─ L_collision: 간섭 (w=50)                            │
│     ├─ L_mass: 경량화 (w=0.0001)                           │
│     └─ L_fix: 형태 (w=100)                                 │
│                                                              │
│  3. 역전파 (Backpropagation)                                 │
│     └─ IFT로 ∂M_p/∂y 계산                                   │
│        → ∂Loss/∂(GNN 파라미터)로 전파                       │
│                                                              │
│  4. 최적화 (Optimization)                                    │
│     └─ w ← w - lr × ∂Loss/∂w                              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 9.3 강점 및 한계

**강점:**
- 물리 기반 설계로 신뢰성 높음
- 이분탐색 수렴이 매우 빠름
- 다층 구조 유연하게 처리
- FiLM으로 조건 주입 효율적

**한계:**
- 2D 단면에만 적용 (3D 확장 필요)
- 이분탐색이 단순 구조 가정 (L자형, T자형 등 특수 단면에서 문제)
- 엣지 특징 [4]이 고정적 (동적 업데이트 미지원)
- 계산 비용: 매 스텝마다 PNA 솔버 30회 반복

---

## 부록: 수학 기호 및 정의

| 기호 | 의미 | 차원 | 범위 |
|------|------|------|------|
| $x$ | 좌표 또는 노드 특징 | [N, 2] 또는 [N, 6] | 실수 |
| $y_{pna}$ | 소성 중립축 | scalar | 실수 |
| $M_p$ | 전소성 모멘트 | scalar | 양수 |
| $t_i$ | i번째 노드의 두께 | scalar | 양수 |
| $f_y^i$ | i번째 노드의 항복강도 | scalar | 양수 |
| $d_i$ | i번째 노드의 중립축 거리 | scalar | 양수 |
| $\gamma, \beta$ | FiLM 파라미터 | [H] | 실수 |
| $h$ | 노드 숨겨진 표현 | [N, H] | 실수 |
| $\Delta c$ | 변위 벡터 | [N, 2] | 실수 |
| $\alpha_{ij}$ | 어텐션 가중치 | scalar | [0, 1] |

---

**작성일**: 2026년 2월 26일  
**버전**: 1.0  
**대상**: 박사급 수준의 딥러닝 및 구조 최적화 연구자
