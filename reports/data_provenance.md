# Dataset provenance and assumptions

All project records, financials and conclusions are SIMULATED. Independent portfolio work; no affiliation with or access to Snabbit internal information.

## Public dataset research

Researched 5 November 2026 using queries for public home-service bookings, worker assignments and dataset licenses. No suitable verified end-to-end service dataset was identified in this bounded search; this is not a claim that none exists.

The UCI Online Retail dataset has verifiable institutional provenance and a CC BY 4.0 license: https://archive.ics.uci.edu/dataset/352/online+retail . Its invoices describe product retail, not service assignments or worker shifts, so it cannot support the requested utilization and scheduling validation. Online Retail II is also product retail: https://archive.ics.uci.edu/dataset/502/online+retail+ii . Neither dataset is incorporated. Unverified third-party booking datasets were not used.

## Simulation contract

- NumPy seed 42; 60,000 immediate requests created over every day of calendar 2025. Local timestamps are naive Asia/Kolkata (UTC+05:30, no DST). No personal data is generated.
- Six illustrative Bengaluru zones, 12,000 eligible customers, 108 workers. Workers remain in their home zone and can perform all three service categories. Customer demand weights follow a Pareto distribution, producing repeat behavior. Customer zone weights are 20%, 20%, 19%, 17%, 14%, 10%.
- Request hours 07:00–20:59; normalized weights [7,13,13,8,5,4,4,5,7,10,12,10,6,3]. Weekends multiply demand by 1.18; day weights increase linearly by roughly 25% over the year. These are assumptions, not observed market estimates.
- Each worker independently works with probability 0.81 per day. Fixed 07:00–15:00 or 13:00–21:00 shifts alternate across worker IDs. Eight hours includes travel and breaks; no separate break schedule is simulated.
- Cleaning / dishwashing / laundry expected durations are 70 / 35 / 55 minutes; request mix 48% / 30% / 22%; duration is normal with SD 10, clipped to 20–110 minutes, adjusted by worker productivity sampled uniformly from 0.85–1.18.
- Assignment reserves a worker starting no earlier than request+2 minutes, shift opening, or prior release+10-minute buffer. Start is assignment+10 minutes. Complete within shift and assign within 45 minutes, otherwise cancel for no capacity. Greedy earliest feasible assignment; no optimization or cross-zone dispatch.
- 6.5% cancel before dispatch; 3.5% of feasible assignments cancel three minutes after acceptance. These cancellation types are mutually exclusive. Post-assignment cancellations reserve the worker through cancellation plus 10 minutes. All final statuses resolve; no open backlog at cutoff. Simulation may resolve final-day requests within that day's shifts.
- Base service prices INR 399 / 199 / 299. INR 29 surcharge for requests in hours 8,9,17,18. Revenue only on completion. Payout INR 2.10 per service minute; INR 15 for accepted cancellation. Materials 4.5% and payment processing 2% of realized revenue, rounded per booking. No taxes, discounts, tips, refunds, fixed overhead, guaranteed shift wages or acquisition costs.
- Contribution includes attributable cancellation payouts. It is not profit. Capacity gaps compare expected requested service minutes to shared shift minutes and are only a coarse workload indicator; they omit travel and cannot establish scheduling feasibility.

## Cleaning and reporting

Typed IDs and explicit schema enforce keys. Canonical status values require no text imputation. Timestamps are parsed to pandas datetime; null assignment and completion timestamps are preserved because they encode cancellation stages. Missing durations are excluded from averages; no imputed zero delay. Request filters use inclusive local calendar dates. All revenue displayed in the dashboard belongs to the selected creation cohort; for a completion-date ledger use completed_at instead. Selected partial months are not annualized. Full-year insights avoid partial-period comparisons.

Every booking carries is_simulated=1. All other tables and exports belong to the same simulated dataset. Run pytest to verify structural, temporal, capacity and financial invariants.

## External review additions

Baseline database and original normalized CSVs are preserved. `request_inputs.csv` captures latent per-request duration and paired pre/post cancellation flags without consuming additional draws in the original RNG sequence. Reconstructing those inputs asserted exact original status and timestamp agreement. Replaying the baseline asserted worker assignment and financial agreement as well.

Hourly capacity uses half-open interval intersections. Service time is only completed work. Occupied time is assignment through terminal event plus ten minutes, clipped to shift end; it includes travel and accepted cancellation reservations, but not wait before assignment. Workload assigns each request's expected duration to arrival hour, not an occupancy interval. Shared capacity stays unchanged under category filters. Undefined zero-capacity rates remain blank.

Dispatch failures are classified by feasibility with all same-day scheduled workers empty. If no complete service fits within the original assignment/shift constraints, the diagnostic is shift window/duration. Otherwise reservations bind. This is a defined counterfactual partition, not unique causal attribution or globally optimal scheduling.

Hypothetical schedules: later_close retains every attended worker/8-hour shift but moves 13–21 shifts to 14–22. lean_split retains within-zone worker IDs 1–10 on original attended days, with 07–11 and 17–21 split shifts. Both dispatch all original requests again; no rescaling of demand/capacity is used as an outcome estimate. Every assigned request retains its baseline cancellation flag; previously unassigned requests get a potential post-assignment cancellation flag from a separate keyed NumPy seed (42 + booking_id + 100000). Worker acceptance of split/later schedules is unvalidated. Wage savings cannot be inferred from this per-service payout model.
