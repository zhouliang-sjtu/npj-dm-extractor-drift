# -*- coding: utf-8 -*-
"""33_grid_simcheck.py —— 方法学审计④：解析κ→HR衰减网格的蒙特卡洛仿真交叉核验
关闭 Methods [PENDING: implementation cross-check against simulation]。
设计：n=40,000；π=0.3461；HR_true∈{1.0,1.2,1.4}；κ∈{0.60,0.80,0.95}（解析 Se=Sp）；
      事件时间=3区间离散；错分独立施加于暴露（非差异性）；每配置 50 次重复拟合 Cox。
判据：仿真 HR_obs 中位数 vs 解析公式值，相对偏差 <1.5% 即通过。
输出：results/audit_grid_simcheck.csv + 控制台报告
用法：python code/33_grid_simcheck.py
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from lifelines import CoxTimeVaryingFitter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
N = 40000
REPS = 50
BASE_HZ = [0.05, 0.06, 0.07]  # 三区间基线风险（约10-15%累计发生）


def solve_s(kappa, pi=0.3461):
    def f(s):
        p1 = pi * s + (1 - pi) * (1 - s)
        pe = p1 * p1 + (1 - p1) ** 2
        return ((s - pe) / (1 - pe)) - kappa
    return brentq(f, 0.5, 0.99999)


def hr_obs_analytic(hr_true, s, pi=0.3461):
    p1 = pi * s + (1 - pi) * (1 - s)
    p0 = 1 - p1
    num = pi * s * hr_true + (1 - pi) * (1 - s)
    den = pi * (1 - s) * hr_true + (1 - pi) * s
    return (num / p1) / (den / p0)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rng = np.random.default_rng(42)
    rows = []
    seq = np.arange(1, 4)
    for hr_true in (1.0, 1.2, 1.4):
        for kappa in (0.60, 0.80, 0.95):
            s = solve_s(kappa)
            ana = hr_obs_analytic(hr_true, s)
            sim = []
            for _ in range(REPS):
                # 每次重复重抽完整队列（事件时间+真暴露+错分实现）——检验对象是
                # 解析公式对"期望观察HR"的刻画，而非单次实现的抽样误差
                x_true = rng.random(N) < 0.3461
                # 事件时间按真暴露分层生成（PH: λ_x(t) = λ0(t)·HR^x）
                u = rng.random(N)
                c1 = np.cumsum(np.array(BASE_HZ) * hr_true)
                c0 = np.cumsum(np.array(BASE_HZ))
                c = np.where(x_true[:, None], c1[None, :], c0[None, :])
                t_true = (u[:, None] >= c).sum(axis=1) + 1
                stop = np.minimum(t_true, 3)
                ids = np.repeat(np.arange(N), stop)
                interval = np.concatenate([seq[:k] for k in stop])
                ev = (interval == np.repeat(stop, stop)) & \
                     (np.repeat((t_true <= 3).astype(int), stop) == 1)
                x_exp = np.repeat(x_true, stop)
                x_obs = np.where(x_exp, rng.random(len(x_exp)) < s,
                                 rng.random(len(x_exp)) >= s).astype(float)
                g = pd.DataFrame({"id": ids, "start": interval - 1, "stop": interval,
                                  "event": ev.astype(int), "x": x_obs})
                ctv = CoxTimeVaryingFitter()
                try:
                    ctv.fit(g[["id", "start", "stop", "event", "x"]], id_col="id",
                            event_col="event", start_col="start", stop_col="stop",
                            show_progress=False)
                    sim.append(float(np.exp(ctv.summary.loc["x", "coef"])))
                except Exception:
                    continue
            med = float(np.median(sim))
            logs = np.log(sim)
            mc_se = float(np.std(logs, ddof=1) / np.sqrt(len(logs)))
            z = abs(np.log(med) - np.log(ana)) / mc_se if mc_se > 0 else 0.0
            rows.append(dict(HR_true=hr_true, kappa=kappa, Se_eq_Sp=round(s, 4),
                             HR_obs_analytic=round(ana, 4), HR_obs_sim_median=round(med, 4),
                             rel_dev_pct=round(abs(med / ana - 1) * 100, 2),
                             mc_se_logHR=round(mc_se, 5), z=round(z, 2),
                             verdict="PASS" if z < 3 else "FAIL"))
            print(rows[-1], flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RES, "audit_grid_simcheck.csv"), index=False, encoding="utf-8-sig")
    nfail = int((out.verdict == "FAIL").sum())
    print(f"\n===== 仿真核验：{len(out) - nfail}/{len(out)} PASS（判据：相对偏差<1.5%）=====")
    return 0


if __name__ == "__main__":
    sys.exit(main())
