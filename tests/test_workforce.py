import sqlite3,re,json
import numpy as np
import pandas as pd
import pytest
from src.analytics import ROOT,load_data,filter_data,location_performance
from src.workforce import hourly_capacity,replay,scenario_shifts,SCENARIOS

def test_hourly_exact_intervals():
    s=pd.DataFrame({'shift_id':[1],'location':['A'],'start_at':pd.to_datetime(['2025-01-01 07:30']),'end_at':pd.to_datetime(['2025-01-01 09:15'])})
    b=pd.DataFrame({'location':['A'],'shift_id':[1],'created_at':pd.to_datetime(['2025-01-01 07:35']),'assigned_at':pd.to_datetime(['2025-01-01 07:40']),'start_at':pd.to_datetime(['2025-01-01 07:50']),'completed_at':pd.to_datetime(['2025-01-01 08:20']),'cancelled_at':[pd.NaT],'expected_minutes':[55],'booking_id':[1]})
    h=hourly_capacity(b,s,'2025-01-01','2025-01-01',['A']).set_index('period')
    assert len(h)==24
    assert h.available_minutes.sum()==105;assert h.service_minutes.sum()==30;assert h.occupied_minutes.sum()==50;assert h.request_workload_minutes.sum()==55
    for hour,avail,service,occupied in [(7,30,10,20),(8,60,20,30),(9,15,0,0)]:
        row=h.loc[pd.Timestamp(f'2025-01-01 {hour:02d}:00')];assert tuple(row[['available_minutes','service_minutes','occupied_minutes']])==(avail,service,occupied)
    assert pd.isna(h.iloc[0].occupied_utilization)

def test_hourly_reservation_clip_and_cancellation():
    s=pd.DataFrame({'shift_id':[1],'location':['A'],'start_at':pd.to_datetime(['2025-01-01 07:00']),'end_at':pd.to_datetime(['2025-01-01 08:00'])})
    b=pd.DataFrame({'location':['A'],'shift_id':[1],'created_at':pd.to_datetime(['2025-01-01 07:45']),'assigned_at':pd.to_datetime(['2025-01-01 07:50']),'start_at':[pd.NaT],'completed_at':[pd.NaT],'cancelled_at':pd.to_datetime(['2025-01-01 07:53']),'expected_minutes':[30],'booking_id':[1]})
    h=hourly_capacity(b,s,'2025-01-01','2025-01-01',['A']);assert h.occupied_minutes.sum()==10;assert h.service_minutes.sum()==0

@pytest.fixture(scope='module')
def original():return load_data()

def test_hourly_conservation_and_utilization(original):
    b,s=original;h=pd.read_csv(ROOT/'reports/hourly_capacity.csv')
    assert len(h)==6*365*24
    assert h.available_minutes.sum()==pytest.approx((s.end_at-s.start_at).dt.total_seconds().sum()/60)
    assert h.service_minutes.sum()==pytest.approx(b.service_minutes.sum())
    assert h.request_workload_minutes.sum()==b.expected_minutes.sum();assert h.requested.sum()==len(b)
    assert (h.occupied_minutes>=h.service_minutes).all();assert (h.occupied_minutes<=h.available_minutes+1e-8).all()
    assert h.occupied_utilization.dropna().between(0,1).all()
    assert h.loc[h.available_minutes.eq(0),'occupied_utilization'].isna().all()

def test_hourly_date_location_category_scope(original):
    b,s=original;start='2025-03-01';end='2025-03-02';locs=['Hebbal']
    x=filter_data(b,start,end,locs,['Cleaning']);allcat=filter_data(b,start,end,locs,b.service.unique())
    h=hourly_capacity(x,s,start,end,locs);a=hourly_capacity(allcat,s,start,end,locs)
    assert len(h)==48;assert h.available_minutes.sum()==a.available_minutes.sum();assert h.requested.sum()==len(x);assert h.service_minutes.sum()==pytest.approx(x.service_minutes.sum());assert h.occupied_minutes.sum()<=a.occupied_minutes.sum()

def test_replay_baseline_preserved(original):
    b,s=original;r=pd.read_csv(ROOT/'reports/scenarios/baseline_bookings.csv').sort_values('booking_id');b=b.sort_values('booking_id')
    assert r.status.tolist()==b.status.tolist();assert r.worker_id.fillna(-1).tolist()==b.worker_id.fillna(-1).tolist()
    for c in ['assigned_at','completed_at','cancelled_at']:assert pd.to_datetime(r[c]).reset_index(drop=True).equals(b[c].reset_index(drop=True))
    assert r.revenue.sum()==17211937;assert r.contribution_margin.sum()==pytest.approx(10058501.88)

@pytest.mark.parametrize('name',list(SCENARIOS))
def test_scenario_constraints(name):
    r=pd.read_csv(ROOT/f'reports/scenarios/{name}_bookings.csv');s=pd.read_csv(ROOT/f'reports/scenarios/{name}_shifts.csv')
    for c in ['assigned_at','start_at','completed_at','cancelled_at']:r[c]=pd.to_datetime(r[c])
    for c in ['start_at','end_at']:s[c]=pd.to_datetime(s[c])
    a=r[r.assigned_at.notna()].copy().sort_values(['worker_id','assigned_at']);a['release']=a.completed_at.fillna(a.cancelled_at)
    prev=a.groupby('worker_id').release.shift();assert (prev.isna()|(a.assigned_at>=prev+pd.Timedelta(minutes=10))).all()
    m=a.merge(s,on='shift_id',suffixes=('_b','_s'));assert (m.worker_id_b==m.worker_id_s).all();assert (m.assigned_at>=m.start_at_s).all();assert (m.release<=m.end_at).all()
    s=s.sort_values(['worker_id','start_at']);prev=s.groupby('worker_id').end_at.shift();assert (prev.isna()|(s.start_at>=prev)).all()
    assert r.booking_id.nunique()==60000
    assert r.status.eq('completed').sum()+r.status.eq('cancelled').sum()==60000
    assert r.failure_diagnostic.notna().sum()==r.cancellation_reason.eq('No capacity within 45 minutes').sum()

def test_dispatch_counterfactual_and_determinism():
    b=pd.DataFrame({'booking_id':[1,2],'created_at':pd.to_datetime(['2025-01-01 07:00','2025-01-01 07:40']),'cancelled_at':[pd.NaT,pd.NaT],'location_id':[1,1],'location':['A','A'],'service':['Cleaning','Cleaning'],'service_id':[1,1],'expected_minutes':[40,30],'quoted_value':[399,399]})
    s=pd.DataFrame({'shift_id':[1],'worker_id':[1],'location_id':[1],'location':['A'],'start_at':pd.to_datetime(['2025-01-01 07:00']),'end_at':pd.to_datetime(['2025-01-01 08:00'])})
    w=pd.DataFrame({'worker_id':[1],'productivity':[1.]});i=pd.DataFrame({'booking_id':[1,2],'latent_minutes':[40,30],'pre_cancel':[False,False],'post_cancel':[False,False]})
    r=replay(b,s,w,i);assert r.status.tolist()==['completed','cancelled'];assert r.iloc[1].failure_diagnostic=='Shift window / duration'
    s.end_at+=pd.Timedelta(hours=1);a=replay(b,s,w,i);assert a.status.eq('completed').all();assert a.iloc[1].delay_diagnostic=='Reservation contention'
    pd.testing.assert_frame_equal(a,replay(b,s,w,i))
    # The same service fits an empty shift, but a prior reservation prevents it.
    s.end_at-=pd.Timedelta(hours=1);b.loc[1,'created_at']=pd.Timestamp('2025-01-01 07:01')
    congested=replay(b,s,w,i);assert congested.iloc[1].failure_diagnostic=='Reservation contention'

def test_scenario_attendance_and_hours(original):
    _,s=original;a=scenario_shifts(s,'later_close');assert len(a)==len(s);assert a.worker_id.tolist()==s.worker_id.tolist();assert (a.end_at-a.start_at).eq(pd.Timedelta(hours=8)).all()
    lean=scenario_shifts(s,'lean_split');assert lean.worker_id.nunique()==60;assert len(lean)==2*len(s[(s.worker_id-1)%18<10]);assert (lean.end_at-lean.start_at).eq(pd.Timedelta(hours=4)).all()

def test_all_sql_outputs(original):
    b,s=original
    with sqlite3.connect(ROOT/'data/serviceops.db') as c:
        q={name:pd.read_sql(query,c) for name,query in re.findall(r'-- name: (\w+)\n(.*?)(?=-- name:|\Z)',(ROOT/'sql/analyses.sql').read_text(),re.S)}
    assert len(q)==12
    assert q['daily_volume'].requested.tolist()==b.groupby('day').size().tolist()
    assert q['monthly_kpis'].completed.tolist()==b.groupby('month').status.apply(lambda x:x.eq('completed').sum()).tolist()
    expected=b.assign(cancel=b.status.eq('cancelled')).groupby(['location','service']).cancel.mean().sort_index()
    actual=q['cancellations'].set_index(['location','service']).cancellation_rate.sort_index();assert np.allclose(actual,expected)
    assert q['hourly_weekly_demand'].set_index(['weekday','hour']).requested.sort_index().tolist()==b.groupby(['weekday','hour']).size().sort_index().tolist()
    assert np.allclose(q['assignment_delays'].set_index('location').assignment_minutes.sort_index(),b.groupby('location').assignment_minutes.mean().sort_index(),atol=1e-5)
    u=q['utilization'];assert u.busy_minutes.sum()==pytest.approx(b.service_minutes.sum(),abs=.01);assert u.available_minutes.sum()==pytest.approx((s.end_at-s.start_at).dt.total_seconds().sum()/60,abs=.01)
    rep=b.groupby('customer_id').size();assert set(q['repeat_customers'].customer_id)==set(rep[rep>1].index)
    assert q['average_booking_value'].iloc[0,0]==pytest.approx(b.revenue.sum()/b.status.eq('completed').sum())
    assert q['revenue_by_service'].revenue.sum()==b.revenue.sum()
    assert q['margin_by_location'].contribution_margin.sum()==pytest.approx(b.contribution_margin.sum())
    z=location_performance(b);assert set(q['underperforming_zones'].location)==set(z.loc[z.fulfillment<b.status.eq('completed').mean(),'location'])
    assert q['demand_capacity_gaps'].requested_minutes.sum()==b.expected_minutes.sum();assert q['demand_capacity_gaps'].gap_minutes.ge(0).all()

def test_excel_formulas_and_cached_values():
    from openpyxl import load_workbook
    path=ROOT/'reports/serviceops_operations.xlsx';f=load_workbook(path,data_only=False);v=load_workbook(path,data_only=True)
    assert {'Hourly capacity','Scenarios'}.issubset(f.sheetnames)
    for name in ['Monthly','Locations','Services']:
        for row in range(5,f[name].max_row+1):
            assert f[name].cell(row,11).value==f'=IF(B{row}=0,0,C{row}/B{row})'
            n=v[name].cell(row,2).value;c=v[name].cell(row,3).value;revenue=v[name].cell(row,5).value
            assert f[name].cell(row,12).value==f'=IF(B{row}=0,0,(B{row}-C{row})/B{row})'
            assert f[name].cell(row,13).value==f'=IF(C{row}=0,0,E{row}/C{row})'
            for col,expected in [(11,c/n),(12,(n-c)/n),(13,revenue/c)]:
                cached=v[name].cell(row,col).value
                # openpyxl refresh delegates calculation to Excel; shipped Artifact
                # Tool snapshot has cached values, both paths retain exact formulas.
                if cached is not None:assert cached==pytest.approx(expected)
    s=f['Hourly capacity']
    for row in range(5,s.max_row+1):
        assert s.cell(row,8).value==f'=IF(C{row}=0,"",D{row}/C{row})'
        assert s.cell(row,9).value==f'=IF(C{row}=0,"",E{row}/C{row})'
    for s in v:
        for row in s:
            assert not any(c.data_type=='e' for c in row)

def test_report_refresh_is_idempotent(original):
    from src.review_reports import write_review
    path=ROOT/'reports/workbook_data.json';before=json.loads(path.read_text())
    write_review(*original);after=json.loads(path.read_text())
    assert before==after
