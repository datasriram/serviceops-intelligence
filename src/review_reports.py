"""Calculated review findings; no invented effects or externally calibrated claims."""
import json
import pandas as pd
from src.analytics import ROOT,kpis,location_performance

def write_review(b, _shifts=None):
    out=ROOT/'reports';h=pd.read_csv(out/'hourly_capacity.csv',parse_dates=['period'])
    diag=pd.read_csv(out/'dispatch_diagnostics.csv');d=b.merge(diag,on='booking_id',validate='one_to_one')
    scenarios=pd.read_csv(out/'staffing_scenarios.csv');base=scenarios.iloc[0]
    zone=h.groupby('location')[['available_minutes','service_minutes','occupied_minutes','request_workload_minutes']].sum().reset_index()
    zone['service_utilization']=zone.service_minutes/zone.available_minutes;zone['occupied_utilization']=zone.occupied_minutes/zone.available_minutes
    zone.to_csv(out/'zone_capacity.csv',index=False)
    h['hour']=h.period.dt.hour
    profile=h.groupby(['location','hour'])[['available_minutes','service_minutes','occupied_minutes','request_workload_minutes','requested']].sum().reset_index()
    profile['service_utilization']=profile.service_minutes.div(profile.available_minutes.replace(0,float('nan')))
    profile['occupied_utilization']=profile.occupied_minutes.div(profile.available_minutes.replace(0,float('nan')))
    profile.to_csv(out/'hourly_zone_profile.csv',index=False)
    failure=d.groupby(['failure_diagnostic','hour']).size().reset_index(name='requests');failure.to_csv(out/'failure_diagnostics.csv',index=False)
    delays=d[d.assigned_at.notna()].groupby('delay_diagnostic').agg(accepted=('booking_id','size'),mean_delay=('assignment_minutes','mean')).reset_index()
    delays.to_csv(out/'delay_diagnostics.csv',index=False)
    delay_lookup=delays.set_index('delay_diagnostic')
    minimum=delay_lookup.loc['Minimum dispatch latency']; waiting=delay_lookup.loc['Reservation contention']
    after=d[d.failure_diagnostic.eq('Shift window / duration')].hour.ge(19).sum()
    contention=d.failure_diagnostic.eq('Reservation contention').sum();boundary=d.failure_diagnostic.eq('Shift window / duration').sum()
    k=kpis(b);z=location_performance(b);weak=z.loc[z.fulfillment.idxmin()];best=z.loc[z.fulfillment.idxmax()]
    peak=b.groupby('hour').size();reasons=b[b.status.eq('cancelled')].cancellation_reason.value_counts();rep=b.groupby('customer_id').size()
    later=scenarios.set_index('scenario').loc['later_close'];lean=scenarios.set_index('scenario').loc['lean_split']
    under=zone.loc[zone.service_utilization.idxmin()]
    text='# Business insights\n\nThese findings use simulated bookings from 2025. Each proposed action would need validation with operating data.\n'
    findings=[
      ('Is annual supply credible?',f'{base.shift_hours:,.0f} shift hours support {len(b):,} requests. Service utilization is {base.service_utilization:.2%}; occupied utilization is {base.occupied_utilization:.2%}. {under.location} has {under.service_utilization:.1%} service and {under.occupied_utilization:.1%} occupied utilization.', 'Completed or occupied minutes / available shift minutes.', 'Equal zone staffing and long full-day coverage create substantial modeled slack; these are not empirically calibrated supply levels.', '108 workers; 81% attendance; equal 18 workers per zone; eight-hour shifts; fixed travel and turnaround.', 'Collect attendance, paid-time, travel and breaks by zone/hour. Do not use this baseline as a hiring plan. Compare coverage changes through dispatch replay first.'),
      ('Why are requests unfulfilled despite spare hours?',f'{boundary:,} of {boundary+contention:,} no-capacity failures cannot fit on an empty scheduled shift; {contention:,} can fit on an empty schedule but encounter reservations. {after:,} boundary failures arrive at or after 19:00. Of {d.assigned_at.notna().sum():,} accepted requests, {minimum.accepted:,.0f} assign at the two-minute minimum; {waiting.accepted:,.0f} wait on reservations (mean {waiting.mean_delay:.2f} minutes).', 'Boundary and contention diagnostics partition dispatch failures, not all cancellations. Delay means use accepted requests.', 'Whole-service fit before closing dominates these modeled dispatch failures; reservation contention drives delays above the minimum. Empty-schedule feasibility retains worker productivity and the 45-minute assignment limit.', 'Greedy non-preemptive dispatch and no cross-zone workers or advance bookings.', 'Investigate closing-time coverage and last-booking policies before broad headcount expansion. Boundary diagnostics do not prove a unique real-world cause.'),
      ('What does a schedule replay show?',f'Later closing completes {later.completed:,.0f} requests ({later.fulfillment:.2%}) at {later.shift_hours:,.0f} hours, versus {base.completed:,.0f} ({base.fulfillment:.2%}) baseline. Lean split completes {lean.completed:,.0f} ({lean.fulfillment:.2%}) at {lean.shift_hours:,.0f} hours.', 'Full dispatch reruns on paired requests; see staffing_scenarios.csv.', 'Moving late coverage can improve simulated fit without adding hours; removing midday coverage sacrifices fulfillment despite higher service utilization.', 'Later close shifts 13–21 to 14–22. Lean split retains 10 workers per zone on attended days for 07–11 and 17–21. Same latent requests and worker productivity; fixed paired cancellation propensity.', 'Validate worker willingness, transport and demand near closing before a small late-shift trial. Reject an efficiency target based on utilization alone. These deterministic results are not forecasts, optimized plans or causal treatment effects.'),
      ('Where and when should operations investigate?',f'{weak.location} fulfills {weak.fulfillment:.1%} of {weak.requested:,.0f} requests versus {best.location} at {best.fulfillment:.1%}. The {peak.idxmax():02d}:00 hour has {peak.max():,} requests; {peak.idxmin():02d}:00 has {peak.min():,}.', 'Completed/requested by zone; request counts by creation hour.', 'The zone gap is descriptive and relatively small. Hourly interval accounting distinguishes incoming workload from actual occupied reservations; summed daily workload hides coverage windows.', 'Demand peaks, weekend weights and unequal zone demand are specified inputs.', 'Use the zone-hour table to inspect arrival mix, remaining shift length and contention together. Set service-level guardrails before changing schedules.'),
      ('Which cancellations merit separate actions?',f'{reasons.get("Customer changed plans",0):,} customer-plan cancellations, {reasons.get("Customer cancelled after assignment",0):,} accepted cancellations and {reasons.get("No capacity within 45 minutes",0):,} dispatch failures total {k["cancelled"]:,}.', 'Reason count / all cancelled requests, with exclusive final reasons.', 'Customer attrition and dispatch feasibility require different interventions; they must not all be described as staffing shortages.', '6.5% pre-dispatch and 3.5% conditional post-assignment cancellation probabilities are modeled.', 'Validate reason coding in actual logs. Test reminders or clearer timing only after observed cancellation evidence; monitor accepted-cancellation payouts separately.'),
      ('What do repeats and service mix establish?',f'{(rep>1).mean():.1%} of {len(rep):,} active customers request more than once. Cleaning earns INR {b.loc[b.service.eq("Cleaning"),"revenue"].sum():,.0f}, or {b.loc[b.service.eq("Cleaning"),"revenue"].sum()/k["revenue"]:.1%} of revenue.', 'Repeat requesters / active requesters; completed cleaning revenue / all revenue.', 'These describe request concentration and price/mix, not customer retention or skill shortages. Cancelled requests count toward repeats.', 'Pareto customer propensities, service mix, prices and interchangeable worker skills are specified.', 'Separate repeat completed-customer cohorts from repeat request cohorts before retention decisions. Review contribution and duration alongside revenue before prioritizing services.'),
      ('Does positive contribution establish profitability?',f'INR {k["revenue"]:,.2f} revenue less INR {k["revenue"]-k["contribution_margin"]:,.2f} attributable costs yields INR {k["contribution_margin"]:,.2f} contribution ({k["contribution_margin"]/k["revenue"]:.1%}).', 'Completed charges less per-service payouts, materials and processing, including accepted cancellation compensation.', 'Contribution excludes the cost of maintaining idle shift capacity. Low occupied utilization makes the missing wage model especially material.', 'Per-service minute payouts; no guaranteed hourly pay, acquisition costs, refunds, taxes or overhead.', 'Add contractual wage obligations and fixed operating costs before judging profitability or estimating staffing savings. No scenario financial uplift is presented as a business impact claim.')]
    for i,(question,fact,kpi,interpretation,assumption,action) in enumerate(findings,1):
        text+=f'\n## {i}. {question}\n\n{fact}\n\n{kpi} {interpretation}\n\n{assumption} {action}\n'
    (out/'business_insights.md').write_text(text,encoding='utf-8')
    payload=json.loads((out/'workbook_data.json').read_text())
    workforce=pd.DataFrame(payload['Workforce']['rows'],columns=payload['Workforce']['columns'])
    workforce=workforce.drop(columns=[c for c in workforce if c.startswith('occupied_')])
    workforce=workforce.merge(zone[['location','occupied_minutes','occupied_utilization']],on='location',validate='one_to_one')
    for name,df in [('Workforce',workforce),('Hourly capacity',profile),('Scenarios',scenarios[['scenario','requested','completed','fulfillment','shift_hours','service_utilization','occupied_utilization','boundary_cancellations','contention_cancellations']])]:
        payload[name]={'columns':list(df.columns),'rows':json.loads(df.to_json(orient='values'))}
    payload['Definitions']['rows'] += [
        ['Occupied utilization','Assignment to terminal event plus ten-minute turnaround, clipped to shift end / available minutes. Includes service, travel and accepted cancellations.'],
        ['Hourly workload','Expected duration placed at request arrival hour. Not concurrent occupancy. Weekdays 0=Monday through 6=Sunday.'],
        ['Scenarios','Hypothetical paired dispatch replays, not forecasts. Later close 14–22; lean split retains 10 workers/zone on original attended days, 07–11 and 17–21.'],
        ['Boundary diagnostic','Cannot fit even with empty workers on scheduled shifts. Contention means empty-schedule fit exists but reservations prevent assignment.'],
        ['Zero capacity','Hourly utilization is blank where no shift capacity exists; not zero. Shared capacity is not allocated across service categories.']]
    # Idempotent report refresh: preserve one definition per metric.
    payload['Definitions']['rows']=list({row[0]:row for row in payload['Definitions']['rows']}.values())
    (out/'workbook_data.json').write_text(json.dumps(payload))
    return zone
