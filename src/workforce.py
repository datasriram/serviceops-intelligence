"""Hourly interval accounting and paired hypothetical schedule dispatch replays."""
import json
import numpy as np
import pandas as pd
from src.analytics import ROOT, load_data, kpis

ORIGIN=pd.Timestamp('2025-01-01')
SCENARIOS={
    'baseline': 'Original 07–15 / 13–21 shifts; observed attendance and all workers retained.',
    'later_close': 'Same workers, attendance and 8-hour shifts; late shifts move from 13–21 to 14–22.',
    'lean_split': 'Workers with within-zone ID 1–10 retained; 4-hour split shifts 07–11 and 17–21, using original attended days. Hypothetical split-shift acceptability is unvalidated.',
}

def scenario_shifts(s,name):
    if name not in SCENARIOS:raise ValueError(name)
    out=s.copy()
    if name=='later_close':
        late=out.start_at.dt.hour.eq(13)
        out.loc[late,'start_at']+=pd.Timedelta(hours=1);out.loc[late,'end_at']+=pd.Timedelta(hours=1)
    elif name=='lean_split':
        out=out[(out.worker_id-1)%18<10].copy()
        out['start_at']=out.start_at.dt.normalize()+pd.Timedelta(hours=7)
        out['end_at']=out.start_at+pd.Timedelta(hours=4)
        late=out.copy();late.start_at+=pd.Timedelta(hours=10);late.end_at+=pd.Timedelta(hours=10)
        out=pd.concat([out,late],ignore_index=True)
    # Retain source row order to preserve the baseline dispatch tie-break rule.
    out=out.reset_index(drop=True)
    out['shift_id']=np.arange(1,len(out)+1)
    # Baseline ties must retain original worker order and identifiers.
    return s.copy() if name=='baseline' else out

def replay(b,s,workers,inputs):
    """Greedy dispatch rerun on identical latent requests, with failure diagnostics.

    A no-capacity request is boundary-limited if it cannot fit even with empty
    workers on today's scheduled shifts; otherwise existing reservations bind.
    This counterfactual is diagnostic, not a unique causal attribution.
    """
    p=workers.set_index('worker_id').productivity.to_dict()
    shifts={}
    for sh in s.itertuples():
        start=(sh.start_at-ORIGIN).total_seconds()/60;end=(sh.end_at-ORIGIN).total_seconds()/60
        shifts.setdefault((int(start//1440),sh.location_id),[]).append((sh.worker_id,sh.shift_id,start,end))
    free={};rows=[]
    requests=b.merge(inputs,on='booking_id',validate='one_to_one').sort_values(['created_at','booking_id'])
    for r in requests.itertuples():
        t=(r.created_at-ORIGIN).total_seconds()/60
        assigned=start=end=cancel=np.nan;worker=shift=np.nan;reason=None;diagnosis=None;delay_cause=None
        candidate=None;empty_earliest=np.inf
        if r.pre_cancel:
            reason='Customer changed plans';cancel=(r.cancelled_at-ORIGIN).total_seconds()/60
        else:
            for w,sh,a,z in shifts.get((int(t//1440),r.location_id),[]):
                duration=int(r.latent_minutes/p[w]);empty=max(t+2,a)
                if empty<=t+45 and empty+10+duration<=z:empty_earliest=min(empty_earliest,empty)
                accept=max(t+2,a,free.get(w,a));finish=accept+10+duration
                if accept<=t+45 and finish<=z and (candidate is None or accept<candidate[0]):candidate=(accept,finish,w,sh,z)
            if candidate is None:
                reason='No capacity within 45 minutes';cancel=t+45
                diagnosis='Shift window / duration' if np.isinf(empty_earliest) else 'Reservation contention'
            else:
                assigned,end,worker,shift,shift_end=candidate;start=assigned+10
                delay_cause='Reservation contention' if assigned>empty_earliest else ('Shift opening' if assigned>t+2 else 'Minimum dispatch latency')
                if r.post_cancel:
                    reason='Customer cancelled after assignment';cancel=assigned+3;start=end=np.nan
                    free[worker]=cancel+10
                else:free[worker]=end+10
        status='completed' if not np.isnan(end) else 'cancelled'
        revenue=r.quoted_value if status=='completed' else 0
        payout=round((end-start)*2.1,2) if status=='completed' else (15 if not np.isnan(worker) else 0)
        rows.append((r.booking_id,worker,shift,assigned,start,end,cancel,status,reason,diagnosis,delay_cause,revenue,payout,round(revenue*.045,2),round(revenue*.02,2)))
    result=pd.DataFrame(rows,columns=['booking_id','worker_id','shift_id','assigned_at','start_at','completed_at','cancelled_at','status','cancellation_reason','failure_diagnostic','delay_diagnostic','revenue','worker_payout','materials','processing'])
    for c in ['assigned_at','start_at','completed_at','cancelled_at']:result[c]=ORIGIN+pd.to_timedelta(result[c],unit='m')
    metadata=b[['booking_id','location_id','location','service','service_id','created_at','expected_minutes','quoted_value']]
    result=result.merge(metadata,on='booking_id',validate='one_to_one')
    result['service_minutes']=(result.completed_at-result.start_at).dt.total_seconds()/60
    result['assignment_minutes']=(result.assigned_at-result.created_at).dt.total_seconds()/60
    result['contribution_margin']=result.revenue-result.worker_payout-result.materials-result.processing
    return result

def hourly_capacity(b,s,start,end,locations):
    """Daily-zone-hour grid; exact half-open interval overlaps, in worker-minutes.

    Workload is expected service minutes of requests arriving in the bucket,
    NOT an interval occupancy estimate. Occupied = accepted reservation through
    terminal event plus ten-minute turnaround, clipped to shift end. Includes
    pre-service travel and accepted cancellation time, excludes pre-assignment wait.
    """
    lo=pd.Timestamp(start).normalize();hi=pd.Timestamp(end).normalize()+pd.Timedelta(days=1)
    hours=pd.date_range(lo,hi,freq='h',inclusive='left');locs=list(locations)
    index=pd.MultiIndex.from_product([locs,hours],names=['location','period'])
    out=pd.DataFrame(0.,index=index,columns=['available_minutes','service_minutes','occupied_minutes','request_workload_minutes','requested'])
    if not locs:return out.reset_index()
    length=len(hours);locidx={x:i for i,x in enumerate(locs)}
    def intervals(df,begin,finish,column):
        arr=np.zeros(len(index))
        for loc,a,z in df[['location',begin,finish]].itertuples(index=False,name=None):
            if loc not in locidx or pd.isna(a) or pd.isna(z):continue
            a=max(a,lo);z=min(z,hi)
            if z<=a:continue
            amin=(a-lo).total_seconds()/60;zmin=(z-lo).total_seconds()/60
            for h in range(int(amin//60),int(np.ceil(zmin/60))):arr[locidx[loc]*length+h]+=min(zmin,(h+1)*60)-max(amin,h*60)
        out[column]=arr
    intervals(s,'start_at','end_at','available_minutes')
    intervals(b,'start_at','completed_at','service_minutes')
    accepted=b[b.assigned_at.notna()].copy()
    accepted=accepted.merge(s[['shift_id','end_at']],on='shift_id',validate='many_to_one')
    accepted['occupied_end']=accepted.completed_at.fillna(accepted.cancelled_at)+pd.Timedelta(minutes=10)
    accepted['occupied_end']=accepted[['occupied_end','end_at']].min(axis=1)
    intervals(accepted,'assigned_at','occupied_end','occupied_minutes')
    arrivals=b[b.location.isin(locs)&b.created_at.between(lo,hi,inclusive='left')].copy();arrivals['period']=arrivals.created_at.dt.floor('h')
    grouped=arrivals.groupby(['location','period']).agg(request_workload_minutes=('expected_minutes','sum'),requested=('booking_id','size'))
    out[['request_workload_minutes','requested']]=grouped.reindex(index,fill_value=0)
    out['service_utilization']=out.service_minutes.div(out.available_minutes.replace(0,np.nan))
    out['occupied_utilization']=out.occupied_minutes.div(out.available_minutes.replace(0,np.nan))
    out['unoccupied_minutes']=out.available_minutes-out.occupied_minutes
    return out.reset_index()

def build_workforce():
    import sqlite3
    b,s=load_data();path=ROOT/'data/request_inputs.csv'
    if not path.exists():
        from src.generate import generate
        generate(inputs_only=True)
    inputs=pd.read_csv(path)
    with sqlite3.connect(ROOT/'data/serviceops.db') as c:workers=pd.read_sql('SELECT * FROM workers',c)
    destination=ROOT/'reports/scenarios';destination.mkdir(exist_ok=True)
    rows=[]
    for name in SCENARIOS:
        sh=scenario_shifts(s,name);r=replay(b,sh,workers,inputs)
        if name=='baseline':
            old=b.sort_values('booking_id').reset_index(drop=True);new=r.sort_values('booking_id').reset_index(drop=True)
            for col in ['status','worker_id','assigned_at','start_at','completed_at','cancelled_at']:
                pd.testing.assert_series_equal(old[col],new[col],check_names=False,check_dtype=False)
            for col in ['revenue','worker_payout','materials','processing','contribution_margin']:assert np.allclose(old[col],new[col])
        r.to_csv(destination/f'{name}_bookings.csv',index=False);sh.to_csv(destination/f'{name}_shifts.csv',index=False)
        h=hourly_capacity(r,sh,'2025-01-01','2025-12-31',sorted(b.location.unique()))
        h.to_csv(destination/f'{name}_hourly.csv',index=False)
        if name=='baseline':
            r[['booking_id','failure_diagnostic','delay_diagnostic']].to_csv(ROOT/'reports/dispatch_diagnostics.csv',index=False)
            h.to_csv(ROOT/'reports/hourly_capacity.csv',index=False)
        k=kpis(r);available=h.available_minutes.sum()
        rows.append(dict(scenario=name,**k,shift_hours=available/60,service_utilization=h.service_minutes.sum()/available,occupied_utilization=h.occupied_minutes.sum()/available,boundary_cancellations=int(r.failure_diagnostic.eq('Shift window / duration').sum()),contention_cancellations=int(r.failure_diagnostic.eq('Reservation contention').sum())))
    summary=pd.DataFrame(rows);summary.to_csv(ROOT/'reports/staffing_scenarios.csv',index=False)
    (ROOT/'reports/scenario_assumptions.json').write_text(json.dumps(SCENARIOS,indent=2))
    print(summary.to_string(index=False))
    return summary
if __name__=='__main__':build_workforce()
