# What the data says

Four analyses run on the modeled data in BigQuery. Each is reproducible with
`python -m analysis.run_all`, which refreshes the JSON in `analysis/outputs/`.
Numbers below are from the July 2026 data (2015 through May 2026).

## 1. What drives on-time performance

I fit a standardized linear regression of weekday on-time performance on the three
operational factors available at the line-month level: ridership, wait assessment
(how evenly spaced the trains are), and fleet reliability (mean distance between
failures). Standardizing the inputs makes the coefficients comparable as driver
strengths.

Across 2,464 line-months the model explains **47% of the variance in on-time
performance** (R² = 0.47, and a 5-fold cross-validated R² of 0.47, so it is not
overfit). The drivers, strongest first:

| Factor | Standardized β | Correlation with OTP | Reading |
|---|---|---|---|
| Wait assessment | +6.70 | +0.54 | Evenly spaced trains are the biggest lever |
| Ridership | −5.56 | −0.51 | More riders, worse performance |
| Fleet reliability (MDBF) | +3.24 | +0.16 | Helps, but a weaker signal |

The ridership result is the interesting one. Even after controlling for headway
regularity and fleet reliability, higher ridership independently predicts worse
on-time performance. Crowding is not just correlated with delays, it is one of the
strongest single predictors of them. At the system level the raw correlation
between monthly ridership and on-time performance is **−0.74**.

## 2. Can you forecast on-time performance?

Monthly on-time performance per line is a short series with a large structural break
in 2020, so this is a genuinely hard forecasting problem. To keep the regime
consistent I used only the post-recovery period (July 2021 onward) and backtested a
Holt-Winters model against a seasonal-naive baseline (this month, last year) with a
rolling origin over the most recent nine months.

Holt-Winters beats the naive baseline: **mean absolute error 2.9 points versus 4.1**,
and it wins on 18 of 23 lines. That is a real improvement, but the honest framing is
that predicting monthly on-time performance to within about three points is the
ceiling here. There is not enough clean history to justify anything heavier, and I
would not trust a horizon much beyond a few months.

## 3. Anomaly detection: statistics that match the headlines

I scored every line-month with a robust z-score (median and median-absolute-deviation,
which the outliers themselves do not distort) and required both a large z and a
material deviation from the line's own norm, so that ultra-stable shuttle lines do not
flag on a trivial dip.

The worst flagged months are exactly the ones you would expect if you followed NYC
transit news:

- The **5 line collapsed to 24–31% on-time through most of 2017** (z as low as −6.7).
  This is the "Summer of Hell" period of track fires and emergency repairs.
- The **7 line fell to 55% in spring 2018** during its signal-modernization shutdowns.
- The **4 line hit 27% in late 2017**, part of the same system-wide breakdown.

The method also flags the COVID months in the other direction, where near-empty trains
ran unusually close to schedule.

## 4. Ridership recovery is uneven, and it maps to geography

Comparing each station's trailing-12-month ridership to its 2019 baseline, the system
sits at **77.6% of pre-pandemic ridership**. That average hides a clear borough gradient:

| Borough | Recovery vs 2019 |
|---|---|
| Queens | 81.4% |
| Brooklyn | 79.8% |
| Manhattan | 77.6% |
| Bronx | 65.4% |

The Bronx is roughly sixteen points behind Queens. Of 424 station complexes with a
2019 baseline, 145 are still "depressed" (below 70% recovered) and only 25 are fully
back. The stations that recovered strongest cluster in gentrifying areas (Bedford Ave
on the L in Williamsburg is above its 2019 level); the weakest are concentrated in the
Bronx and at event or seasonal venues. A handful of extreme outliers exist where a
station reopened or its complex changed between 2019 and now, which inflates their
ratio.

## Caveats

- The driver regression is associational, not causal. Crowding and delays share
  confounders, and the model is intentionally simple and interpretable rather than
  predictive.
- Ridership at the line level uses passenger counts from the customer-journey feed;
  station-level ridership is a separate dataset joined by complex.
- Mean distance between failures is reported per car class, not per line, so it enters
  the model as a division-level (A/B) fleet signal.
