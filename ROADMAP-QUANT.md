# Quant Enhancement Roadmap

## Context

ระบบเทรดปัจจุบันใช้ rule-based ensemble + ML (LightGBM) + AI sentiment filter — ยังขาด quantitative methods แบบ institutional grade ทั้ง risk management, alpha signals, และ portfolio optimization

เป้าหมาย: เพิ่ม quant ให้ครบทุกด้าน ระดับ full complexity (GARCH, Copula, Kalman, VaR/CVaR, etc.)

## สิ่งที่มีอยู่แล้ว (ต่อยอดได้)

| Component | Location | Method |
|-----------|----------|--------|
| Kelly criterion | `risk/manager.py:99` | Fractional Kelly (0.25) |
| ATR-based vol adjustment | `risk/manager.py:69` | High/low vol lot factor |
| Regime detection | `strategy/regime.py` | ATR% + ADX threshold |
| Monte Carlo | `backtest/monte_carlo.py` | Permutation-based robustness |
| Walk-forward | `backtest/walk_forward.py` | Expanding window + bootstrap CI |
| Cointegration test | `backtest/statistical_tests.py` | ADF on spread residuals |
| Pair spread z-score | `strategy/pair_spread.py` | Rolling z-score, entry ±2σ |
| PSI drift detection | `ml/drift.py` | Population Stability Index |
| Correlation filter | `risk/correlation.py` | Static hardcoded correlations |
| ML features | `ml/features.py` | 43 features (EMA, RSI, ATR, BB, MACD, etc.) |

---

## Phase 0: Foundation Refactor

ก่อนเริ่ม Phase 1-6 ต้อง refactor ระบบเดิมให้รองรับ quant enhancement โดยไม่พังสิ่งที่มีอยู่

### 0.1 Engine Pipeline → Pluggable Architecture

**Modify:** `backend/app/bot/engine.py`

ปัจจุบัน flow เป็น: signal → permission → order (hardcoded)
Refactor เป็น pluggable pipeline ที่ Phase 6 สามารถ inject confirmation gate + UNCERTAIN state ได้:

```python
# Before: fixed flow
result = await self._generate_signal()
if await self._check_trade_permission(signal): ...

# After: pipeline-based
pipeline = [self._pre_check, self._generate_signal, self._validate, self._execute]
await self._run_pipeline(pipeline)
```

- เพิ่ม `UNCERTAIN` signal state (ปัจจุบันมีแค่ 1, 0, -1)
- เพิ่ม hook points สำหรับ confirmation gate, pre-trade reasoning

### 0.2 Regime Output → Dual Mode

**Modify:** `backend/app/strategy/regime.py`

เพิ่ม probability output โดยยังรองรับ string label เดิม:

```python
# Before: returns "trending_high_vol"
# After: returns RegimeResult(label="trending_high_vol", probabilities={"trending_high_vol": 0.7, ...})
```

- ทุกที่ที่ใช้ `regime` เป็น string ยังทำงานได้ผ่าน `.label`
- Phase 2 HMM จะ populate `.probabilities`

### 0.3 Risk Manager → Volatility Source Abstraction

**Modify:** `backend/app/risk/manager.py`

เปลี่ยนจาก hardcode ATR เป็น pluggable volatility source:

```python
# Before: calculate_lot_size(..., atr_pct=0.5)
# After: calculate_lot_size(..., volatility=VolatilityEstimate(value=0.5, source="atr"))
```

- Phase 1 GARCH จะเป็น `source="garch"` โดยไม่ต้องแก้ function signature
- Threshold (HIGH_VOL, LOW_VOL) ปรับตาม source อัตโนมัติ

### 0.4 Ensemble → Dynamic Weight Interface

**Modify:** `backend/app/strategy/ensemble.py`

เปลี่ยน weight จาก fixed tuple เป็น callable:

```python
# Before: strategies = [(ema_strat, 0.4), (ml_strat, 0.6)]
# After: strategies = [(ema_strat, weight_fn)] where weight_fn(regime, performance) -> float
```

- Backward compat: ถ้าส่ง float เข้ามาจะ wrap เป็น `lambda: float` อัตโนมัติ

### 0.5 Correlation → Async Interface

**Modify:** `backend/app/risk/correlation.py`

เปลี่ยน function เป็น async + accept data source:

```python
# Before: check_correlation_conflict(symbol, signal, positions) → sync, hardcoded
# After: await check_correlation_conflict(symbol, signal, positions, market_data) → async, pluggable
```

### 0.6 Scheduler → Job Dependency Support

**Modify:** `backend/app/bot/scheduler.py`

เพิ่ม simple job ordering mechanism:

```python
# Jobs with depends_on will wait for dependency to complete
scheduler.add_job(morning_learn, depends_on="daily_reset")
scheduler.add_job(ml_retrain, depends_on="morning_learn")
```

### 0.7 Alembic Migration — New Models

**New file:** `backend/alembic/versions/n4o5p6q7r8s9_add_quant_tables.py`

- เพิ่ม `QUANT_LEARNING` ใน `MemoryCategory` enum
- เพิ่ม `quant_metrics` table (VaR, regime, correlation snapshots)
- เพิ่ม `trade_reasoning` table (pre/post trade AI reasoning)

---

## Phase 1: Quant Risk Layer

เสริม risk management ที่มีอยู่ให้เป็น quant-grade

### 1.1 VaR/CVaR Calculator

**New file:** `backend/app/risk/var.py`

- Historical VaR (percentile-based)
- Parametric VaR (normal assumption)
- CVaR (Expected Shortfall) — average loss beyond VaR
- Cornish-Fisher VaR (adjusted for skewness + kurtosis)
- Rolling window: 60-bar default
- ใช้ใน: circuit breaker (แทน fixed % loss limit), position sizing

### 1.2 Rolling Correlation Monitor

**Modify:** `backend/app/risk/correlation.py`

- แทน hardcoded correlation ด้วย rolling correlation (30-bar window)
- DCC (Dynamic Conditional Correlation) approximation
- Correlation regime change detection (z-test on Fisher-transformed corr)
- Alert เมื่อ correlation structure เปลี่ยน (breakdown)

### 1.3 GARCH Volatility Forecast

**New file:** `backend/app/risk/garch.py`

- GARCH(1,1) model fit on returns
- Forward-looking vol forecast (1-step, 5-step)
- ใช้แทน ATR ใน: position sizing, SL/TP calculation
- EWMA fallback ถ้า GARCH fit fail (convergence issue)
- Dependencies: `arch` library

### 1.4 Portfolio-Level Risk

**New file:** `backend/app/risk/portfolio_risk.py`

- Portfolio VaR (correlation-adjusted)
- Marginal VaR per position
- Component VaR (contribution of each symbol)
- Max position limit based on marginal VaR
- Integrate กับ `_check_trade_permission()` ใน engine.py

### 1.5 UI — Risk Dashboard Enhancement

**Modify:** `frontend/app/dashboard/page.tsx`

เพิ่ม risk widgets เข้า dashboard หลัก:

- **VaR Gauge** — แสดง daily VaR/CVaR เป็น % ของ portfolio (reuse `GoldGauge` component)
- **Vol Forecast Card** — GARCH forecast vs realized ATR (stat-card with trend arrow)
- **Correlation Alert Banner** — แถบแจ้งเตือนเมื่อ correlation breakdown detected

**Modify:** `frontend/app/macro/page.tsx`

- เพิ่ม **Rolling Correlation Heatmap** — 4×4 matrix (GOLD, OIL, BTC, JPY) color-coded
- เพิ่ม **Correlation Trend Chart** — rolling correlation over time per pair

**New component:** `frontend/components/quant/CorrelationHeatmap.tsx`
**New component:** `frontend/components/quant/VaRGauge.tsx`

---

## Phase 2: Quant Alpha Signals

เพิ่ม statistical signals เข้า strategy ensemble

### 2.1 Statistical Signal Module

**New file:** `backend/app/strategy/quant_signals.py`

- **Z-score mean reversion** — rolling z-score with half-life estimation (OLS regression)
- **Hurst exponent** — classify trending (H>0.5) vs mean-reverting (H<0.5) per symbol
- **Rolling Sharpe** — detect strategy deterioration in real-time
- **Momentum factor** — risk-adjusted momentum (return / vol) cross-symbol ranking
- **Volatility breakout** — normalized ATR breakout with regime confirmation

### 2.2 Regime-Switching Model (Hamilton Filter)

**Modify:** `backend/app/strategy/regime.py`

- Hidden Markov Model (2-state: trending/ranging) via `hmmlearn`
- Smooth transition probabilities (not hard threshold)
- Per-symbol regime state + portfolio aggregate
- Integrate with ensemble weights (auto-adjust strategy weights per regime)

### 2.3 Kalman Filter

**New file:** `backend/app/strategy/kalman.py`

- Dynamic hedge ratio estimation (แทน static OLS ใน pair spread)
- Adaptive moving average (Kalman-smoothed price)
- Signal: Kalman residual z-score for mean reversion
- ใช้ใน: pair_spread.py, SL/TP trailing

### 2.4 Integrate into Ensemble

**Modify:** `backend/app/strategy/ensemble.py`

- เพิ่ม quant signals เป็น sub-strategy ใน ensemble
- Regime-adaptive weights: HMM regime → ปรับ weight ของแต่ละ strategy
- Rolling performance-weighted: strategy ที่ทำได้ดีล่าสุดได้ weight มากขึ้น

### 2.5 UI — Signal & Regime Visualization

**Modify:** `frontend/app/dashboard/page.tsx`

- **Regime Badge** — แสดง HMM state ปัจจุบัน + probability % ข้าง symbol tab (เช่น "Trending 82%")
- **Signal Confidence Bar** — แสดงว่า quant signals กี่ตัว agree/disagree (horizontal stacked bar)

**Modify:** `frontend/app/insights/page.tsx`

- เพิ่ม **Quant Signals Panel** — z-score, Hurst, rolling Sharpe per symbol
- เพิ่ม **Regime History Chart** — HMM state transitions over time (colored timeline)

**New component:** `frontend/components/quant/RegimeBadge.tsx`
**New component:** `frontend/components/quant/SignalConfidenceBar.tsx`
**New component:** `frontend/components/quant/RegimeTimeline.tsx`

---

## Phase 3: Portfolio Optimization

จัดสรร capital ข้าม 4 symbols (GOLD, OILCash, BTCUSD, USDJPY) อย่าง optimal

### 3.1 Mean-Variance Optimization (Markowitz)

**New file:** `backend/app/risk/portfolio_optimizer.py`

- Efficient frontier calculation
- Minimum variance portfolio
- Maximum Sharpe portfolio
- Black-Litterman overlay (ใช้ AI sentiment เป็น views)
- Constraints: min/max allocation per symbol, long-only
- Rebalance trigger: significant weight drift (>5%)

### 3.2 CVaR Optimization

**Same file:** `backend/app/risk/portfolio_optimizer.py`

- Minimize CVaR subject to return target
- Robust ต่อ fat tails กว่า mean-variance
- ใช้ historical simulation (not parametric)

### 3.3 Risk Parity Enhancement

**Modify:** `backend/app/strategy/risk_parity.py`

- แทน simple inverse-ATR ด้วย true risk parity (equal risk contribution)
- GARCH-forecasted vol แทน realized ATR
- Correlation-adjusted (ไม่ใช่แค่ vol)

### 3.4 Position Sizing Integration

**Modify:** `backend/app/risk/manager.py`

- Portfolio optimizer output → per-symbol lot allocation
- Kelly criterion + portfolio VaR constraint (dual bound)
- Regime-conditional sizing: HMM state → different risk budget

### 3.5 UI — Portfolio Visualization

**Modify:** `frontend/app/dashboard/page.tsx`

- **Portfolio Allocation Donut Chart** — แสดงสัดส่วน capital แต่ละ symbol (optimal vs actual)
- **Risk Contribution Bar** — แสดง % risk contribution ของแต่ละ symbol ใน portfolio

**New component:** `frontend/components/quant/PortfolioDonut.tsx`
**New component:** `frontend/components/quant/RiskContributionBar.tsx`

---

## Phase 4: Advanced Analytics & Monitoring

Dashboard + monitoring สำหรับ quant metrics

### 4.1 Quant Metrics API

**New file:** `backend/app/api/routes/quant.py`

| Endpoint | Description |
|----------|-------------|
| `GET /api/quant/var` | Current VaR/CVaR per symbol + portfolio |
| `GET /api/quant/regime` | HMM regime state + transition probabilities |
| `GET /api/quant/correlation` | Rolling correlation matrix |
| `GET /api/quant/volatility` | GARCH forecast vs realized |
| `GET /api/quant/portfolio` | Optimal weights, risk contribution |
| `GET /api/quant/signals` | Z-score, Hurst, rolling Sharpe per symbol |

### 4.2 ML Calibration

**New file:** `backend/app/ml/calibration.py`

- Platt scaling / isotonic regression for probability calibration
- Reliability diagram data (for frontend)
- Brier score tracking

### 4.3 Stress Testing

**New file:** `backend/app/backtest/stress_test.py`

- Historical scenario replay (2008, 2020 COVID, 2022 rate hikes)
- Synthetic stress: vol spike ×3, correlation breakdown, liquidity dry-up
- Portfolio impact report

### 4.4 Frontend — Dedicated Quant Page

**New file:** `frontend/app/quant/page.tsx`

รวม quant metrics ทั้งหมดไว้หน้าเดียว:

**Section 1 — Risk Overview**
- VaR/CVaR gauges per symbol (reuse `GoldGauge` adapted for risk)
- Portfolio VaR gauge (aggregate)
- GARCH vol forecast vs realized chart (AreaChart)
- Risk budget utilization progress bar

**Section 2 — Market Regime**
- HMM regime state per symbol (RegimeBadge × 4)
- Regime transition probability matrix (small heatmap)
- Regime history timeline (last 30 days)

**Section 3 — Correlation Monitor**
- 4×4 rolling correlation heatmap
- Correlation change alerts (highlighted cells)
- Correlation vs historical average comparison

**Section 4 — Alpha Signals**
- Z-score per symbol (bar chart, highlighted when extreme)
- Hurst exponent per symbol (trending vs mean-reverting indicator)
- Rolling Sharpe per strategy (line chart)
- Momentum ranking table (sorted by risk-adjusted return)

**Section 5 — Portfolio Optimization**
- Efficient frontier chart (scatter plot)
- Current vs optimal allocation (side-by-side donut)
- Rebalance recommendation (if drift > 5%)

**Section 6 — Stress Testing**
- Scenario results table (COVID, rate hike, flash crash)
- Portfolio impact bars (red/green for each scenario)
- Worst-case drawdown estimates

### 4.5 Frontend — Enhance Existing Pages

**Modify:** `frontend/app/dashboard/page.tsx`

เพิ่ม Quant Summary Strip ด้านบน — 1 row ของ compact cards:
```
[VaR: -2.3%] [Regime: Trending 82%] [Vol: High ↑] [Corr: Stable ✓] [Portfolio: Balanced]
```

User เห็น quant status ทันทีโดยไม่ต้องไปหน้า /quant

**Modify:** `frontend/app/history/page.tsx`

เพิ่มข้อมูล quant ใน trade history table:
- Column: Regime at entry (trending/ranging)
- Column: AI confidence + confirmations count (3/5)
- Expandable row: Pre-trade reasoning + post-trade accountability

**Modify:** `frontend/app/activity/page.tsx`

เพิ่ม event types ใหม่:
- `quant_alert` — correlation breakdown, VaR breach, regime shift
- `ai_learning` — AI learned new pattern, parameter adjusted
- `baseline_reset` — auto reset เมื่อ performance drop

**Modify:** `frontend/app/backtest/page.tsx`

เพิ่ม tabs:
- Stress Testing tab — run stress scenarios + view results
- Regime Backtest tab — backtest performance by regime

### 4.6 Frontend — Navigation Update

**Modify:** `frontend/components/layout/Sidebar.tsx`

เพิ่ม "Quant" ในเมนู:
```
Analytics
├─ AI Insights
├─ AI Activity
├─ ML Model
├─ Macro Data
└─ Quant        ← NEW (QuantPage)
```

### 4.7 Frontend — Shared Quant Components

**New directory:** `frontend/components/quant/`

| Component | Used In | Purpose |
|-----------|---------|---------|
| `CorrelationHeatmap.tsx` | /quant, /macro | 4×4 color matrix |
| `VaRGauge.tsx` | /quant, /dashboard | Semicircular VaR display |
| `RegimeBadge.tsx` | /quant, /dashboard, /history | Regime label + probability |
| `RegimeTimeline.tsx` | /quant, /insights | State history over time |
| `SignalConfidenceBar.tsx` | /dashboard, /insights | Stacked confirmation indicator |
| `PortfolioDonut.tsx` | /quant, /dashboard | Allocation pie chart |
| `RiskContributionBar.tsx` | /quant | Per-symbol risk contribution |
| `QuantSummaryStrip.tsx` | /dashboard | Compact quant status row |
| `TradeReasoningCard.tsx` | /history, /activity | Pre/post trade AI reasoning |
| `StressTestTable.tsx` | /quant, /backtest | Scenario results |

---

## Phase 5: AI Meta-Learner (Self-Learning Quant)

ใช้ AI เป็น meta-layer ที่เรียนรู้จาก quant model output แล้วปรับ parameter อัตโนมัติ พร้อม safety architecture ป้องกัน 3 ความเสี่ยงหลัก

### Safety Architecture

```
┌──────────────────────────────────┐
│  AI Meta-Learner (เสนอ)          │
│  "ควรปรับ X เป็น Y เพราะ..."    │
└──────────┬───────────────────────┘
           ▼
┌──────────────────────────────────┐
│  Statistical Gate (ตรวจสอบ)      │
│  min sample ✓ p-value ✓ OOS ✓   │
│  rate limit ✓ max change ✓      │
└──────────┬───────────────────────┘
           ▼
┌──────────────────────────────────┐
│  Apply + Monitor (ติดตาม)        │
│  rolling Sharpe vs baseline      │
│  ถ้าแย่กว่า 70% → auto reset    │
└──────────┬───────────────────────┘
           ▼
┌──────────────────────────────────┐
│  Baseline Anchor (safe harbor)   │
│  walk-forward optimal params     │
│  reset ได้ทุกเมื่อ               │
└──────────────────────────────────┘
```

### 5.1 AI Quant Analyzer

**New file:** `backend/app/ai/quant_analyzer.py`

ทุกวัน Claude วิเคราะห์ quant metrics ทั้งหมด:

- GARCH forecast แม่นไหม? (forecast vs realized)
- HMM regime ถูกไหม? (regime vs actual performance)
- Correlation เปลี่ยนไหม? (rolling vs assumption)
- Strategy ไหนทำได้ดี/แย่ใน regime นี้?
- สรุป: ปรับ parameter อะไร + เหตุผล → บันทึกเป็น learning

### 5.2 Statistical Significance Gate

**New file:** `backend/app/ai/param_gate.py`

ป้องกัน Overfitting — AI ปรับบ่อยเกิน fit noise:

- ต้องมี data อย่างน้อย 30 trades (min sample size)
- ต้องผ่าน permutation test (p < 0.05)
- Parameter เปลี่ยนได้ไม่เกิน ±20% ต่อวัน (rate limit)
- ถ้า OOS Sharpe แย่กว่า IS Sharpe > 50% → reject
- Cooldown period: หลังปรับต้องรอ N trades ก่อนปรับอีก

### 5.3 Pattern Validation Pipeline

**New file:** `backend/app/ai/pattern_validator.py`

ป้องกัน AI Hallucination — เห็น pattern ที่ไม่มีจริง:

- **Layer 1 — Backtest verification**: pattern นี้ทำกำไรจริงไหมใน 90 วัน?
- **Layer 2 — Statistical test**: ดีกว่า random มี p-value เท่าไหร่?
- **Layer 3 — Cross-validation**: ใช้ได้กับหลาย symbol หรือแค่ตัวเดียว?
- **Layer 4 — Confidence decay**: ถ้า pattern ไม่เกิดซ้ำใน 14 วัน → ลด weight, 30 วัน → ลบทิ้ง

### 5.4 Baseline Anchor + Auto Reset

**New file:** `backend/app/ai/baseline_manager.py`

ป้องกัน Compounding Errors — feedback loop ที่พังตัวเอง:

- บันทึก baseline params (walk-forward optimal)
- Monitor: rolling Sharpe vs baseline Sharpe ตลอดเวลา
- ถ้า rolling Sharpe < baseline × 0.7 → **auto reset กลับ baseline**
- Failed experiment → flag ใน memory → AI เรียนรู้ว่าอะไรไม่ควรทำ
- Cooldown 7 วันหลัง reset ก่อน AI ปรับได้อีก
- Monthly: recalculate baseline จาก walk-forward optimization

### 5.5 Continuous Learning Schedule

**Modify:** `backend/app/bot/scheduler.py`

| Timing | Action |
|--------|--------|
| Morning | AI อ่าน overnight data → ปรับ model priors |
| Intraday | Monitor quant signals → flag anomalies real-time |
| Evening | Review วันนี้ → สรุป lessons → update memory |
| Weekly | Deep analysis → retrain ML + recalibrate quant params |
| Monthly | Stress test ด้วย data ล่าสุด → ปรับ risk budget + recalculate baseline |

### 5.6 Learning Memory Store

**Modify:** `backend/app/memory/session_memory.py`

- Quant-specific memory type: `quant_learning`
- Structure: `{pattern, evidence, statistical_test, outcome, confidence, decay_date}`
- Auto-decay: confidence ลดทุกวันถ้าไม่มี evidence ใหม่ confirm
- Cross-session: successful learnings persist (TTL 30d), failed ones persist as warnings (TTL 90d)

### 5.7 UI — AI Learning Transparency

**New file:** `frontend/app/ai-learning/page.tsx`

User ต้องเห็นว่า AI เรียนรู้อะไร + ปรับอะไร:

- **Learning Timeline** — แสดง AI learnings ทั้งหมด + confidence + decay status
- **Parameter Change Log** — ก่อน/หลัง + เหตุผล + statistical test result
- **Baseline vs Current** — เทียบ params ปัจจุบัน vs baseline (diff view)
- **Failed Experiments** — list ของสิ่งที่ AI ลองแล้วไม่ work (เพื่อ transparency)

**Modify:** `frontend/components/layout/Sidebar.tsx`

เพิ่ม "AI Learning" ในเมนู Analytics

---

## Phase 6: Autonomous Expert AI (End-to-End)

AI จัดการทุกอย่างตั้งแต่วิเคราะห์ตลาดจนถึงเข้าเทรด มนุษย์ตั้งค่าครั้งเดียว (ทุน + max risk) แล้วดูผ่าน dashboard

### Design Principles

**เป้าหมาย**: AI ที่ตัดสินใจแบบ expert trader — ไม่ใช่เลียนแบบ intuition แต่ encode กระบวนการคิดของ expert เป็นระบบ

**หลักสำคัญ**: ไม่ใช่ทำให้ AI "ฉลาดขึ้น" แต่ทำให้ AI **"โง่ไม่ได้"**

```
มนุษย์ตั้งแค่ครั้งเดียว (Day 0)
├─ ทุนเริ่มต้น
├─ Max drawdown ที่รับได้ (เช่น 15%)
└─ Risk per trade สูงสุด (เช่น 2%)
    ↓
ค่าพวกนี้ AI ห้ามแก้ — hardcode เป็น guardrail

    ↓
AI จัดการทุกอย่างที่เหลือ
├─ Morning:   อ่านตลาด → ปรับ regime → set strategy
├─ Intraday:  generate signal → validate → execute
├─ Evening:   review trades → learn → adjust params
├─ Weekly:    retrain ML → recalibrate quant
└─ Monthly:   stress test → adjust risk budget
```

---

### 6.1 Expert Decision Framework

**New file:** `backend/app/ai/expert_framework.py`

Expert trader ตัดสินใจผ่าน checklist — AI ต้องทำเหมือนกัน:

```
Default = ไม่เทรด → ต้องพิสูจน์ว่าควรเทรด

1. ตลาดอยู่ใน condition ที่เทรดได้ไหม?    → ถ้าไม่ → นั่งเฉย
2. มี setup ที่ชัดเจนไหม?                 → ถ้าไม่ → นั่งเฉย
3. Risk/reward คุ้มไหม?                   → ถ้าไม่ → นั่งเฉย
4. มี confirmation กี่ตัว?                 → ถ้าน้อยเกิน → นั่งเฉย
5. ผ่านทุกข้อ → เข้าเทรด ด้วย size ที่เหมาะสม
```

4 ใน 5 ข้อคือ "นั่งเฉย" — expert เทรดน้อย แต่แม่น

### 6.2 Multiple Confirmation Gate

**New file:** `backend/app/ai/confirmation_gate.py`

Expert ไม่เคยเทรดจาก signal เดียว — AI ก็ต้องไม่:

```
ต้องผ่านอย่างน้อย 3 ใน 5:
├─ Quant signal    (z-score, momentum, breakout)
├─ ML prediction   (LightGBM confidence > threshold)
├─ Regime match    (HMM state เหมาะกับ strategy ที่จะใช้)
├─ Risk/reward     (TP/SL ratio > 1.5)
└─ AI reasoning    (Claude วิเคราะห์แล้วเห็นด้วย)

ถ้าได้แค่ 2 → ไม่เทรด แม้ว่าแต่ละตัวจะ confident มาก
```

### 6.3 Pre-Trade Reasoning (Anti-Hallucination)

**Modify:** `backend/app/bot/engine.py`

ก่อนเข้า trade ทุกครั้ง AI ต้องสร้าง structured reasoning:

```json
{
  "setup": "GOLD H1 breakout above 2350 with increasing volume",
  "confirmations": ["HMM trending 82%", "z-score 2.3", "ML buy 71%"],
  "risk_reward": "SL 2320 (-30), TP 2410 (+60) = 1:2",
  "counter_evidence": "FOMC ใน 4 ชม. อาจ reverse",
  "what_would_invalidate": "ถ้า price กลับต่ำกว่า 2340 ใน 15 นาที",
  "confidence": 0.72,
  "position_size_reason": "GARCH vol high → reduce to 0.8x"
}
```

กฎ:
- ถ้า AI ให้เหตุผลไม่ได้ → **ไม่เทรด**
- ถ้าเหตุผลขัดกันเอง → **ไม่เทรด**
- ถ้าไม่มี counter_evidence → **ไม่เทรด** (confirmation bias)
- ทุก reasoning ถูกบันทึกเพื่อ post-trade accountability

### 6.4 Counter-Evidence Requirement (Anti-Bias)

**Same file:** `backend/app/ai/expert_framework.py`

ป้องกัน confirmation bias — AI ต้องหาเหตุผลที่ trade จะพัง:

```
ทุกครั้งก่อนเทรด AI ต้องตอบ:
├─ "อะไรที่จะทำให้ trade นี้พัง?"
├─ "ถ้าผิด จะเสียเท่าไหร่?"
└─ "มี event/data อะไรที่ยัง confirm ไม่ได้?"

ถ้า counter-evidence แข็งกว่า evidence → ไม่เทรด
ถ้ามี upcoming event ที่อาจ invalidate → ลด lot หรือไม่เทรด
```

### 6.5 "UNCERTAIN" as Valid Decision

**Modify:** `backend/app/bot/engine.py`

ปัจจุบัน AI ถูกบังคับเลือก BUY/SELL/HOLD — ต้องเพิ่ม UNCERTAIN:

```
AI decisions:
├─ BUY        — มี evidence + confirmations เพียงพอ
├─ SELL       — มี evidence + confirmations เพียงพอ
├─ HOLD       — ไม่มี setup
└─ UNCERTAIN  — มี signal แต่ขัดแย้งกัน → นั่งเฉย

UNCERTAIN ≠ HOLD:
- HOLD = ไม่มี signal เลย
- UNCERTAIN = มี signal แต่ไม่มั่นใจ → ดีกว่าเดา
```

AI ที่บอกว่า "ไม่รู้" ได้ = AI ที่ไม่ hallucinate

### 6.6 Post-Trade Accountability Loop

**New file:** `backend/app/ai/trade_accountability.py`

Expert ที่ดีตัดสินที่ process ไม่ใช่ result:

```
ทุก trade ที่ปิด:
├─ เทียบ pre-trade reasoning vs สิ่งที่เกิดจริง
│
├─ ถ้าเหตุผลถูก + กำไร   → "skilled win"     → reinforce
├─ ถ้าเหตุผลถูก + ขาดทุน  → "correct process" → ไม่ปรับอะไร
├─ ถ้าเหตุผลผิด + กำไร   → "lucky win"       → flag ⚠️ ไม่ reinforce
├─ ถ้าเหตุผลผิด + ขาดทุน  → "real mistake"    → เรียนรู้ + ปรับ
│
└─ AI เรียนรู้จาก process ไม่ใช่จาก P&L
```

ป้องกัน: AI เรียนรู้ pattern ที่ "บังเอิญ" กำไร → overfit noise

### 6.7 Bias Elimination Layer

**New file:** `backend/app/ai/bias_guard.py`

| Bias | Detection | Prevention |
|------|-----------|------------|
| **Recency bias** | น้ำหนัก trade ล่าสุดมากเกิน | บังคับ min 30 trades ก่อนปรับ parameter |
| **Confirmation bias** | หา evidence สนับสนุนอย่างเดียว | บังคับ counter-evidence ทุก trade |
| **Overtrading** | เทรดเยอะกว่า baseline > 50% | Max trades per day limit + penalize ถ้า win rate ต่ำ |
| **Anchoring** | ยึดติดราคาเข้า | SL/TP คำนวณจาก ATR/GARCH เท่านั้น ไม่ใช่จากราคาเข้า |
| **Sunk cost** | ถือ losing trade เพราะไม่ยอมตัด | Hard SL ที่ AI แก้ไม่ได้ (non-bypassable) |
| **Gambler's fallacy** | เพิ่ม lot หลังแพ้ เพื่อ "เอาคืน" | Streak adjustment (แพ้ 2 ×0.6, แพ้ 3+ ×0.4) lock ไว้ |

### 6.8 Graduated Autonomy (Rollout)

**Modify:** `backend/app/api/routes/rollout.py`

ใช้ rollout mode ที่มีอยู่แล้ว — ไม่ปล่อย AI เต็มที่ทันที:

```
Week 1-2:  shadow mode
           AI ตัดสินใจแต่ไม่เทรดจริง
           เทียบผลกับ rule-based strategy
           ต้อง win rate ≥ baseline

Week 3-4:  paper mode
           เทรด paper ดู performance
           ต้อง Sharpe ≥ baseline × 0.8

Week 5-6:  micro mode
           lot 0.01 เท่านั้น
           ต้อง Sharpe ≥ baseline × 0.9

Week 7+:   live mode
           ค่อยๆ เพิ่ม lot ตาม performance
           ถ้า Sharpe drop < baseline × 0.7 → auto downgrade กลับ micro
```

### 6.9 Human Override (Telegram + Dashboard)

**Modify:** `backend/app/notifications/telegram.py`

มนุษย์ไม่ต้อง config แต่ยังสั่งได้ทุกเมื่อ:

```
Telegram commands:
├─ /pause          → หยุดเทรดทันที
├─ /resume         → เริ่มเทรดต่อ
├─ /status         → AI รายงานสถานะ + reasoning ล่าสุด
├─ /performance    → สรุป P&L, Sharpe, drawdown
├─ /reset          → force reset to baseline params
└─ /mode [shadow|paper|micro|live]  → เปลี่ยน rollout mode

Daily report (auto):
├─ สรุป trades วันนี้ + reasoning
├─ Quant metrics (VaR, regime, correlation)
├─ AI learnings วันนี้
└─ Alert ถ้ามี anomaly
```

### 6.10 Non-Bypassable Guardrails

**Modify:** `backend/mcp_server/guardrails.py`

AI ทำอะไรก็ได้ **ยกเว้น** ข้ามสิ่งเหล่านี้:

```
Hardcoded (AI แก้ไม่ได้เด็ดขาด):
├─ Max drawdown from peak        → หยุดเทรดทันที
├─ Max lot per trade              → cap ตาย
├─ Max daily loss                 → circuit breaker
├─ Max correlation exposure       → block conflicting trades
├─ Hard SL on every trade         → ไม่มี trade ไหนไม่มี SL
├─ Baseline reset threshold       → Sharpe drop > 30% = auto reset
└─ Rollout mode downgrade         → performance drop = auto downgrade

AI มีอิสระเต็มที่ภายในกรอบนี้
กรอบนี้ถูก hardcode ใน guardrails.py — ไม่มี API ให้แก้
```

### 6.11 UI — Autonomous AI Control Center

**New file:** `frontend/app/autonomous/page.tsx`

หน้าหลักสำหรับ monitor AI autonomous mode:

**Section 1 — AI Status**
- Current rollout mode (shadow/paper/micro/live) + progress bar toward next upgrade
- AI uptime + trades today + win rate today
- Current baseline Sharpe vs rolling Sharpe (live comparison)
- Auto-upgrade/downgrade conditions + status

**Section 2 — Live AI Reasoning**
- Real-time feed: AI กำลังคิดอะไร (WebSocket stream)
- ล่าสุด: "GOLD — HOLD (UNCERTAIN): z-score bullish but HMM ranging → conflict → นั่งเฉย"
- ก่อนหน้า: "BTCUSD — BUY: 4/5 confirmations, R:R 1:2.3, GARCH vol normal"
- Color-coded: BUY (green), SELL (red), HOLD (gray), UNCERTAIN (yellow)

**Section 3 — Decision Quality**
- Accountability matrix: skilled win / correct process / lucky win / real mistake (pie chart)
- Process accuracy % (reasoning ถูกกี่ %) vs P&L accuracy (กำไรกี่ %)
- Bias detection alerts (overtrading, recency bias, etc.)

**Section 4 — Guardrail Status**
- All guardrails with current utilization (progress bars)
  - Daily loss: 1.2% / 3.0% max (40% utilized)
  - Drawdown: 5.1% / 15.0% max (34% utilized)
  - Max lot: 0.03 / 0.10 max
- Circuit breaker history (when triggered + why)

**Section 5 — Human Override Panel**
- Pause/Resume button (large, prominent)
- Force reset to baseline button (with confirmation dialog)
- Mode selector (shadow/paper/micro/live)
- Emergency stop (kills all positions immediately)

**Modify:** `frontend/components/layout/Sidebar.tsx`

เพิ่ม "AI Control" ในเมนู:
```
System
├─ Agent Prompts
├─ Integration
├─ Notifications
├─ AI Control    ← NEW (Autonomous page)
└─ Settings
```

**Modify:** `frontend/app/dashboard/page.tsx`

เพิ่ม **AI Mode Banner** ด้านบนสุด:
```
🤖 AI Autonomous Mode: MICRO | Sharpe: 1.42 (baseline: 1.38) | Next upgrade in 5 days
```

Clickable → ไปหน้า /autonomous

### 6.12 UI — Trade Reasoning in History

**Modify:** `frontend/app/history/page.tsx`

ทุก trade ที่ AI ตัดสินใจจะแสดง reasoning:

- Expandable row → แสดง pre-trade reasoning card
- Post-trade accountability (skilled/lucky/correct process/mistake)
- Confirmation count badge (3/5, 4/5, etc.)
- Counter-evidence ที่ AI คิดไว้ก่อนเข้า trade

**New component:** `frontend/components/quant/AccountabilityBadge.tsx`
- "Skilled Win" (green), "Correct Process" (blue), "Lucky" (yellow ⚠️), "Mistake" (red)

---

## Quick Wins (ทำได้เลย ไม่ต้องรอ Phase ไหน)

### QW-1: News Fetching Optimization — ลดเปลือง API

**ปัจจุบัน:** Sentiment job รันทุก 15 นาที (96 ครั้ง/วัน weekday, 24 ครั้ง/วัน weekend)
ดึงข่าว + เรียก Claude Haiku วิเคราะห์ทุกรอบ ไม่สนว่าตลาดเปิดหรือปิด

**เปลี่ยนเป็น:** ดึงข่าวเฉพาะตอนที่มีความหมาย

**Modify:** `backend/app/bot/scheduler.py` — `_sentiment_job()`

```
เงื่อนไข: ดึงข่าวเมื่อ
├─ Bot ของ symbol นั้น state = RUNNING
├─ ตลาด MT5 เปิดอยู่ (ไม่ใช่ช่วง market closed)
├─ Timeframe ตรง — ดึงตอน candle close ของ symbol นั้น
│   เช่น GOLD M15 → ดึงข่าวทุก 15 นาที
│   เช่น BTCUSD H1 → ดึงข่าวทุก 1 ชั่วโมง
└─ Bot start → ดึงข่าวทันที 1 ครั้ง (fresh context)

ไม่ดึงเมื่อ:
├─ ตลาดปิด (weekend, market holiday)
├─ Bot state ≠ RUNNING
└─ นอก trading hours ของ symbol นั้น
```

**Modify:** `backend/app/bot/engine.py`

- เรียก `fetch_and_analyze_sentiment()` ตอน `process_candle()` แทนที่จะแยก job
- Sentiment จะ sync กับ candle timing ของแต่ละ symbol

**ผลลัพธ์:** ~96 calls/day → ~40-50 calls/day (ลด ~50%+ ไม่มีผลต่อ signal quality)

### QW-2: Telegram Notification Cleanup — ส่งเฉพาะที่สำคัญ

**ปัจจุบัน:** ส่ง 14 ประเภท notification รวมทั้ง sentiment ทุก 15 นาที

**เปลี่ยนเป็น:** ส่งเฉพาะ critical events

**Modify:** `backend/app/notifications/telegram.py`
**Modify:** `backend/app/bot/engine.py` — ลบ/skip การเรียก send ที่ไม่จำเป็น

```
ส่ง Telegram:
├─ ✅ Trade opened (ซื้อ/ขาย) — ต้องรู้ทันที
├─ ✅ Trade closed (ปิดไม้) — ต้องรู้ผล
├─ ✅ Bot stopped / error — ต้องรู้ว่าหยุดทำงาน
├─ ✅ Circuit breaker triggered — ต้องรู้ว่าเกิดอะไร
├─ ✅ Daily summary (22:00 UTC) — สรุปวัน
└─ ✅ Losing streak alert — ต้องรู้

ไม่ส่ง Telegram:
├─ ❌ Sentiment analysis (ดูใน dashboard แทน)
├─ ❌ Optimization report (ดูใน /insights แทน)
├─ ❌ Regime change (ดูใน dashboard แทน)
├─ ❌ Health recovered (ดูใน /notifications แทน)
└─ ❌ Generic bot start (ส่งแค่ตอน manual start)
```

**ผลลัพธ์:** ~100+ messages/day → ~10-20 messages/day (เฉพาะที่ต้อง action)

### QW-3: Market Hours Detection

**Modify:** `backend/app/bot/scheduler.py`

เพิ่ม market hours check ก่อนรัน sentiment job:

```python
# MT5 market hours (approximate)
MARKET_CLOSED_HOURS = {
    "GOLD": {"weekend": True, "daily_close": (22, 23)},     # Closes 22:00-23:00 UTC
    "OILCash": {"weekend": True, "daily_close": (22, 23)},
    "BTCUSD": {"weekend": False, "daily_close": None},       # 24/7
    "USDJPY": {"weekend": True, "daily_close": (22, 22)},
}

def is_market_open(symbol: str) -> bool:
    ...
```

---

## Dependencies ที่ต้องเพิ่ม

```
arch>=7.0          # GARCH models
hmmlearn>=0.3      # Hidden Markov Models
filterpy>=1.4      # Kalman filter
scipy>=1.11        # optimization (already have)
cvxpy>=1.4         # convex optimization (portfolio)
```

## Files Summary

### New Files (32):

| # | File | Purpose |
|---|------|---------|
| 1 | `backend/app/risk/var.py` | VaR/CVaR calculator |
| 2 | `backend/app/risk/garch.py` | GARCH vol forecast |
| 3 | `backend/app/risk/portfolio_risk.py` | Portfolio-level risk |
| 4 | `backend/app/risk/portfolio_optimizer.py` | Markowitz + CVaR optimization |
| 5 | `backend/app/strategy/quant_signals.py` | Statistical alpha signals |
| 6 | `backend/app/strategy/kalman.py` | Kalman filter |
| 7 | `backend/app/ml/calibration.py` | ML probability calibration |
| 8 | `backend/app/backtest/stress_test.py` | Stress testing |
| 9 | `backend/app/api/routes/quant.py` | Quant API endpoints |
| 10 | `frontend/app/quant/page.tsx` | Quant dashboard |
| 11 | `backend/app/ai/quant_analyzer.py` | AI quant daily analysis |
| 12 | `backend/app/ai/param_gate.py` | Statistical significance gate |
| 13 | `backend/app/ai/pattern_validator.py` | Pattern validation pipeline |
| 14 | `backend/app/ai/baseline_manager.py` | Baseline anchor + auto reset |
| 15 | `backend/app/ai/expert_framework.py` | Expert decision checklist + counter-evidence |
| 16 | `backend/app/ai/confirmation_gate.py` | Multiple confirmation gate (3/5 required) |
| 17 | `backend/app/ai/trade_accountability.py` | Post-trade reasoning evaluation |
| 18 | `backend/app/ai/bias_guard.py` | Bias detection + prevention |
| 19 | `backend/alembic/versions/..._add_quant_tables.py` | Quant DB tables + enum |
| 20 | `frontend/app/quant/page.tsx` | Quant analytics dashboard |
| 21 | `frontend/app/ai-learning/page.tsx` | AI learning transparency |
| 22 | `frontend/app/autonomous/page.tsx` | AI autonomous control center |
| 23 | `frontend/components/quant/CorrelationHeatmap.tsx` | 4×4 correlation matrix |
| 24 | `frontend/components/quant/VaRGauge.tsx` | VaR/CVaR gauge |
| 25 | `frontend/components/quant/RegimeBadge.tsx` | Regime state + probability |
| 26 | `frontend/components/quant/RegimeTimeline.tsx` | Regime history chart |
| 27 | `frontend/components/quant/SignalConfidenceBar.tsx` | Confirmation count bar |
| 28 | `frontend/components/quant/PortfolioDonut.tsx` | Allocation pie chart |
| 29 | `frontend/components/quant/RiskContributionBar.tsx` | Per-symbol risk % |
| 30 | `frontend/components/quant/QuantSummaryStrip.tsx` | Dashboard compact strip |
| 31 | `frontend/components/quant/TradeReasoningCard.tsx` | Pre/post trade reasoning |
| 32 | `frontend/components/quant/StressTestTable.tsx` | Stress scenario results |
| 33 | `frontend/components/quant/AccountabilityBadge.tsx` | Trade quality badge |

### Modify Files (19):

| # | File | Change |
|---|------|--------|
| 1 | `backend/app/risk/correlation.py` | Rolling correlation |
| 2 | `backend/app/risk/manager.py` | Integrate VaR, GARCH, portfolio optimizer |
| 3 | `backend/app/strategy/regime.py` | Add HMM regime switching |
| 4 | `backend/app/strategy/ensemble.py` | Regime-adaptive weights + quant signals |
| 5 | `backend/app/strategy/risk_parity.py` | True risk parity |
| 6 | `backend/app/strategy/pair_spread.py` | Kalman hedge ratio |
| 7 | `backend/requirements.txt` | Add dependencies |
| 8 | `backend/app/bot/scheduler.py` | Add continuous learning schedule |
| 9 | `backend/app/memory/session_memory.py` | Add quant learning memory type |
| 10 | `backend/app/bot/engine.py` | Pre-trade reasoning + UNCERTAIN decision + confirmation gate |
| 11 | `backend/app/api/routes/rollout.py` | Graduated autonomy (auto upgrade/downgrade) |
| 12 | `backend/app/notifications/telegram.py` | Human override commands + daily report |
| 13 | `backend/mcp_server/guardrails.py` | Non-bypassable guardrails for autonomous mode |
| 14 | `frontend/app/dashboard/page.tsx` | Quant summary strip + VaR + regime badge + portfolio donut + AI mode banner |
| 15 | `frontend/app/history/page.tsx` | Trade reasoning + accountability + regime column |
| 16 | `frontend/app/insights/page.tsx` | Quant signals panel + regime history |
| 17 | `frontend/app/activity/page.tsx` | New event types (quant_alert, ai_learning, baseline_reset) |
| 18 | `frontend/app/macro/page.tsx` | Rolling correlation heatmap + trend chart |
| 19 | `frontend/app/backtest/page.tsx` | Stress testing tab + regime backtest tab |
| 20 | `frontend/components/layout/Sidebar.tsx` | Add Quant, AI Learning, AI Control menu items |

### Quick Win Modify Files (3):

| # | File | Change |
|---|------|--------|
| QW-1 | `backend/app/bot/scheduler.py` | Sentiment job → sync with candle timing + market hours check |
| QW-2 | `backend/app/notifications/telegram.py` | Filter: send only trade open/close, stop, circuit breaker, daily summary |
| QW-3 | `backend/app/bot/engine.py` | Call sentiment in process_candle() + skip telegram for sentiment/regime |

## Execution Order

**Quick Wins** (ทำได้ทันที) → Phase 0 → 1 → 2 → 3 → 4 → 5 → 6

- **Phase 0**: Foundation refactor — ทำก่อนเพื่อไม่ให้ phase ถัดไปพังระบบเดิม
- **Phase 1-4**: สร้าง quant tools + UI — แต่ละ phase ใช้งานได้ทันที พร้อม UI แสดงผล
- **Phase 5**: สอน AI ใช้ quant tools + safety architecture + AI learning page
- **Phase 6**: ปล่อย AI ทำเอง + AI control center (ต้องรอ Phase 0-5 เสร็จก่อน)
- **Phase 6 rollout**: shadow (2w) → paper (2w) → micro (2w) → live

**UI principle**: ทุก Phase ต้องมี UI ที่สื่อสารกับ user — ไม่มี backend feature ไหนที่ไม่มี UI แสดงผล
