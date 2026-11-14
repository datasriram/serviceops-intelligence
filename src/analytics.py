from pathlib import Path
import sqlite3
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def load_data(path=None):
    path=Path(path or ROOT/'data/serviceops.db')
    if not path.exists():raise FileNotFoundError('Run python -m src.build first.')
    with sqlite3.connect(path) as c:
        b=pd.read_sql('SELECT * FROM booking_fact',c)
        s=pd.read_sql('SELECT s.*,l.location FROM shifts s JOIN locations l USING(location_id)',c)
    for col in ['created_at','assigned_at','start_at','completed_at','cancelled_at']:b[col]=pd.to_datetime(b[col])
    for col in ['start_at','end_at']:s[col]=pd.to_datetime(s[col])
    b['assignment_minutes']=(b.assigned_at-b.created_at).dt.total_seconds()/60
    b['service_minutes']=(b.completed_at-b.start_at).dt.total_seconds()/60
    b['month']=b.created_at.dt.strftime('%Y-%m');b['day']=b.created_at.dt.strftime('%Y-%m-%d')
    b['hour']=b.created_at.dt.hour;b['weekday']=b.created_at.dt.dayofweek
    return b,s
def filter_data(b,start,end,locations,services):
    return b[b.created_at.dt.date.between(pd.Timestamp(start).date(),pd.Timestamp(end).date()) & b.location.isin(locations)&b.service.isin(services)].copy()
def kpis(b):
    n=len(b);completed=int(b.status.eq('completed').sum())
    return dict(requested=n,accepted=int(b.assigned_at.notna().sum()),completed=completed,cancelled=n-completed,fulfillment=completed/n if n else 0,cancellation=(n-completed)/n if n else 0,revenue=float(b.revenue.sum()),abv=float(b.revenue.sum()/completed) if completed else 0,contribution_margin=float(b.contribution_margin.sum()),assignment_minutes=float(b.assignment_minutes.mean()) if b.assignment_minutes.notna().any() else 0)
def summary(b,group):
    return b.groupby(group).agg(requested=('booking_id','size'),completed=('status',lambda x:x.eq('completed').sum()),accepted=('assigned_at','count'),revenue=('revenue','sum'),cost=('worker_payout','sum'),materials=('materials','sum'),processing=('processing','sum'),margin=('contribution_margin','sum'),assignment_minutes=('assignment_minutes','mean')).reset_index()
def capacity(b,s,start,end,locations):
    """Service-category filters affect busy minutes, never duplicate/shared shift capacity."""
    s=s[s.start_at.dt.date.between(pd.Timestamp(start).date(),pd.Timestamp(end).date())&s.location.isin(locations)].copy()
    s['available_minutes']=(s.end_at-s.start_at).dt.total_seconds()/60
    avail=s.groupby('location').available_minutes.sum()
    busy=b.groupby('location').service_minutes.sum()
    requested=b.groupby('location').expected_minutes.sum()
    out=pd.concat([avail,busy,requested],axis=1).fillna(0).rename(columns={'service_minutes':'busy_minutes','expected_minutes':'requested_minutes'}).reset_index()
    out['utilization']=out.busy_minutes.div(out.available_minutes.replace(0,float('nan'))).fillna(0)
    out['aggregate_gap_minutes']=(out.requested_minutes-out.available_minutes).clip(lower=0)
    return out
def export_csv(b):return b.to_csv(index=False).encode('utf-8')

def location_performance(b):
    out=summary(b,'location')
    out['fulfillment']=out.completed/out.requested
    out['cancellation']=1-out.fulfillment
    out['abv']=out.revenue.div(out.completed.replace(0,float('nan')))
    out['margin_rate']=out.margin.div(out.revenue.replace(0,float('nan')))
    return out
