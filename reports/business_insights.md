# Business insights

These findings use simulated bookings from 2025. Each proposed action would need validation with operating data.

## 1. Is annual supply credible?

255,488 shift hours support 60,000 requests. Service utilization is 18.66%; occupied utilization is 25.59%. Hebbal has 11.3% service and 15.4% occupied utilization.

Completed or occupied minutes / available shift minutes. Equal zone staffing and long full-day coverage create substantial modeled slack; these are not empirically calibrated supply levels.

108 workers; 81% attendance; equal 18 workers per zone; eight-hour shifts; fixed travel and turnaround. Collect attendance, paid-time, travel and breaks by zone/hour. Do not use this baseline as a hiring plan. Compare coverage changes through dispatch replay first.

## 2. Why are requests unfulfilled despite spare hours?

1,733 of 1,959 no-capacity failures cannot fit on an empty scheduled shift; 226 can fit on an empty schedule but encounter reservations. 1,733 boundary failures arrive at or after 19:00. Of 54,072 accepted requests, 51,356 assign at the two-minute minimum; 2,716 wait on reservations (mean 18.26 minutes).

Boundary and contention diagnostics partition dispatch failures, not all cancellations. Delay means use accepted requests. Whole-service fit before closing dominates these modeled dispatch failures; reservation contention drives delays above the minimum. Empty-schedule feasibility retains worker productivity and the 45-minute assignment limit.

Greedy non-preemptive dispatch and no cross-zone workers or advance bookings. Investigate closing-time coverage and last-booking policies before broad headcount expansion. Boundary diagnostics do not prove a unique real-world cause.

## 3. What does a schedule replay show?

Later closing completes 53,774 requests (89.62%) at 255,488 hours, versus 52,198 (87.00%) baseline. Lean split completes 33,943 (56.57%) at 142,328 hours.

Full dispatch reruns on paired requests; see staffing_scenarios.csv. Moving late coverage can improve simulated fit without adding hours; removing midday coverage sacrifices fulfillment despite higher service utilization.

Later close shifts 13–21 to 14–22. Lean split retains 10 workers per zone on attended days for 07–11 and 17–21. Same latent requests and worker productivity; fixed paired cancellation propensity. Validate worker willingness, transport and demand near closing before a small late-shift trial. Reject an efficiency target based on utilization alone. These deterministic results are not forecasts, optimized plans or causal treatment effects.

## 4. Where and when should operations investigate?

Indiranagar fulfills 86.4% of 13,016 requests versus HSR Layout at 87.5%. The 08:00 hour has 7,402 requests; 20:00 has 1,677.

Completed/requested by zone; request counts by creation hour. The zone gap is descriptive and relatively small. Hourly interval accounting distinguishes incoming workload from actual occupied reservations; summed daily workload hides coverage windows.

Demand peaks, weekend weights and unequal zone demand are specified inputs. Use the zone-hour table to inspect arrival mix, remaining shift length and contention together. Set service-level guardrails before changing schedules.

## 5. Which cancellations merit separate actions?

3,969 customer-plan cancellations, 1,874 accepted cancellations and 1,959 dispatch failures total 7,802.

Reason count / all cancelled requests, with exclusive final reasons. Customer attrition and dispatch feasibility require different interventions; they must not all be described as staffing shortages.

6.5% pre-dispatch and 3.5% conditional post-assignment cancellation probabilities are modeled. Validate reason coding in actual logs. Test reminders or clearer timing only after observed cancellation evidence; monitor accepted-cancellation payouts separately.

## 6. What do repeats and service mix establish?

78.2% of 10,479 active customers request more than once. Cleaning earns INR 10,260,966, or 59.6% of revenue.

Repeat requesters / active requesters; completed cleaning revenue / all revenue. These describe request concentration and price/mix, not customer retention or skill shortages. Cancelled requests count toward repeats.

Pareto customer propensities, service mix, prices and interchangeable worker skills are specified. Separate repeat completed-customer cohorts from repeat request cohorts before retention decisions. Review contribution and duration alongside revenue before prioritizing services.

## 7. Does positive contribution establish profitability?

INR 17,211,937.00 revenue less INR 7,153,435.12 attributable costs yields INR 10,058,501.88 contribution (58.4%).

Completed charges less per-service payouts, materials and processing, including accepted cancellation compensation. Contribution excludes the cost of maintaining idle shift capacity. Low occupied utilization makes the missing wage model especially material.

Per-service minute payouts; no guaranteed hourly pay, acquisition costs, refunds, taxes or overhead. Add contractual wage obligations and fixed operating costs before judging profitability or estimating staffing savings. No scenario financial uplift is presented as a business impact claim.
