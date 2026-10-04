# FRACTAL FLOW — PHASE 1E FORMULA MATRIX

**Phase**: 1E — Volatility Engine Metrics
**Status**: COMPLETE

---

## Metric & Formula Registry

| Metric Name | Mathematical Formula / Definition | Source Specification | Inputs | Lookback / Window | Warmup Requirement | Causal Boundary | Numerical Type | Missing-Data Behavior | Classification | Version | Calibration Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **True Range (TR)** | $\max(H_t - L_t, \|H_t - C_{t-1}\|, \|L_t - C_{t-1}\|)$ | `docs/04_STRUCTURE_ENGINE.md` | $H_t, L_t, C_{t-1}$ | 1 bar | 1 bar | $t_{input} \le t$ | `Decimal` | Retain previous close; zero range gap handling | `EXECUTABLE_CANONICAL` | v1.0 | CALIBRATED |
| **Wilder ATR-14** | $ATR_t = \frac{13 \times ATR_{t-1} + TR_t}{14}$ | `docs/04_STRUCTURE_ENGINE.md` | $TR_t, ATR_{t-1}$ | 14 bars | 14 bars | $t_{input} \le t$ | `Decimal` | SMA initialization on initial 14 bars | `EXECUTABLE_CANONICAL` | v1.0 | CALIBRATED |
| **Realized Volatility** | $\sqrt{\frac{\sum (r_i - \bar{r})^2}{N-1}} \times \sqrt{252 \times 1440}$ | `docs/07_REGIME_ENGINE.md` | Log returns $r_i = \ln(C_i / C_{i-1})$ | 20 bars | 20 bars | $t_{input} \le t$ | `float` (Statistical) | Skip missing bars in return series | `EXECUTABLE_CANONICAL` | v1.0 | CALIBRATED |
| **Local Volatility** | $\frac{\sigma(C_{t-4..t})}{C_t}$ | `docs/04_STRUCTURE_ENGINE.md` | Close prices $C_{t-4..t}$ | 5 bars | 5 bars | $t_{input} \le t$ | `float` (Statistical) | Zero std dev on flat data | `EXECUTABLE_CANONICAL` | v1.0 | CALIBRATED |
| **Short Volatility** | $\frac{ATR_{14}}{C_t}$ | `docs/04_STRUCTURE_ENGINE.md` | $ATR_{14}, C_t$ | 14 bars | 14 bars | $t_{input} \le t$ | `float` (Statistical) | 0.0 if close is zero | `EXECUTABLE_CANONICAL` | v1.0 | CALIBRATED |
| **Session Volatility** | $H_{session} - L_{session}$ | `docs/07_REGIME_ENGINE.md` | Session $H, L$ | Daily session | 1 bar | $t_{input} \le t$ | `Decimal` | Reset at session open boundary | `EXECUTABLE_CANONICAL` | v1.0 | CALIBRATED |
| **Rolling Percentile** | $\frac{\text{count}(ATR_{history} \le ATR_t)}{N_{history}}$ | `docs/07_REGIME_ENGINE.md` | $ATR_t, ATR_{history}$ | 100 bars | 1 bar | $t_{input} \le t$ | `float` (Statistical) | Rank over available history | `EXECUTABLE_CANONICAL` | v1.0 | CALIBRATED |
| **Range Percentile** | $\frac{\text{count}(Range_{history} \le Range_t)}{N_{history}}$ | `docs/07_REGIME_ENGINE.md` | $Range_t, Range_{history}$ | 100 bars | 1 bar | $t_{input} \le t$ | `float` (Statistical) | Rank over available history | `EXECUTABLE_CANONICAL` | v1.0 | CALIBRATED |
| **Expansion Rate** | $\frac{ATR_{short}}{ATR_{long}} - 1.0$ | `docs/04_STRUCTURE_ENGINE.md` | $ATR_{short}, ATR_{long}$ | Short 5, Long 14 | 14 bars | $t_{input} \le t$ | `float` (Statistical) | 0.0 if ATR is zero | `EXECUTABLE_CANONICAL` | v1.0 | CALIBRATED |
| **Contraction Rate** | $1.0 - \frac{ATR_{short}}{ATR_{long}}$ | `docs/04_STRUCTURE_ENGINE.md` | $ATR_{short}, ATR_{long}$ | Short 5, Long 14 | 14 bars | $t_{input} \le t$ | `float` (Statistical) | 0.0 if ATR is zero | `EXECUTABLE_CANONICAL` | v1.0 | CALIBRATED |
| **Shock Score** | $\frac{\|C_t - O_t\|}{ATR_{14}}$ | `docs/10_NEWS_SHIELD.md` | $O_t, C_t, ATR_{14}$ | 14 bars | 14 bars | $t_{input} \le t$ | `float` (Statistical) | 0.0 if ATR is zero | `EXECUTABLE_CANONICAL` | v1.0 | CALIBRATED |
