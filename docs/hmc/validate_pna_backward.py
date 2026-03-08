#!/usr/bin/env python
# coding: utf-8
"""
ImplicitPNASolver 역전파 검증 코드
구조: 1 section (floor), 2 part (Outer + Inner)

검증 항목:
1. Forward PNA 정확도 (bisection vs. 해석해)
2. IFT dg/dy 부호 버그 검출 (finite difference + gradcheck)
3. Mp 그래디언트 전체 검증 (direct + indirect)
4. 결과 시각화
"""

import math
import numpy as np
import torch
import torch.nn.functional as F
import matplotlib
matplotlib.use('Agg')  # non-interactive backend (no display needed)
import matplotlib.pyplot as plt
from torch.autograd import Function, gradcheck


# ─────────────────────────────────────────────────────────────
# 1. 공통 bisection forward
# ─────────────────────────────────────────────────────────────

def bisect_pna(y, t, fy, n_iter=40):
    """y_pna 위치만 반환 (no_grad). torch 텐서 유지."""
    y_lo = y.min().clone()
    y_hi = y.max().clone()
    for _ in range(n_iter):
        y_mid = 0.5 * (y_lo + y_hi)
        F_tens = (t * fy * torch.clamp(y - y_mid, min=0.0)).sum()
        F_comp = (t * fy * torch.clamp(y_mid - y, min=0.0)).sum()
        # 조건부 업데이트 (tensor 유지)
        if F_tens > F_comp:
            y_lo = y_mid
        else:
            y_hi = y_mid
    return 0.5 * (y_lo + y_hi)


def analytical_pna(y, t, fy):
    """
    해석해: 균일 배열에서 PNA 계산
    g = Σ t_i*fy_i*(y_i - y_pna) = 0
    → y_pna = Σ(t_i*fy_i*y_i) / Σ(t_i*fy_i)   [소성 도심 = 면적 중심]

    주의: 이 식은 g = Σ t*fy*(y - y_pna) = 0의 해이지만,
    실제 bisection은 F_tens = F_comp를 찾으므로 동일.
    """
    return (t * fy * y).sum() / (t * fy).sum()


# ─────────────────────────────────────────────────────────────
# 2. 버전 A: 원본 코드 (dg_dy = s * t * fy) — 버그 있음
# ─────────────────────────────────────────────────────────────

class PNASolverBuggy(Function):
    """원본 20260226_v3.py의 ImplicitPNASolver 역전파 로직 그대로."""

    @staticmethod
    def forward(ctx, y, t, fy):
        with torch.no_grad():
            y_pna = bisect_pna(y, t, fy)
        ctx.save_for_backward(y, t, fy, y_pna.unsqueeze(0))
        return y_pna

    @staticmethod
    def backward(ctx, grad_output):
        y, t, fy, y_pna_buf = ctx.saved_tensors
        y_pna = y_pna_buf.squeeze(0)

        s = torch.sign(y - y_pna)
        dg_dy_pna = -torch.sum(t * fy)
        dg_dy = s * t * fy                           # ← 원본: 버그 의심 부분
        dy_pna_dy = -dg_dy / (dg_dy_pna + 1e-12)    # IFT

        return grad_output * dy_pna_dy, None, None


class MpSolverBuggy(Function):
    """원본 코드의 Mp 역전파 (y_pna + Mp 포함)."""

    @staticmethod
    def forward(ctx, y, t, fy):
        with torch.no_grad():
            y_pna = bisect_pna(y, t, fy)
        d = torch.abs(y - y_pna)
        mp = (t * fy * d).sum()
        ctx.save_for_backward(y, t, fy, y_pna.unsqueeze(0))
        return mp

    @staticmethod
    def backward(ctx, grad_output):
        y, t, fy, y_pna_buf = ctx.saved_tensors
        y_pna = y_pna_buf.squeeze(0)
        s = torch.sign(y - y_pna)

        dg_dy_pna = -torch.sum(t * fy)
        dg_dy = s * t * fy                           # ← 원본: 버그 의심
        dy_pna_dy = -dg_dy / (dg_dy_pna + 1e-12)

        direct = t * fy * s
        indirect = -torch.sum(t * fy * s) * dy_pna_dy
        dMp_dy = direct + indirect

        grad_coords_y = grad_output * dMp_dy
        return grad_coords_y, None, None


# ─────────────────────────────────────────────────────────────
# 3. 버전 B: 수정된 IFT (dg_dy = t * fy) — 수학적으로 올바름
# ─────────────────────────────────────────────────────────────

class PNASolverFixed(Function):
    """
    수정된 역전파:
    g = F_tens - F_comp에서
    ∂g/∂y_i = t_i*fy_i (부호 무관, y_i 위/아래 모두 양수)
    증명:
      y_i > y_pna: ∂F_tens/∂y_i = t_i*fy_i, ∂F_comp/∂y_i = 0 → +t_i*fy_i
      y_i < y_pna: ∂F_tens/∂y_i = 0, ∂F_comp/∂y_i = -t_i*fy_i → +t_i*fy_i
    """

    @staticmethod
    def forward(ctx, y, t, fy):
        with torch.no_grad():
            y_pna = bisect_pna(y, t, fy)
        ctx.save_for_backward(y, t, fy, y_pna.unsqueeze(0))
        return y_pna

    @staticmethod
    def backward(ctx, grad_output):
        y, t, fy, y_pna_buf = ctx.saved_tensors
        y_pna = y_pna_buf.squeeze(0)

        dg_dy_pna = -torch.sum(t * fy)
        dg_dy = t * fy                               # ← 수정: sign 제거
        dy_pna_dy = -dg_dy / (dg_dy_pna + 1e-12)    # 항상 양수

        return grad_output * dy_pna_dy, None, None


class MpSolverFixed(Function):
    """수정된 Mp 역전파."""

    @staticmethod
    def forward(ctx, y, t, fy):
        with torch.no_grad():
            y_pna = bisect_pna(y, t, fy)
        d = torch.abs(y - y_pna)
        mp = (t * fy * d).sum()
        ctx.save_for_backward(y, t, fy, y_pna.unsqueeze(0))
        return mp

    @staticmethod
    def backward(ctx, grad_output):
        y, t, fy, y_pna_buf = ctx.saved_tensors
        y_pna = y_pna_buf.squeeze(0)
        s = torch.sign(y - y_pna)

        dg_dy_pna = -torch.sum(t * fy)
        dg_dy = t * fy                               # ← 수정
        dy_pna_dy = -dg_dy / (dg_dy_pna + 1e-12)

        direct = t * fy * s
        indirect = -torch.sum(t * fy * s) * dy_pna_dy
        dMp_dy = direct + indirect

        grad_coords_y = grad_output * dMp_dy
        return grad_coords_y, None, None


# ─────────────────────────────────────────────────────────────
# 4. 1 Section / 2 Part 단면 생성
# ─────────────────────────────────────────────────────────────

def build_simple_section(n_nodes_per_part=10):
    """
    1 section (floor=0), 2 parts: Outer(part 0) + Inner(part 2)

    구조 (20260226_v3.py 참고):
      Outer: y ≈ 50mm (상단), t=1.5mm, fy=1500 MPa
      Inner: y ≈ 20mm (하단), t=1.5mm, fy=1200 MPa
      양 끝 4개 노드(i=0,1,8,9)는 fixed (y=0으로 합류)

    Returns:
      y, t, fy tensors (free nodes only for gradient test)
      y_all, t_all, fy_all (전체, fixed 포함)
    """
    # ── 전체 노드 좌표 ──────────────────────────────────────────
    rows = []
    for part, y_base, t_val, fy_val in [(0, 50.0, 1.5, 1500.0),
                                          (2, 20.0, 1.5, 1200.0)]:
        for i in range(n_nodes_per_part):
            x_coord = i * (100.0 / (n_nodes_per_part - 1))
            is_fixed = (i in [0, 1, n_nodes_per_part - 2, n_nodes_per_part - 1])
            y_coord = 0.0 if is_fixed else y_base
            rows.append((y_coord, t_val, fy_val, int(is_fixed), part))

    data = torch.tensor(rows, dtype=torch.double)  # double for gradcheck
    y_all  = data[:, 0]
    t_all  = data[:, 1]
    fy_all = data[:, 2]
    fixed  = data[:, 3].bool()
    parts  = data[:, 4].long()

    return y_all, t_all, fy_all, fixed, parts


# ─────────────────────────────────────────────────────────────
# 5. Finite Difference 그래디언트 계산
# ─────────────────────────────────────────────────────────────

def finite_difference_dy_pna(y, t, fy, eps=1e-5):
    """∂y_pna/∂y_i 수치 미분."""
    grad = torch.zeros_like(y)
    for i in range(len(y)):
        y_p = y.clone(); y_p[i] += eps
        y_m = y.clone(); y_m[i] -= eps
        pna_p = bisect_pna(y_p, t, fy)
        pna_m = bisect_pna(y_m, t, fy)
        grad[i] = (pna_p - pna_m) / (2 * eps)
    return grad


def finite_difference_dMp(y, t, fy, eps=1e-5):
    """∂Mp/∂y_i 수치 미분."""
    grad = torch.zeros_like(y)
    for i in range(len(y)):
        def mp_val(y_):
            y_pna = bisect_pna(y_, t, fy)
            return (t * fy * torch.abs(y_ - y_pna)).sum()
        y_p = y.clone(); y_p[i] += eps
        y_m = y.clone(); y_m[i] -= eps
        grad[i] = (mp_val(y_p) - mp_val(y_m)) / (2 * eps)
    return grad


# ─────────────────────────────────────────────────────────────
# 6. 검증 실행
# ─────────────────────────────────────────────────────────────

def run_validation():
    print("=" * 70)
    print("ImplicitPNASolver 역전파 검증")
    print("구조: 1 Section / 2 Parts (Outer + Inner)")
    print("=" * 70)

    y_all, t_all, fy_all, fixed, parts = build_simple_section(n_nodes_per_part=10)

    # ── TEST 0: 최소 예시 (2 노드) ──────────────────────────────
    print("\n[Test 0] 2-노드 최소 예시")
    print("  y=[10, 30], t=fy=1  → 해석해 y_pna=20")
    y2 = torch.tensor([10.0, 30.0], dtype=torch.double)
    t2 = torch.tensor([1.0, 1.0],  dtype=torch.double)
    fy2 = torch.tensor([1.0, 1.0], dtype=torch.double)
    pna2 = bisect_pna(y2, t2, fy2).item()
    print(f"  bisection y_pna = {pna2:.6f}  (해석해: 20.0)")
    fd2 = finite_difference_dy_pna(y2, t2, fy2)
    print(f"  FD ∂y_pna/∂y: {fd2.tolist()}")
    print(f"  Buggy IFT: s*t*fy/Σ(t*fy) = {torch.sign(y2-pna2).tolist()} * 1 / 2 = {(torch.sign(y2-pna2)/2).tolist()}")
    print(f"  Fixed IFT: t*fy/Σ(t*fy) = {(t2*fy2/(t2*fy2).sum()).tolist()}")
    print()

    # ── TEST 1: Forward PNA 정확도 ─────────────────────────────
    print("[Test 1] Forward PNA 정확도 (1 section / 2 parts)")
    y_fwd   = y_all.detach()
    pna_bis = bisect_pna(y_fwd, t_all, fy_all).item()
    pna_ana = analytical_pna(y_fwd, t_all, fy_all).item()
    pna_true = pna_ana  # 균일 배치이므로 해석해 = 가중 평균

    print(f"  bisection  y_pna = {pna_bis:.6f} mm")
    print(f"  analytical y_pna = {pna_ana:.6f} mm")
    print(f"  오차              = {abs(pna_bis - pna_ana):.2e} mm")
    print()

    # ── TEST 2: ∂y_pna/∂y 비교 (Buggy vs Fixed vs FD) ─────────
    print("[Test 2] ∂y_pna/∂y 그래디언트 비교")

    # Finite difference (기준)
    fd_grad = finite_difference_dy_pna(y_fwd, t_all, fy_all)

    # Buggy backward
    y_bug = y_fwd.clone().requires_grad_(True)
    pna_bug = PNASolverBuggy.apply(y_bug, t_all, fy_all)
    pna_bug.backward()
    grad_buggy = y_bug.grad.clone().detach()

    # Fixed backward
    y_fix = y_fwd.clone().requires_grad_(True)
    pna_fix = PNASolverFixed.apply(y_fix, t_all, fy_all)
    pna_fix.backward()
    grad_fixed = y_fix.grad.clone().detach()

    err_buggy = (grad_buggy - fd_grad).abs()
    err_fixed = (grad_fixed - fd_grad).abs()

    print(f"  {'Node':>4}  {'Part':>4}  {'FD':>10}  {'Buggy':>10}  {'Fixed':>10}  {'Err_Bug':>10}  {'Err_Fix':>10}")
    for i in range(len(y_fwd)):
        part_str = "Outer" if parts[i] == 0 else "Inner"
        print(f"  {i:>4}  {part_str:>5}  {fd_grad[i]:>10.6f}  "
              f"{grad_buggy[i]:>10.6f}  {grad_fixed[i]:>10.6f}  "
              f"{err_buggy[i]:>10.2e}  {err_fixed[i]:>10.2e}")

    max_err_bug = err_buggy.max().item()
    max_err_fix = err_fixed.max().item()
    print(f"\n  Buggy 최대 오차: {max_err_bug:.4e}  ← {'FAIL' if max_err_bug > 1e-4 else 'PASS'}")
    print(f"  Fixed 최대 오차: {max_err_fix:.4e}  ← {'FAIL' if max_err_fix > 1e-4 else 'PASS'}")
    print()

    # ── TEST 3: ∂Mp/∂y 비교 ────────────────────────────────────
    print("[Test 3] ∂Mp/∂y 그래디언트 비교")

    fd_mp = finite_difference_dMp(y_fwd, t_all, fy_all)

    y_bug2 = y_fwd.clone().requires_grad_(True)
    mp_bug = MpSolverBuggy.apply(y_bug2, t_all, fy_all)
    mp_bug.backward()
    grad_mp_buggy = y_bug2.grad.clone().detach()

    y_fix2 = y_fwd.clone().requires_grad_(True)
    mp_fix = MpSolverFixed.apply(y_fix2, t_all, fy_all)
    mp_fix.backward()
    grad_mp_fixed = y_fix2.grad.clone().detach()

    err_mp_bug = (grad_mp_buggy - fd_mp).abs()
    err_mp_fix = (grad_mp_fixed - fd_mp).abs()

    print(f"  {'Node':>4}  {'Part':>5}  {'FD_Mp':>12}  {'Bug_Mp':>12}  {'Fix_Mp':>12}  {'Err_Bug':>10}  {'Err_Fix':>10}")
    for i in range(len(y_fwd)):
        part_str = "Outer" if parts[i] == 0 else "Inner"
        print(f"  {i:>4}  {part_str:>5}  {fd_mp[i]:>12.2f}  "
              f"{grad_mp_buggy[i]:>12.2f}  {grad_mp_fixed[i]:>12.2f}  "
              f"{err_mp_bug[i]:>10.2e}  {err_mp_fix[i]:>10.2e}")

    max_err_mp_bug = err_mp_bug.max().item()
    max_err_mp_fix = err_mp_fix.max().item()
    status_bug = 'FAIL' if max_err_mp_bug > 1.0 else 'PASS'
    status_fix = 'FAIL' if max_err_mp_fix > 1.0 else 'PASS'
    print(f"\n  Mp 그래디언트 Buggy 최대 오차: {max_err_mp_bug:.4e}  <- {status_bug}")
    print(f"  Mp 그래디언트 Fixed 최대 오차: {max_err_mp_fix:.4e}  <- {status_fix}")
    print()

    # ── TEST 4: torch.autograd.gradcheck ───────────────────────
    print("[Test 4] torch.autograd.gradcheck (y_pna)")
    y_gc = y_fwd[:4].clone().requires_grad_(True)  # 4노드로 축소 (속도)
    t_gc  = t_all[:4]
    fy_gc = fy_all[:4]

    print("  BUGGY gradcheck ...", end=" ")
    try:
        result = gradcheck(lambda y_: PNASolverBuggy.apply(y_, t_gc, fy_gc),
                           (y_gc,), eps=1e-6, atol=1e-4, raise_exception=False)
        print("PASS" if result else "FAIL (버그 확인됨)")
    except Exception as e:
        print(f"ERROR: {e}")

    y_gc2 = y_fwd[:4].clone().requires_grad_(True)
    print("  FIXED gradcheck  ...", end=" ")
    try:
        result = gradcheck(lambda y_: PNASolverFixed.apply(y_, t_gc, fy_gc),
                           (y_gc2,), eps=1e-6, atol=1e-4, raise_exception=False)
        print("PASS (수정 확인됨)" if result else "FAIL")
    except Exception as e:
        print(f"ERROR: {e}")

    print()

    # ── TEST 5: y_pna 예측 정확도 시각화 ───────────────────────
    print("[Test 5] y_pna 예측 정확도 - 파라미터 스윕")

    # Outer y좌표를 변화시켰을 때 PNA 변화
    outer_y_range = np.linspace(30.0, 80.0, 50)
    pna_vals = []
    for oy in outer_y_range:
        y_test = y_fwd.clone()
        # Outer 노드 (part 0 = 앞 10개) free nodes만 조정
        outer_free_mask = (parts == 0) & (~fixed)
        y_test[outer_free_mask] = float(oy)
        pna_vals.append(bisect_pna(y_test, t_all, fy_all).item())
    pna_vals = np.array(pna_vals)

    # 해석해 (고정 Inner + 변화 Outer)
    n_outer_free = (outer_free_mask).sum().item()
    n_inner_free = ((parts == 2) & (~fixed)).sum().item()
    n_fixed = fixed.sum().item()
    t_outer, fy_outer = 1.5, 1500.0
    t_inner, fy_inner = 1.5, 1200.0
    inner_y0 = 20.0
    fixed_y0 = 0.0

    def analytical_pna_sweep(oy):
        # Σ(t*fy*y) / Σ(t*fy)
        num = (n_outer_free * t_outer * fy_outer * oy +
               n_inner_free * t_inner * fy_inner * inner_y0 +
               n_fixed * 1.5 * 1350.0 * fixed_y0)  # fixed nodes (mixed)
        # 실제 fixed는 Outer/Inner 혼합이므로 y_all[fixed] 사용
        fixed_num = (t_all[fixed] * fy_all[fixed] * y_fwd[fixed]).sum().item()
        fixed_den = (t_all[fixed] * fy_all[fixed]).sum().item()
        num2 = (n_outer_free * t_outer * fy_outer * oy +
                n_inner_free * t_inner * fy_inner * inner_y0 +
                fixed_num)
        den2 = (n_outer_free * t_outer * fy_outer +
                n_inner_free * t_inner * fy_inner +
                fixed_den)
        return num2 / den2

    pna_ana_vals = np.array([analytical_pna_sweep(oy) for oy in outer_y_range])

    # ── 시각화 ─────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Plot 1: PNA sweep
    ax = axes[0]
    ax.plot(outer_y_range, pna_vals, 'b-o', ms=4, label='bisection PNA')
    ax.plot(outer_y_range, pna_ana_vals, 'r--', label='analytical PNA')
    ax.set_xlabel('Outer Y 좌표 (mm)')
    ax.set_ylabel('PNA 위치 (mm)')
    ax.set_title('PNA Forward 정확도\n(Outer Y 변화에 따른 PNA)')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Plot 2: ∂y_pna/∂y 비교 (Test 2 결과)
    ax = axes[1]
    x_idx = np.arange(len(y_fwd))
    ax.bar(x_idx - 0.3, fd_grad.numpy(),     0.28, label='FD (수치)', color='green', alpha=0.7)
    ax.bar(x_idx,       grad_buggy.numpy(),  0.28, label='Buggy IFT', color='red',   alpha=0.7)
    ax.bar(x_idx + 0.3, grad_fixed.numpy(),  0.28, label='Fixed IFT', color='blue',  alpha=0.7)
    ax.axhline(0, color='k', lw=0.5)
    ax.set_xlabel('노드 인덱스')
    ax.set_ylabel('∂y_pna/∂y_i')
    ax.set_title('PNA 그래디언트 비교\n(수치 vs Buggy vs Fixed)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis='y')
    # 파트 구분선
    ax.axvline(9.5, color='gray', ls='--', lw=1, label='Outer|Inner')
    ax.text(4.5, ax.get_ylim()[1]*0.9, 'Outer\n(part 0)', ha='center', fontsize=8, color='navy')
    ax.text(14.5, ax.get_ylim()[1]*0.9, 'Inner\n(part 2)', ha='center', fontsize=8, color='darkred')

    # Plot 3: ∂Mp/∂y 비교
    ax = axes[2]
    ax.bar(x_idx - 0.3, fd_mp.numpy(),          0.28, label='FD (수치)', color='green', alpha=0.7)
    ax.bar(x_idx,       grad_mp_buggy.numpy(),   0.28, label='Buggy Mp', color='red',   alpha=0.7)
    ax.bar(x_idx + 0.3, grad_mp_fixed.numpy(),   0.28, label='Fixed Mp', color='blue',  alpha=0.7)
    ax.axhline(0, color='k', lw=0.5)
    ax.set_xlabel('노드 인덱스')
    ax.set_ylabel('∂Mp/∂y_i (N·mm/mm)')
    ax.set_title('Mp 그래디언트 비교\n(수치 vs Buggy vs Fixed)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis='y')
    ax.axvline(9.5, color='gray', ls='--', lw=1)

    plt.suptitle('ImplicitPNASolver Backward Validation - 1 Section / 2 Parts',
                 fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig('pna_backward_validation.png', dpi=120, bbox_inches='tight')
    print("  시각화 저장: pna_backward_validation.png")
    plt.show()

    # ── 요약 ─────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("검증 요약")
    print("=" * 70)
    print(f"  Forward PNA 오차 (bisection vs 해석해): {abs(pna_bis - pna_ana):.2e} mm")
    print()
    print("  역전파 버그 분석:")
    print("  원본 코드: dg_dy = sign(y - y_pna) * t * fy")
    print("  올바른 식: dg_dy = t * fy  (부호 무관, 모든 노드에서 +t*fy)")
    print()
    s1 = 'FAIL' if max_err_bug > 1e-4 else 'PASS'
    s2 = 'FAIL' if max_err_fix > 1e-4 else 'PASS'
    s3 = 'FAIL' if max_err_mp_bug > 1.0 else 'PASS'
    s4 = 'FAIL' if max_err_mp_fix > 1.0 else 'PASS'
    print(f"  dy_pna/dy  Buggy max err: {max_err_bug:.4e}  ({s1})")
    print(f"  dy_pna/dy  Fixed max err: {max_err_fix:.4e}  ({s2})")
    print(f"  dMp/dy     Buggy max err: {max_err_mp_bug:.4e}  ({s3})")
    print(f"  dMp/dy     Fixed max err: {max_err_mp_fix:.4e}  ({s4})")
    print()
    print("  IFT 부호 오류로 인한 영향:")
    print("  - 압축측(y_i < y_pna) 노드의 ∂y_pna/∂y_i 부호 반전")
    print("  - Mp 역전파의 indirect 항 오류 전파")
    print("  - 비대칭 단면에서 최적화 방향 왜곡 가능성")
    print("=" * 70)

    return {
        'pna_bisection': pna_bis,
        'pna_analytical': pna_ana,
        'grad_pna_buggy': grad_buggy,
        'grad_pna_fixed': grad_fixed,
        'grad_pna_fd': fd_grad,
        'grad_mp_buggy': grad_mp_buggy,
        'grad_mp_fixed': grad_mp_fixed,
        'grad_mp_fd': fd_mp,
        'max_err_pna_bug': max_err_bug,
        'max_err_pna_fix': max_err_fix,
        'max_err_mp_bug': max_err_mp_bug,
        'max_err_mp_fix': max_err_mp_fix,
    }


if __name__ == "__main__":
    results = run_validation()
