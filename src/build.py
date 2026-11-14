"""Build data, execute all SQL analyses, and calculate reports."""
import json
import re
import sqlite3
import pandas as pd
from src.analytics import ROOT,load_data,kpis,summary,capacity
from src.generate import generate
def reports():
    b,s=load_data();out=ROOT/'reports';qdir=out/'query_outputs';qdir.mkdir(exist_ok=True)
    with sqlite3.connect(ROOT/'data/serviceops.db') as con:
        for name,query in re.findall(r'-- name: (\w+)\n(.*?)(?=-- name:|\Z)',(ROOT/'sql/analyses.sql').read_text(),re.S):
            pd.read_sql(query,con).to_csv(qdir/f'{name}.csv',index=False)
        counts={t:con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ['customers','workers','locations','service_categories','shifts','bookings','booking_costs','booking_status_events']}
    k=kpis(b);(out/'kpis.json').write_text(json.dumps({'kpis':k,'row_counts':counts},indent=2))
    cap=capacity(b,s,'2025-01-01','2025-12-31',b.location.unique())
    sheets={name:summary(b,key) for name,key in [('Monthly','month'),('Locations','location'),('Services','service')]}
    sheets['Workforce']=cap
    worker=s.groupby('worker_id').size().reset_index(name='shifts');busy=b.groupby('worker_id').service_minutes.sum().reset_index();worker=worker.merge(busy,on='worker_id',how='left').fillna(0);worker['available_minutes']=worker.shifts*480;worker['utilization']=worker.service_minutes/worker.available_minutes;sheets['Workers']=worker
    sheets['Demand pivot']=b.pivot_table(index='weekday',columns='hour',values='booking_id',aggfunc='count',fill_value=0).reset_index()
    sheets['Definitions']=pd.DataFrame([
        ['Source','All records and findings are simulated. Seed 42; Jan–Dec 2025; Asia/Kolkata; INR.'],
        ['Requested','All bookings created in the reporting dates.'],['Accepted','Assigned at least once, including later cancellations.'],['Fulfillment','Completed / requested.'],['Cancellation','Cancelled / requested.'],['ABV','Realized revenue / completed bookings.'],['Revenue','Completed service charges; cohort reporting by request creation.'],['Contribution','Revenue minus payouts, materials and processing, including cancellation payout. Excludes fixed costs.'],['Utilization','Completed service minutes / all shift minutes. Excludes travel.'],['Capacity','Shared across service categories; aggregate gaps can conceal time-specific shortages.'],['Provenance','Independent synthetic model; no Snabbit internal information. See reports/data_provenance.md.']],columns=['Metric','Definition'])
    payload={name:{'columns':list(map(str,df.columns)),'rows':json.loads(df.to_json(orient='values'))} for name,df in sheets.items()}
    (out/'workbook_data.json').write_text(json.dumps(payload))
    b.describe(include='all').astype(str).to_csv(out/'descriptive_statistics.csv')
    from src.workforce import build_workforce
    from src.review_reports import write_review
    build_workforce()
    write_review(b)

if __name__=='__main__':
    if not (ROOT/'data/serviceops.db').exists():generate()
    reports()
