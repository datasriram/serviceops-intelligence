import io,sqlite3
import numpy as np
import pandas as pd
import pytest
from src.analytics import ROOT,load_data,kpis,filter_data,capacity,export_csv
@pytest.fixture(scope='module')
def data():return load_data()
@pytest.fixture
def con():
    with sqlite3.connect(ROOT/'data/serviceops.db') as c:yield c
def test_keys(con):assert con.execute('PRAGMA foreign_key_check').fetchall()==[]
@pytest.mark.parametrize('table,key',[('customers','customer_id'),('workers','worker_id'),('locations','location_id'),('service_categories','service_id'),('bookings','booking_id'),('shifts','shift_id'),('booking_costs','booking_id'),('booking_status_events','event_id')])
def test_primary_keys(con,table,key):
    assert con.execute(f'SELECT COUNT(*)=COUNT(DISTINCT {key}) FROM {table}').fetchone()[0]
def test_status(data):
    b,_=data;assert set(b.status)=={'completed','cancelled'};assert b.is_simulated.eq(1).all()
def test_timestamps(data):
    b,_=data;a=b[b.assigned_at.notna()];c=b[b.status.eq('completed')];x=b[b.status.eq('cancelled')]
    assert (a.created_at<a.assigned_at).all();assert (c.assigned_at<c.start_at).all();assert (c.start_at<c.completed_at).all();assert (x.cancelled_at>x.created_at).all();assert x.completed_at.isna().all();assert c.cancelled_at.isna().all()
def test_shift_overlap(data):
    _,s=data;s=s.sort_values(['worker_id','start_at']);prev=s.groupby('worker_id').end_at.shift();assert (prev.isna()|(s.start_at>=prev)).all()
def test_assignments(data):
    b,s=data;a=b[b.assigned_at.notna()].sort_values(['worker_id','assigned_at']).copy();a['release']=a.completed_at.fillna(a.cancelled_at);prev=a.groupby('worker_id').release.shift()
    assert (prev.isna()|(a.assigned_at>=prev+pd.Timedelta(minutes=10))).all()
    m=a.merge(s,on='shift_id',suffixes=('_b','_s'));assert (m.worker_id_b==m.worker_id_s).all();assert (m.location_id_b==m.location_id_s).all();assert (m.assigned_at>=m.start_at_s).all();assert (m.release<=m.end_at).all()
def test_denominators(data):
    b,_=data;k=kpis(b);assert k['requested']==60000;assert k['completed']+k['cancelled']==k['requested'];assert k['fulfillment']+k['cancellation']==1;assert k['accepted']>=k['completed']
def test_revenue_margin(data):
    b,_=data;assert b.loc[b.status.eq('cancelled'),'revenue'].eq(0).all();assert b.loc[b.status.eq('completed'),'revenue'].equals(b.loc[b.status.eq('completed'),'quoted_value']);assert np.allclose(b.contribution_margin,b.revenue-b.worker_payout-b.materials-b.processing)
def test_utilization(data):
    b,s=data;c=capacity(b,s,'2025-01-01','2025-12-31',b.location.unique());assert c.utilization.between(0,1).all()
def test_filters_and_capacity(data):
    b,s=data;d=filter_data(b,'2025-03-01','2025-03-31',['Hebbal'],['Cleaning']);assert len(d)>0;assert d.location.eq('Hebbal').all();assert d.service.eq('Cleaning').all();assert d.created_at.dt.month.eq(3).all()
    allcat=filter_data(b,'2025-03-01','2025-03-31',['Hebbal'],b.service.unique());assert capacity(d,s,'2025-03-01','2025-03-31',['Hebbal']).available_minutes.sum()==capacity(allcat,s,'2025-03-01','2025-03-31',['Hebbal']).available_minutes.sum()
def test_empty(data):
    b,_=data;d=filter_data(b,'2025-01-01','2025-01-31',[],[]);assert kpis(d)['requested']==0;assert kpis(d)['abv']==0
def test_loading():
    with pytest.raises(FileNotFoundError):load_data(ROOT/'data/nonexistent.db')
def test_csv(data):
    b,_=data;d=b.head(10);r=pd.read_csv(io.BytesIO(export_csv(d)));assert len(r)==10;assert r.booking_id.tolist()==d.booking_id.tolist();assert list(r.columns)==list(d.columns)
def test_sql_python(data,con):
    b,_=data;k=kpis(b);row=con.execute("SELECT COUNT(*),SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END),SUM(revenue),SUM(contribution_margin) FROM booking_fact").fetchone();assert row[0]==k['requested'];assert row[1]==k['completed'];assert row[2]==pytest.approx(k['revenue']);assert row[3]==pytest.approx(k['contribution_margin'])
def test_events(con):
    assert con.execute("SELECT COUNT(*) FROM (SELECT b.booking_id FROM bookings b LEFT JOIN booking_status_events e ON e.booking_id=b.booking_id AND e.state=b.status GROUP BY b.booking_id HAVING COUNT(e.event_id)!=1)").fetchone()[0]==0
@pytest.mark.parametrize('page',range(4))
def test_dashboard_pages(page):
    from streamlit.testing.v1 import AppTest
    at=AppTest.from_file(str(ROOT/'dashboard/app.py'),default_timeout=30).run();at.sidebar.radio[0].set_value(['Executive Overview','Demand Intelligence','Workforce & Fulfillment','Revenue & Unit Economics'][page]).run();assert not at.exception
def test_dashboard_empty_filters():
    from streamlit.testing.v1 import AppTest
    at=AppTest.from_file(str(ROOT/'dashboard/app.py'),default_timeout=30).run();at.sidebar.multiselect[0].set_value([]).run();assert not at.exception;assert any('No bookings' in x.value for x in at.info)
def test_dashboard_filtered_kpis(data):
    from streamlit.testing.v1 import AppTest
    b,_=data
    at=AppTest.from_file(str(ROOT/'dashboard/app.py'),default_timeout=30).run()
    at.sidebar.multiselect[0].set_value(['Hebbal']);at.sidebar.multiselect[1].set_value(['Cleaning']);at.run()
    assert not at.exception
    assert at.metric[0].value==f"{len(b[b.location.eq('Hebbal') & b.service.eq('Cleaning')]):,}"

@pytest.mark.parametrize('page',range(4))
def test_dashboard_all_filters(page,data):
    from streamlit.testing.v1 import AppTest
    b,_=data
    at=AppTest.from_file(str(ROOT/'dashboard/app.py'),default_timeout=45).run()
    at.sidebar.radio[0].set_value(['Executive Overview','Demand Intelligence','Workforce & Fulfillment','Revenue & Unit Economics'][page])
    at.sidebar.date_input[0].set_value((pd.Timestamp('2025-03-01').date(),pd.Timestamp('2025-03-31').date()))
    at.sidebar.multiselect[0].set_value(['Hebbal']);at.sidebar.multiselect[1].set_value(['Cleaning']);at.run()
    assert not at.exception
    expected=filter_data(b,'2025-03-01','2025-03-31',['Hebbal'],['Cleaning'])
    if page==0:assert at.metric[0].value==f'{len(expected):,}'
    if page==3:assert at.metric[0].value==f'₹{expected.revenue.sum():,.0f}'
