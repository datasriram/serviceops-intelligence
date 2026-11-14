"""Deterministic discrete-event simulation. All records are synthetic."""
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
def generate(seed=42,n=60000,inputs_only=False):
    rng=np.random.default_rng(seed)
    locations=pd.DataFrame({'location_id':range(1,7),'location':['Indiranagar','Koramangala','Whitefield','HSR Layout','Jayanagar','Hebbal']})
    services=pd.DataFrame({'service_id':[1,2,3],'service':['Cleaning','Dishwashing','Laundry'],'base_price':[399,199,299],'expected_minutes':[70,35,55]})
    customers=pd.DataFrame({'customer_id':range(1,12001),'location_id':rng.choice(range(1,7),12000,p=[.20,.20,.19,.17,.14,.10])})
    workers=pd.DataFrame({'worker_id':range(1,109),'location_id':np.repeat(range(1,7),18),'productivity':rng.uniform(.85,1.18,108)})
    productivity=workers.set_index('worker_id').productivity.to_dict()
    shifts=[]; sid=0
    for day in pd.date_range('2025-01-01','2025-12-31'):
        for w in workers.itertuples():
            if rng.random()<.81:
                sid+=1; hour=7 if w.worker_id%2 else 13
                start=day+pd.Timedelta(hours=hour)
                shifts.append((sid,w.worker_id,w.location_id,start,start+pd.Timedelta(hours=8)))
    shifts=pd.DataFrame(shifts,columns=['shift_id','worker_id','location_id','start_at','end_at'])
    # Requests span all 365 days, with mild growth and weekend seasonality.
    days=pd.date_range('2025-01-01','2025-12-31'); p=np.array([(1+.25*i/365)*(1.18 if d.dayofweek>=5 else 1) for i,d in enumerate(days)]); p/=p.sum()
    dates=rng.choice(days,n,p=p)
    hp=np.array([7,13,13,8,5,4,4,5,7,10,12,10,6,3]);hours=rng.choice(range(7,21),n,p=hp/hp.sum())
    created=pd.to_datetime(dates)+pd.to_timedelta(hours,unit='h')+pd.to_timedelta(rng.integers(0,60,n),unit='m')
    weights=rng.pareto(1.8,12000)+.3;weights/=weights.sum()
    cids=rng.choice(range(1,12001),n,p=weights)
    base=pd.DataFrame({'booking_id':range(1,n+1),'customer_id':cids,'service_id':rng.choice([1,2,3],n,p=[.48,.30,.22]),'created_at':created}).sort_values(['created_at','booking_id'])
    locmap=customers.set_index('customer_id').location_id
    shiftmap={k:list(g.itertuples()) for k,g in shifts.groupby([shifts.start_at.dt.date,'location_id'])}
    free={}; records=[];costs=[];events=[];inputs=[]
    for b in base.itertuples():
        loc=int(locmap[b.customer_id]);s=services.iloc[b.service_id-1];t=b.created_at
        dur=int(np.clip(rng.normal(s.expected_minutes,10),20,110))
        assigned=start=end=cancel=None;worker=shift=None;reason=None
        status='cancelled';candidate=None
        if rng.random()<.065:
            reason='Customer changed plans';cancel=t+pd.Timedelta(minutes=int(rng.integers(1,12)))
        else:
            sg=shiftmap.get((t.date(),loc))
            if sg is not None:
                for sh in sg:
                    a=max(t+pd.Timedelta(minutes=2),sh.start_at,free.get(sh.worker_id,sh.start_at))
                    st=a+pd.Timedelta(minutes=10);en=st+pd.Timedelta(minutes=int(dur/productivity[sh.worker_id]))
                    if en<=sh.end_at and a<=t+pd.Timedelta(minutes=45):
                        if candidate is None or a<candidate[0]:candidate=(a,st,en,sh)
            if candidate is None:
                reason='No capacity within 45 minutes';cancel=t+pd.Timedelta(minutes=45)
            else:
                assigned,start,end,sh=candidate;worker=sh.worker_id;shift=sh.shift_id
                if rng.random()<.035:
                    reason='Customer cancelled after assignment';cancel=assigned+pd.Timedelta(minutes=3);start=end=None
                    free[worker]=cancel+pd.Timedelta(minutes=10)
                else:
                    status='completed';free[worker]=end+pd.Timedelta(minutes=10)
        quote=int(s.base_price+(29 if t.hour in [8,9,17,18] else 0))
        revenue=quote if status=='completed' else 0
        payout=round((end-start).total_seconds()/60*2.1,2) if end is not None else (15 if worker else 0)
        materials=round(revenue*.045,2);processing=round(revenue*.02,2)
        costs.append((b.booking_id,quote,revenue,payout,materials,processing))
        records.append((b.booking_id,b.customer_id,b.service_id,loc,worker,shift,t,assigned,start,end,cancel,status,reason,dur,1))
        for state,at in [('requested',t),('accepted',assigned),('completed',end),('cancelled',cancel)]:
            if at is not None:events.append((len(events)+1,b.booking_id,state,at))
        # Capture original latent duration and realized cancellation propensity without
        # consuming RNG draws. Newly feasible requests use a separate keyed seed.
        post=reason=='Customer cancelled after assignment' if worker else np.random.default_rng(seed+b.booking_id+100000).random()<.035
        inputs.append((b.booking_id,dur,reason=='Customer changed plans',bool(post)))
    bookings=pd.DataFrame(records,columns=['booking_id','customer_id','service_id','location_id','worker_id','shift_id','created_at','assigned_at','start_at','completed_at','cancelled_at','status','cancellation_reason','expected_minutes','is_simulated'])
    costs=pd.DataFrame(costs,columns=['booking_id','quoted_value','revenue','worker_payout','materials','processing'])
    events=pd.DataFrame(events,columns=['event_id','booking_id','state','event_at'])
    tables={'locations':locations,'service_categories':services,'customers':customers,'workers':workers,'shifts':shifts,'bookings':bookings,'booking_costs':costs,'booking_status_events':events}
    if inputs_only:
        from src.analytics import load_data
        old,_=load_data()
        check=bookings.sort_values('booking_id').reset_index(drop=True)
        old=old.sort_values('booking_id').reset_index(drop=True)
        assert check.status.equals(old.status), 'Baseline replay changed final statuses'
        for col in ['assigned_at','start_at','completed_at','cancelled_at']:
            pd.testing.assert_series_equal(pd.to_datetime(check[col]),old[col],check_names=False)
        assert costs.revenue.sum()==old.revenue.sum()
        pd.DataFrame(inputs,columns=['booking_id','latent_minutes','pre_cancel','post_cancel']).to_csv(ROOT/'data/request_inputs.csv',index=False)
        return {'baseline_preserved':True,'request_inputs':len(inputs)}
    pd.DataFrame(inputs,columns=['booking_id','latent_minutes','pre_cancel','post_cancel']).to_csv(ROOT/'data/request_inputs.csv',index=False)
    db=ROOT/'data/serviceops.db';db.unlink(missing_ok=True)
    with sqlite3.connect(db) as con:
        con.executescript((ROOT/'sql/schema.sql').read_text())
        for name,df in tables.items():
            for col in df.select_dtypes('datetime').columns:df[col]=df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
            df.to_sql(name,con,if_exists='append',index=False)
            df.to_csv(ROOT/f'data/{name}.csv',index=False)
    return {k:len(v) for k,v in tables.items()}
if __name__=='__main__':print(generate())
