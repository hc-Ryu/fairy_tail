#!/usr/bin/env python
# coding: utf-8
"""
ImplicitPNASolver 검증 코드
검증 목표:
1. Forward: bisection이 PNA (force balance)를 찾는지 vs 탄성 NA (moment balance)를 찾는지
2. Backward: IFT 그래디언트가 수치 미분과 일치하는지
3. 비대칭 단면에서 오류가 얼마나 큰지
"""

import torch
import numpy as np


# ─────────────────────────────────────────────────────────────
# 원본 코드 복사 (20260309_yj.py 에서)
# ─────────────────────────────────────────────────────────────

class ImplicitPNASolver_Original(torch.autograd.Function):
    """원본 코드 (검증 대상)"""
    @staticmethod
    def forward(ctx, coords, t, fy, edge_index, n_iter=30):
        with torch.no_grad():
            y = coords[:, 1]
            t_flat = t.squeeze(-1)
            fy_flat = fy.squeeze(-1)
            y_lo = y.min().clone()
            y_hi = y.max().clone()
            for _ in range(n_iter):
                y_mid = 0.5 * (y_lo + y_hi)
                F_tens = torch.sum(t_flat * fy_flat * torch.clamp(y - y_mid, min=0.0))
                F_comp = torch.sum(t_flat * fy_flat * torch.clamp(y_mid - y, min=0.0))
                if F_tens > F_comp:
                    y_lo = y_mid
                else:
                    y_hi = y_mid
            y_pna = 0.5 * (y_lo + y_hi)
        d = torch.abs(coords[:, 1] - y_pna)
        area = t_flat
        mp_pred = torch.sum(area * fy_flat * d)
        ctx.save_for_backward(coords, t, fy, y_pna.unsqueeze(0), edge_index)
        return mp_pred

    @staticmethod
    def backward(ctx, grad_output):
        coords, t, fy, y_pna_buf, edge_index = ctx.saved_tensors
        y_pna = y_pna_buf.squeeze(0)
        y = coords[:, 1]
        t_flat = t.squeeze(-1)
        fy_flat = fy.squeeze(-1)
        s = torch.sign(y - y_pna)

        dg_dy_pna = -torch.sum(t_flat * fy_flat)
        dg_dy = s * t_flat * fy_flat
        dy_pna_dy = -dg_dy / (dg_dy_pna + 1e-12)

        direct = t_flat * fy_flat * s
        indirect = -torch.sum(t_flat * fy_flat * s) * dy_pna_dy
        dMp_dy = direct + indirect

        grad_coords = torch.zeros_like(coords)
        grad_coords[:, 1] = grad_output * dMp_dy
        return grad_coords, None, None, None, None


# ─────────────────────────────────────────────────────────────
# 수정 버전: 진정한 소성 중립축 (force balance) + 올바른 IFT
# ─────────────────────────────────────────────────────────────

class ImplicitPNASolver_Corrected(torch.autograd.Function):
    """수정 버전: Force balance bisection + 올바른 IFT"""
    @staticmethod
    def forward(ctx, coords, t, fy, n_iter=50):
        with torch.no_grad():
            y = coords[:, 1]
            t_flat = t.squeeze(-1)
            fy_flat = fy.squeeze(-1)
            y_lo = y.min().clone()
            y_hi = y.max().clone()
            for _ in range(n_iter):
                y_mid = 0.5 * (y_lo + y_hi)
                # Force balance: Σ_T t*fy vs Σ_C t*fy
                F_T = torch.sum(t_flat * fy_flat * (y > y_mid).float())
                F_C = torch.sum(t_flat * fy_flat * (y < y_mid).float())
                if F_T > F_C:
                    y_lo = y_mid
                else:
                    y_hi = y_mid
            y_pna = 0.5 * (y_lo + y_hi)
        d = torch.abs(coords[:, 1] - y_pna)
        mp_pred = torch.sum(t_flat * fy_flat * d)
        ctx.save_for_backward(coords, t, fy, y_pna.unsqueeze(0))
        return mp_pred

    @staticmethod
    def backward(ctx, grad_output):
        coords, t, fy, y_pna_buf = ctx.saved_tensors
        y_pna = y_pna_buf.squeeze(0)
        y = coords[:, 1]
        t_flat = t.squeeze(-1)
        fy_flat = fy.squeeze(-1)
        s = torch.sign(y - y_pna)

        # 올바른 dg/dy_i: 모든 노드에 대해 +t_i*fy_i (부호 없음)
        # g = Σ_T t*fy - Σ_C t*fy, ∂g/∂y_i = t_i*fy_i for ALL i
        dg_dy_pna = -torch.sum(t_flat * fy_flat)  # 여전히 동일
        dg_dy = t_flat * fy_flat  # 부호 없음! (수정된 부분)
        dy_pna_dy = -dg_dy / (dg_dy_pna + 1e-12)

        direct = t_flat * fy_flat * s
        # Force balance at PNA: Σ(t*fy*s) = A_T - A_C ≈ 0
        indirect = -torch.sum(t_flat * fy_flat * s) * dy_pna_dy
        dMp_dy = direct + indirect

        grad_coords = torch.zeros_like(coords)
        grad_coords[:, 1] = grad_output * dMp_dy
        return grad_coords, None, None, None


# ─────────────────────────────────────────────────────────────
# 수치 미분 함수
# ─────────────────────────────────────────────────────────────

def numerical_gradient_mp(coords_val, t_val, fy_val, eps=1e-4):
    """수치 미분으로 ∂Mp/∂y_i 계산 (정확한 참조값)"""
    n = coords_val.shape[0]
    grads = torch.zeros(n)
    for i in range(n):
        coords_plus = coords_val.clone()
        coords_plus[i, 1] += eps
        coords_minus = coords_val.clone()
        coords_minus[i, 1] -= eps

        # 각 섭동에 대해 직접 Mp 계산 (bisection 없이, 올바른 PNA 사용)
        mp_plus = compute_mp_with_correct_pna(coords_plus, t_val, fy_val)
        mp_minus = compute_mp_with_correct_pna(coords_minus, t_val, fy_val)
        grads[i] = (mp_plus - mp_minus) / (2 * eps)
    return grads


def compute_mp_with_correct_pna(coords, t, fy, n_iter=50):
    """올바른 PNA (force balance)로 Mp 계산"""
    y = coords[:, 1]
    t_flat = t.squeeze(-1)
    fy_flat = fy.squeeze(-1)
    y_lo = y.min().clone()
    y_hi = y.max().clone()
    for _ in range(n_iter):
        y_mid = 0.5 * (y_lo + y_hi)
        F_T = torch.sum(t_flat * fy_flat * (y > y_mid).float())
        F_C = torch.sum(t_flat * fy_flat * (y < y_mid).float())
        if F_T > F_C:
            y_lo = y_mid
        else:
            y_hi = y_mid
    y_pna = 0.5 * (y_lo + y_hi)
    d = torch.abs(y - y_pna)
    return torch.sum(t_flat * fy_flat * d).item()


# ─────────────────────────────────────────────────────────────
# TEST 1: 대칭 직사각형 단면
# ─────────────────────────────────────────────────────────────

def test_symmetric_section():
    """대칭 단면: 원본과 수정 버전 동일해야 함"""
    print("\n" + "="*60)
    print("TEST 1: 대칭 직사각형 단면 (6 nodes, 균일 t=5, fy=355)")
    print("="*60)

    N = 6
    y_vals = torch.linspace(-150.0, 150.0, N)
    x_vals = torch.zeros(N)
    coords = torch.stack([x_vals, y_vals], dim=1).requires_grad_(True)
    t = torch.ones(N, 1) * 5.0
    fy = torch.ones(N, 1) * 355.0
    edge_index = torch.zeros(2, 1, dtype=torch.long)

    # 이론적 PNA: y=0 (대칭)
    y_total = y_vals.sum().item()
    weighted_centroid = (t.squeeze() * fy.squeeze() * y_vals).sum() / (t.squeeze() * fy.squeeze()).sum()
    print(f"  이론적 PNA (대칭): y = 0.0")
    print(f"  탄성 NA (weighted centroid): y = {weighted_centroid:.4f}")
    print(f"  → 대칭이므로 동일해야 함")

    # 원본 코드
    coords_orig = coords.detach().clone().requires_grad_(True)
    mp_orig = ImplicitPNASolver_Original.apply(coords_orig, t, fy, edge_index, 30)
    mp_orig.backward()
    grads_orig = coords_orig.grad[:, 1].detach().clone()

    # 수치 미분 (참조)
    grads_num = numerical_gradient_mp(coords.detach(), t, fy)

    print(f"\n  Mp (원본): {mp_orig.item():.2f} Nmm")

    # 이론적 Mp: sum(t*fy*|y|)
    mp_theory = (t.squeeze() * fy.squeeze() * y_vals.abs()).sum().item()
    print(f"  Mp (이론): {mp_theory:.2f} Nmm")

    print(f"\n  그래디언트 비교 (∂Mp/∂y_i):")
    print(f"  {'node':>4} {'y':>8} {'원본':>12} {'수치미분':>12} {'일치?':>6}")
    for i in range(N):
        match = abs(grads_orig[i].item() - grads_num[i].item()) < 1.0
        print(f"  {i:>4} {y_vals[i]:>8.1f} {grads_orig[i].item():>12.4f} {grads_num[i].item():>12.4f} {'✓' if match else '✗':>6}")


# ─────────────────────────────────────────────────────────────
# TEST 2: 비대칭 단면 (T형 단면 유사)
# ─────────────────────────────────────────────────────────────

def test_asymmetric_section():
    """비대칭 단면: 탄성 NA ≠ 소성 NA, 오류 확인"""
    print("\n" + "="*60)
    print("TEST 2: 비대칭 단면 (3 nodes, 불균일 t)")
    print("  y=[0, 50, 150] mm, t=[10, 5, 20] mm, fy=355 MPa")
    print("="*60)

    y_vals = torch.tensor([0.0, 50.0, 150.0])
    x_vals = torch.zeros(3)
    t_vals = torch.tensor([[10.0], [5.0], [20.0]])  # 비균일 두께
    fy_vals = torch.ones(3, 1) * 355.0
    coords = torch.stack([x_vals, y_vals], dim=1)

    # 탄성 NA (weighted centroid)
    t_fy = (t_vals.squeeze() * fy_vals.squeeze())
    elastic_na = (t_fy * y_vals).sum() / t_fy.sum()
    print(f"\n  탄성 NA (원본 코드 결과): y = {elastic_na:.4f} mm")

    # 소성 NA (force balance)
    total_force = t_fy.sum()
    cumsum = 0.0
    plastic_na = None
    for i, (yi, fi) in enumerate(zip(y_vals.tolist(), t_fy.tolist())):
        cumsum += fi
        if cumsum >= total_force / 2:
            plastic_na = yi
            break
    print(f"  소성 NA (올바른 PNA): y = {plastic_na:.4f} mm")
    print(f"  → 두 값의 차이: {abs(elastic_na.item() - plastic_na):.4f} mm")

    # 원본 코드 Mp
    edge_index = torch.zeros(2, 1, dtype=torch.long)
    coords_orig = coords.clone().requires_grad_(True)
    mp_orig = ImplicitPNASolver_Original.apply(coords_orig, t_vals, fy_vals, edge_index, 30)

    # 올바른 Mp (소성 NA 기준)
    d_correct = (y_vals - plastic_na).abs()
    mp_correct = (t_fy * d_correct).sum()

    print(f"\n  Mp (원본, 탄성 NA 기준): {mp_orig.item():.2f} Nmm")
    print(f"  Mp (올바른 소성 NA 기준): {mp_correct.item():.2f} Nmm")
    print(f"  오차: {abs(mp_orig.item() - mp_correct.item()):.2f} Nmm ({abs(mp_orig.item() - mp_correct.item())/mp_correct.item()*100:.2f}%)")

    # 그래디언트 비교
    mp_orig.backward()
    grads_orig = coords_orig.grad[:, 1].detach().clone()

    # 수치 미분 (올바른 PNA 기반)
    grads_num = numerical_gradient_mp(coords.detach(), t_vals, fy_vals)

    print(f"\n  그래디언트 비교 (∂Mp/∂y_i):")
    print(f"  {'node':>4} {'y':>8} {'원본 IFT':>12} {'수치미분':>12} {'오차':>10}")
    for i in range(3):
        err = abs(grads_orig[i].item() - grads_num[i].item())
        print(f"  {i:>4} {y_vals[i]:>8.1f} {grads_orig[i].item():>12.4f} {grads_num[i].item():>12.4f} {err:>10.4f}")


# ─────────────────────────────────────────────────────────────
# TEST 3: dg/dy_i 부호 오류 직접 확인
# ─────────────────────────────────────────────────────────────

def test_dg_dy_sign():
    """dg/dy_i의 부호 분석"""
    print("\n" + "="*60)
    print("TEST 3: dg/dy_i 부호 분석 (압축 구역에서 부호 오류 확인)")
    print("="*60)

    # 간단한 2-node 단면: y=[0, 100], t=[1,1], fy=[1,1]
    # PNA = 50 (중앙), 두 노드 모두 동일 t*fy
    y_vals = torch.tensor([0.0, 100.0])
    t_vals = torch.tensor([[1.0], [1.0]])
    fy_vals = torch.tensor([[1.0], [1.0]])

    # g(y_pna) = F_tens - F_comp
    y_pna = torch.tensor(50.0)  # 정확한 PNA
    y = y_vals

    s = torch.sign(y - y_pna)

    # 코드의 dg/dy: s * t * fy
    dg_dy_code = s * t_vals.squeeze() * fy_vals.squeeze()

    # 정확한 dg/dy: 항상 +t*fy
    # node 0 (y=0, 압축): ∂/∂y0[-1*(50-0)] = +1 → dg/dy = t*fy = +1
    # node 1 (y=100, 인장): ∂/∂y1[1*(100-50)] = +1 → dg/dy = t*fy = +1
    dg_dy_correct = t_vals.squeeze() * fy_vals.squeeze()

    print(f"  y_pna = {y_pna.item():.1f}")
    print(f"  node 0 (y=0, 압축): sign = {s[0].item():.0f}")
    print(f"    코드 dg/dy = {dg_dy_code[0].item():.4f}  (부호 있음)")
    print(f"    올바른 dg/dy = {dg_dy_correct[0].item():.4f}  (항상 양수)")
    print(f"    오류: {'YES (압축 구역)' if dg_dy_code[0].item() != dg_dy_correct[0].item() else 'NO'}")
    print(f"  node 1 (y=100, 인장): sign = {s[1].item():.0f}")
    print(f"    코드 dg/dy = {dg_dy_code[1].item():.4f}")
    print(f"    올바른 dg/dy = {dg_dy_correct[1].item():.4f}")

    # dy_pna_dy 계산
    dg_dy_pna = -torch.sum(t_vals.squeeze() * fy_vals.squeeze())
    dy_pna_dy_code = -dg_dy_code / (dg_dy_pna + 1e-12)
    dy_pna_dy_correct = -dg_dy_correct / (dg_dy_pna + 1e-12)

    print(f"\n  dy_pna/dy (코드): {dy_pna_dy_code.tolist()}")
    print(f"  dy_pna/dy (올바름): {dy_pna_dy_correct.tolist()}")

    print(f"\n  해석: dy_pna/dy_i의 물리적 의미")
    print(f"  - 노드를 위로 올리면 y_pna도 얼마나 올라가는가?")
    print(f"  - 대칭에서 두 노드의 dy_pna/dy_i = 0.5 (같은 기여)")
    print(f"  - 코드: 인장 {dy_pna_dy_code[1].item():.4f}, 압축 {dy_pna_dy_code[0].item():.4f}")
    print(f"  - 올바름: 인장 {dy_pna_dy_correct[1].item():.4f}, 압축 {dy_pna_dy_correct[0].item():.4f}")


# ─────────────────────────────────────────────────────────────
# TEST 4: 간접항 소멸 조건 수치 확인
# ─────────────────────────────────────────────────────────────

def test_indirect_term():
    """간접항이 소멸하는 조건 확인"""
    print("\n" + "="*60)
    print("TEST 4: 간접항(indirect term) 소멸 조건")
    print("  - Force balance PNA: Σ(t*fy*s) = 0 → indirect = 0")
    print("  - Elastic NA: Σ(t*fy*s) ≠ 0 → indirect ≠ 0")
    print("="*60)

    cases = [
        # (이름, y_vals, t_vals, fy_vals)
        ("대칭 균일",
         [0.0, 50.0, 100.0],
         [1.0, 1.0, 1.0],
         [355.0, 355.0, 355.0]),
        ("비대칭 두께",
         [0.0, 50.0, 150.0],
         [10.0, 5.0, 20.0],
         [355.0, 355.0, 355.0]),
        ("비대칭 항복강도",
         [0.0, 50.0, 100.0],
         [5.0, 5.0, 5.0],
         [355.0, 355.0, 500.0]),
    ]

    for name, y_list, t_list, fy_list in cases:
        y = torch.tensor(y_list)
        t = torch.tensor(t_list)
        fy = torch.tensor(fy_list)
        t_fy = t * fy

        # Elastic NA (코드의 y_pna)
        elastic_na = (t_fy * y).sum() / t_fy.sum()

        # Force balance PNA (올바른 y_pna): 이산 단면에서 근사
        y_lo, y_hi = y.min().clone(), y.max().clone()
        for _ in range(50):
            y_mid = 0.5 * (y_lo + y_hi)
            F_T = (t_fy * (y > y_mid).float()).sum()
            F_C = (t_fy * (y < y_mid).float()).sum()
            if F_T > F_C:
                y_lo = y_mid
            else:
                y_hi = y_mid
        plastic_na = 0.5 * (y_lo + y_hi)

        # Σ(t*fy*s) at each axis
        s_elastic = torch.sign(y - elastic_na)
        s_plastic = torch.sign(y - plastic_na)
        sum_tfy_s_elastic = (t_fy * s_elastic).sum().item()
        sum_tfy_s_plastic = (t_fy * s_plastic).sum().item()

        print(f"\n  [{name}]")
        print(f"    탄성 NA: y = {elastic_na.item():.4f}, Σ(t·fy·s) = {sum_tfy_s_elastic:.4f}")
        print(f"    소성 NA: y = {plastic_na.item():.4f}, Σ(t·fy·s) = {sum_tfy_s_plastic:.4f}")
        print(f"    간접항 소멸 여부: 탄성NA={'소멸' if abs(sum_tfy_s_elastic)<0.01 else '비소멸'}, 소성NA={'소멸' if abs(sum_tfy_s_plastic)<0.01 else '비소멸'}")


# ─────────────────────────────────────────────────────────────
# TEST 5: 전체 그래디언트 정확도 비교 (다양한 단면)
# ─────────────────────────────────────────────────────────────

def test_gradient_accuracy():
    """원본 IFT vs 수치 미분 그래디언트 정확도 체계적 비교"""
    print("\n" + "="*60)
    print("TEST 5: 그래디언트 정확도 체계적 비교")
    print("="*60)

    test_cases = {
        "대칭 균일 (6nodes)": {
            "y": torch.linspace(0, 300, 6),
            "t": torch.ones(6, 1) * 5.0,
            "fy": torch.ones(6, 1) * 355.0,
        },
        "비대칭 두께 (4nodes)": {
            "y": torch.tensor([0.0, 30.0, 100.0, 200.0]),
            "t": torch.tensor([[3.0], [6.0], [3.0], [10.0]]),
            "fy": torch.ones(4, 1) * 355.0,
        },
        "비균일 항복강도 (4nodes)": {
            "y": torch.tensor([0.0, 50.0, 100.0, 150.0]),
            "t": torch.ones(4, 1) * 5.0,
            "fy": torch.tensor([[235.0], [235.0], [355.0], [355.0]]),
        },
        "고강도 강재 혼합 (5nodes)": {
            "y": torch.tensor([0.0, 25.0, 75.0, 150.0, 300.0]),
            "t": torch.tensor([[8.0], [4.0], [4.0], [4.0], [12.0]]),
            "fy": torch.tensor([[355.0], [355.0], [490.0], [355.0], [355.0]]),
        },
    }

    results = []
    for name, case in test_cases.items():
        y_vals = case["y"]
        t_vals = case["t"]
        fy_vals = case["fy"]
        N = len(y_vals)
        edge_index = torch.zeros(2, 1, dtype=torch.long)

        coords = torch.stack([torch.zeros(N), y_vals], dim=1).requires_grad_(True)
        coords_orig = coords.detach().clone().requires_grad_(True)

        mp_orig = ImplicitPNASolver_Original.apply(coords_orig, t_vals, fy_vals, edge_index, 30)
        mp_orig.backward()
        grads_orig = coords_orig.grad[:, 1].detach().clone()

        grads_num = numerical_gradient_mp(coords.detach(), t_vals, fy_vals)

        max_err = (grads_orig - grads_num).abs().max().item()
        rel_err = max_err / (grads_num.abs().max().item() + 1e-8)
        results.append((name, max_err, rel_err))

    print(f"\n  {'단면 유형':<30} {'최대절대오차':>15} {'최대상대오차':>12}")
    for name, abs_err, rel_err in results:
        flag = "⚠️  " if rel_err > 0.05 else "✓  "
        print(f"  {flag}{name:<28} {abs_err:>15.4f} {rel_err*100:>11.2f}%")


# ─────────────────────────────────────────────────────────────
# TEST 6: 실제 B-pillar 유사 단면에서 학습 수렴 영향
# ─────────────────────────────────────────────────────────────

def test_optimization_convergence():
    """최적화 관점: 잘못된 그래디언트가 수렴에 영향을 주는가"""
    print("\n" + "="*60)
    print("TEST 6: 최적화 수렴 비교 (target Mp = 1e6 Nmm)")
    print("="*60)

    torch.manual_seed(42)
    N = 8
    y_init = torch.linspace(0, 200, N)
    t_fixed = torch.ones(N, 1) * 5.0
    fy_fixed = torch.ones(N, 1) * 355.0
    target_mp = 1e6
    edge_index = torch.zeros(2, 1, dtype=torch.long)

    results_orig = []
    results_corr = []

    for version in ["original", "corrected"]:
        y_param = torch.nn.Parameter(y_init.clone())
        optimizer = torch.optim.Adam([y_param], lr=1.0)

        history = []
        for step in range(200):
            optimizer.zero_grad()
            coords_for_grad = torch.stack([torch.zeros(N), y_param], dim=1)

            if version == "original":
                mp = ImplicitPNASolver_Original.apply(coords_for_grad, t_fixed, fy_fixed, edge_index, 30)
            else:
                mp = ImplicitPNASolver_Corrected.apply(coords_for_grad, t_fixed, fy_fixed, 30)

            loss = (mp - target_mp) ** 2 / target_mp ** 2
            loss.backward()
            torch.nn.utils.clip_grad_norm_([y_param], 10.0)
            optimizer.step()
            history.append(mp.item())

        if version == "original":
            results_orig = history
        else:
            results_corr = history

    print(f"\n  초기 Mp: {results_orig[0]:.2f} Nmm")
    print(f"  목표 Mp: {target_mp:.2f} Nmm")
    print(f"\n  {'Step':>5} {'원본 Mp':>15} {'수정 Mp':>15}")
    for step in [0, 10, 50, 100, 199]:
        print(f"  {step:>5} {results_orig[step]:>15.2f} {results_corr[step]:>15.2f}")

    final_err_orig = abs(results_orig[-1] - target_mp) / target_mp * 100
    final_err_corr = abs(results_corr[-1] - target_mp) / target_mp * 100
    print(f"\n  최종 오차: 원본 {final_err_orig:.2f}%, 수정 {final_err_corr:.2f}%")


# ─────────────────────────────────────────────────────────────
# 메인 실행
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("ImplicitPNASolver 검증 시작")
    print("PyTorch version:", torch.__version__)

    test_symmetric_section()
    test_asymmetric_section()
    test_dg_dy_sign()
    test_indirect_term()
    test_gradient_accuracy()
    test_optimization_convergence()

    print("\n" + "="*60)
    print("검증 완료")
    print("="*60)


# ─────────────────────────────────────────────────────────────
# TEST 7: 코드 자체의 Forward 함수에 대한 수치 미분 vs IFT 비교
# (Forward 함수의 정확성과 별개로, backward 일관성 검증)
# ─────────────────────────────────────────────────────────────

def compute_mp_code_forward(y_vals, t_flat, fy_flat, n_iter=30):
    """코드의 forward와 완전히 동일한 Mp 계산 (no_grad, numpy-like)"""
    y = y_vals.clone()
    y_lo = y.min().clone()
    y_hi = y.max().clone()
    for _ in range(n_iter):
        y_mid = 0.5 * (y_lo + y_hi)
        F_tens = torch.sum(t_flat * fy_flat * torch.clamp(y - y_mid, min=0.0))
        F_comp = torch.sum(t_flat * fy_flat * torch.clamp(y_mid - y, min=0.0))
        if F_tens > F_comp:
            y_lo = y_mid
        else:
            y_hi = y_mid
    y_pna = 0.5 * (y_lo + y_hi)
    d = torch.abs(y - y_pna)
    return torch.sum(t_flat * fy_flat * d).item()


def test_backward_consistency():
    """코드 forward의 수치 미분 vs 코드 IFT backward (자체 일관성 검증)"""
    print("\n" + "="*60)
    print("TEST 7: 코드 자체 Forward에 대한 Backward 일관성 검증")
    print("  (올바른 PNA 아닌, 코드의 elastic NA 기준으로 수치미분)")
    print("="*60)

    test_cases = {
        "대칭 균일 (6nodes)": {
            "y": torch.linspace(0.0, 300.0, 6),
            "t": torch.ones(6, 1) * 5.0,
            "fy": torch.ones(6, 1) * 355.0,
        },
        "비대칭 두께 (3nodes)": {
            "y": torch.tensor([0.0, 50.0, 150.0]),
            "t": torch.tensor([[10.0], [5.0], [20.0]]),
            "fy": torch.ones(3, 1) * 355.0,
        },
        "비균일 항복강도 (4nodes)": {
            "y": torch.tensor([0.0, 50.0, 100.0, 150.0]),
            "t": torch.ones(4, 1) * 5.0,
            "fy": torch.tensor([[235.0], [235.0], [355.0], [355.0]]),
        },
    }

    for name, case in test_cases.items():
        y_vals = case["y"]
        t_vals = case["t"]
        fy_vals = case["fy"]
        N = len(y_vals)
        edge_index = torch.zeros(2, 1, dtype=torch.long)
        t_flat = t_vals.squeeze(-1)
        fy_flat = fy_vals.squeeze(-1)

        # IFT 그래디언트 (코드의 backward)
        coords = torch.stack([torch.zeros(N), y_vals], dim=1).requires_grad_(True)
        mp = ImplicitPNASolver_Original.apply(coords, t_vals, fy_vals, edge_index, 30)
        mp.backward()
        grads_ift = coords.grad[:, 1].detach().clone()

        # 코드의 forward 함수에 대한 수치 미분
        eps = 1e-3
        grads_num_code = torch.zeros(N)
        for i in range(N):
            y_plus = y_vals.clone(); y_plus[i] += eps
            y_minus = y_vals.clone(); y_minus[i] -= eps
            mp_plus = compute_mp_code_forward(y_plus, t_flat, fy_flat)
            mp_minus = compute_mp_code_forward(y_minus, t_flat, fy_flat)
            grads_num_code[i] = (mp_plus - mp_minus) / (2 * eps)

        max_err = (grads_ift - grads_num_code).abs().max().item()
        rel_err = max_err / (grads_num_code.abs().max().item() + 1e-8)

        print(f"\n  [{name}]")
        print(f"  {'node':>4} {'y':>8} {'IFT 그래디언트':>15} {'수치미분(코드)':>15} {'오차':>10}")
        for i in range(N):
            err = abs(grads_ift[i].item() - grads_num_code[i].item())
            print(f"  {i:>4} {y_vals[i]:>8.1f} {grads_ift[i].item():>15.4f} {grads_num_code[i].item():>15.4f} {err:>10.4f}")
        print(f"  최대 상대오차: {rel_err*100:.2f}% {'-> OK' if rel_err < 0.05 else '-> 불일치!'}")


if __name__ == "__main__":
    test_backward_consistency()
