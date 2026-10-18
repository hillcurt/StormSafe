# Problem spec — Phase 1 artifact

**Status:** approved (Gate 1: merging this PR is the sign-off)
**Owner:** @hillcurt

## Decision this system supports
Pool staff decide whether to **clear the water** (closure) or **warn swimmers** (advisory) because lightning may come within striking distance. StormSafe gives them a probability ahead of time, so the call isn't made only once thunder is audible.

**Two alert tiers:**
- **Advisory:** risk is elevated; warn swimmers and get ready to clear.
- **Closure:** clear the water now.

Each tier gets its own probability threshold, chosen in Phase 4 from holdout results. The closure tier is held to the recall target (ADR 0005).

## Site and operating rule
- **Site:** one outdoor pool facility. Its location and time zone are private site config (ADR 0004). The site must be within GOES-19 Geostationary Lightning Mapper coverage (the Americas).
- **Closure rule:** the pool closes for **30 minutes** after a lightning strike within **10 miles**.

## Prediction target (label definition)
For a forecast issued at time *t*: will at least one lightning strike occur within **10 miles** of the site in the **next 60 minutes**, (*t*, *t* + 60 min]?

In plain terms: *will the pool have to close in the next hour?*

- **Ground truth:** NOAA GOES-19 GLM flashes. Source details are verified in the Phase 2 data contract.
- The 30-minute closure is an operating rule the system reports on (for example, "closed until 3:42 PM"), not part of what the model predicts.
- Changing the radius, the horizon, the closure duration, or operating hours requires a new ADR.

## Forecasts and operating hours
- **Operating hours:** 10 AM – 6 PM in the site's local time. Training and evaluation use forecast times inside these hours.
- **Scheduled hourly:** a forecast on the hour from 10 AM through 5 PM (8 per day). Each covers the next 60 minutes, so together they cover operating hours with no gaps. They also form the steady prediction log that Phase 5 shadow evaluation needs.
- **On demand:** a fresh forecast can be requested at any time during operating hours, for example when the sky looks bad between scheduled forecasts.

## Cost of errors
| Error | Consequence | Weight |
| --- | --- | --- |
| Miss (false negative) | Swimmers in the water when lightning arrives | Severe: safety |
| False alarm (false positive) | Unneeded closure; lost swim time; staff stop trusting alerts | Moderate: cost and trust |

The system is **recall-first**: it accepts more false alarms to avoid misses (ADR 0005).

## Success criteria
- **Recall ≥ 0.9** for the closure tier on a time-based holdout (ADR 0005)
- Beats two baselines on the same holdout: a CAPE-threshold rule and persistence
- Calibrated probabilities (reliability checked), so "40%" means roughly 40%
- Precision tracked and reported, with a floor set after baselines are measured

## Out of scope (for now)
- Real-time alerting to staff devices (shadow mode only until Gate 5)
- More than one site
- Severe weather other than lightning (wind, hail)
