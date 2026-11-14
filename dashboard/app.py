"""Request-cohort dashboard with exact hourly interval accounting."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import streamlit as st
import pandas as pd
import plotly.express as px
from src.analytics import ROOT,load_data,filter_data,kpis,summary,capacity,export_csv,location_performance
from src.workforce import hourly_capacity,SCENARIOS
st.set_page_config(page_title='ServiceOps Intelligence',layout='wide')
@st.cache_data
def cached_load(signature):
    b,s=load_data()
    p=ROOT/'reports/dispatch_diagnostics.csv'
    if p.exists():b=b.merge(pd.read_csv(p),on='booking_id',validate='one_to_one')
    return b,s
@st.cache_data
def cached_hourly(signature,start,end,locations,services):
    b,s=cached_load(signature)
    return hourly_capacity(filter_data(b,start,end,locations,services),s,start,end,locations)
@st.cache_data
def scenarios(signature):
    out={}
    for name in SCENARIOS:
        p=ROOT/f'reports/scenarios/{name}_bookings.csv'
        if not p.exists():continue
        r=pd.read_csv(p);s=pd.read_csv(ROOT/f'reports/scenarios/{name}_shifts.csv')
        for c in ['created_at','assigned_at','start_at','completed_at','cancelled_at']:r[c]=pd.to_datetime(r[c])
        for c in ['start_at','end_at']:s[c]=pd.to_datetime(s[c])
        out[name]=(r,s)
    return out
p=ROOT/'reports/dispatch_diagnostics.csv';db=ROOT/'data/serviceops.db'
if not db.exists():st.error('Run python -m src.build from the project root.');st.stop()
signature=(db.stat().st_mtime_ns,p.stat().st_mtime_ns if p.exists() else 0)
b,s=cached_load(signature)
with st.sidebar:
    st.subheader('ServiceOps')
    page=st.radio('Workspace',['Executive Overview','Demand Intelligence','Workforce & Fulfillment','Revenue & Unit Economics'])
    st.divider();st.subheader('Reporting scope')
    dates=st.date_input('Request date range',(b.created_at.min().date(),b.created_at.max().date()),min_value=b.created_at.min().date(),max_value=b.created_at.max().date())
    locs=st.multiselect('Location',sorted(b.location.unique()),default=sorted(b.location.unique()))
    services=st.multiselect('Service category',sorted(b.service.unique()),default=sorted(b.service.unique()))
    st.caption('Asia/Kolkata · INR. Independent portfolio demonstration. All data is simulated; no company internal data.')
if len(dates)!=2:st.info('Select a start and end date.');st.stop()
d=filter_data(b,*dates,locs,services)
st.header(page);st.caption(f'SIMULATED DATA / {dates[0]:%d %b %Y} – {dates[1]:%d %b %Y} / {len(locs)} zones / {len(services)} services / INR')
st.sidebar.download_button('Download filtered bookings',export_csv(d),'serviceops_filtered.csv','text/csv',width='stretch')
if d.empty:st.info('No bookings match these filters. Adjust the selection.');st.stop()
k=kpis(d);cap=capacity(d,s,*dates,locs);zones=location_performance(d)
COLORS=['#41698a','#527b72','#343434','#94a3b8']
LABELS={'day':'Request date','month':'Request month','requested':'Requested','completed':'Completed','location':'Service zone','service':'Service category','revenue':'Revenue (INR)','margin':'Contribution (INR)','hour':'Hour of day (IST)','requests':'Requests','assignment_minutes':'Assignment delay (minutes)','fulfillment':'Fulfillment rate','service_utilization':'Service utilization','occupied_utilization':'Occupied utilization','value':'Bookings','variable':''}
def chart(fig,percent=False,currency=False):
    for trace in fig.data:
        old=trace.name
        if old in LABELS:
            trace.name=LABELS[old]
            if trace.hovertemplate:trace.hovertemplate=trace.hovertemplate.replace(old,LABELS[old])
    multi=len(fig.data)>1
    fig.update_layout(template='plotly_white',font=dict(family='Arial',size=12,color='#334155'),margin=dict(l=15,r=15,t=20,b=145 if len(fig.data)>2 else 100 if multi else 60),height=450 if len(fig.data)>2 else 390 if multi else 350,legend=dict(orientation='h',y=-.2,yanchor='top',x=0,title_text=''),paper_bgcolor='white',plot_bgcolor='white')
    if percent:fig.update_yaxes(tickformat='.0%',range=[0,1])
    if currency:fig.update_yaxes(tickprefix='₹',tickformat='~s')
    st.plotly_chart(fig,width='stretch',config={'displaylogo':False})
def cards(items):
    for i in range(0,len(items),2):
        for col,(label,value,helptext) in zip(st.columns(2,gap='medium'),items[i:i+2]):col.metric(label,value,help=helptext,border=False)
def location_table():
    st.dataframe(zones[['location','requested','completed','fulfillment','assignment_minutes','revenue','margin']],hide_index=True,width='stretch',column_config={'location':'Zone','requested':st.column_config.NumberColumn('Requests',format='%,d'),'completed':st.column_config.NumberColumn('Completed',format='%,d'),'fulfillment':st.column_config.NumberColumn('Fulfillment',format='percent'),'assignment_minutes':st.column_config.NumberColumn('Assignment min',format='%.1f'),'revenue':st.column_config.NumberColumn('Revenue INR',format='%,.0f'),'margin':st.column_config.NumberColumn('Contribution INR',format='%,.0f')})
def hourly_view():
    h=cached_hourly(signature,*dates,tuple(locs),tuple(services));h['hour']=h.period.dt.hour
    names={'available_minutes':'Available shift hours','occupied_minutes':'Occupied reservation hours','service_minutes':'Completed service hours','request_workload_minutes':'Incoming expected workload'}
    profile=h.groupby('hour')[list(names)].sum().reset_index();days=(pd.Timestamp(dates[1])-pd.Timestamp(dates[0])).days+1
    profile[list(names)]/=60*days
    chart(px.line(profile.rename(columns=names),x='hour',y=list(names.values()),labels={'hour':'Hour of day (IST)','value':'Worker-hours per calendar day','variable':''},color_discrete_sequence=['#343434','#527b72','#41698a','#94a3b8']))
    st.caption('Incoming workload places expected service duration in the request arrival hour; it is not simultaneous occupancy. Available and occupied hours use exact interval overlaps. Capacity stays shared across categories. Zero-demand days remain in the daily average.')
    st.download_button('Download hourly capacity',export_csv(h),'hourly_capacity.csv','text/csv')
    return h
if page=='Executive Overview':
    cards([('Requested',f"{k['requested']:,}",'All requests created in selected dates.'),('Completed',f"{k['completed']:,}",'Final completed status.'),('Fulfillment',f"{k['fulfillment']:.1%}",'Completed / requested.'),('Cancellation',f"{k['cancellation']:.1%}",'Cancelled / requested.')])
    st.subheader('Operational findings');weak=zones.loc[zones.fulfillment.idxmin()];peak=d.groupby('hour').size()
    with st.container(border=False):
        st.write(f'**{weak.location}** has the lowest selected fulfillment at **{weak.fulfillment:.1%}** across **{weak.requested:,.0f} requests**. Peak demand arrives at **{peak.idxmax():02d}:00**, with **{peak.max():,} requests**.')
        if 'failure_diagnostic' in d:
            boundary=d.failure_diagnostic.eq('Shift window / duration').sum();contention=d.failure_diagnostic.eq('Reservation contention').sum()
            st.write(f'Of {boundary+contention:,} dispatch failures, {boundary:,} cannot fit even on empty scheduled shifts. {contention:,} encounter reservations despite a feasible empty-schedule slot. The counts come from the dispatch simulation.')
    st.subheader('Request and completion trend');chart(px.line(summary(d,'day'),x='day',y=['requested','completed'],labels=LABELS,color_discrete_sequence=COLORS))
    st.subheader('Location performance');chart(px.bar(zones.sort_values('fulfillment'),x='location',y='fulfillment',text_auto='.1%',labels=LABELS,color_discrete_sequence=COLORS),percent=True);location_table()
    with st.expander('Status mix and commercial summary'):
        cards([('Realized revenue',f"₹{k['revenue']:,.0f}",'Completed charges in selected request cohort.'),('Average completed value',f"₹{k['abv']:,.2f}",'Revenue / completed.'),('Accepted',f"{k['accepted']:,}",'Assigned at least once, including later cancellations.')])
        chart(px.pie(d.groupby('status').size().reset_index(name='bookings'),names='status',values='bookings',hole=.65,color_discrete_sequence=COLORS))
elif page=='Demand Intelligence':
    st.subheader('Hourly workload and shift capacity');hourly_view()
    st.subheader('When requests arrive')
    heat=d.pivot_table(index='weekday',columns='hour',values='booking_id',aggfunc='count',fill_value=0).reindex(index=range(7),columns=range(7,21),fill_value=0);heat.index=['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
    chart(px.imshow(heat,color_continuous_scale='Blues',aspect='auto',labels={'x':'Request hour (IST)','y':'Weekday','color':'Requests'}))
    with st.expander('Weekday demand and service mix'):
        week=d.groupby('weekday').size().reindex(range(7),fill_value=0).reset_index(name='requests');week['day']=['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
        chart(px.bar(week,x='day',y='requests',labels={'day':'Weekday','requests':'Requests'},color_discrete_sequence=COLORS))
        chart(px.bar(d.groupby(['location','service']).size().reset_index(name='requests'),x='location',y='requests',color='service',labels=LABELS,color_discrete_sequence=COLORS))
        st.dataframe(cap[['location','requested_minutes','available_minutes','aggregate_gap_minutes']],hide_index=True,width='stretch')
elif page=='Workforce & Fulfillment':
    h=cached_hourly(signature,*dates,tuple(locs),tuple(services));available=h.available_minutes.sum()
    cards([('Service utilization',f'{h.service_minutes.sum()/available:.1%}' if available else 'N/A','Completed service minutes / shared shift minutes.'),('Occupied utilization',f'{h.occupied_minutes.sum()/available:.1%}' if available else 'N/A','Reservation through terminal event plus turnaround / shift minutes.'),('Mean assignment delay',f"{k['assignment_minutes']:.1f} min",'Accepted requests including later cancellations.'),('Shared shift hours',f'{available/60:,.0f}','All date/zone shifts, shared across categories.')])
    st.subheader('Workforce use by zone');z=h.groupby('location')[['available_minutes','service_minutes','occupied_minutes']].sum().reset_index()
    for c in ['service','occupied']:z[c+'_utilization']=z[c+'_minutes']/z.available_minutes.replace(0,float('nan'))
    chart(px.bar(z,x='location',y=['service_utilization','occupied_utilization'],barmode='group',labels=LABELS|{'value':'Utilization'},color_discrete_sequence=COLORS),percent=True)
    st.subheader('Why requests were cancelled');r=d[d.status.eq('cancelled')].groupby('cancellation_reason').size().reset_index(name='bookings');r['share_of_cancellations']=r.bookings/r.bookings.sum()
    r['reason']=r.cancellation_reason.map({'Customer changed plans':'Customer plans','Customer cancelled after assignment':'After acceptance','No capacity within 45 minutes':'Dispatch failure'})
    chart(px.bar(r,x='reason',y='bookings',text='bookings',labels={'reason':'Cancellation reason','bookings':'Cancelled bookings'},color_discrete_sequence=COLORS))
    st.dataframe(r.drop(columns='reason'),hide_index=True,column_config={'cancellation_reason':'Reason','bookings':st.column_config.NumberColumn('Bookings',format='%,d'),'share_of_cancellations':st.column_config.NumberColumn('Share of cancellations',format='percent')})
    with st.expander('Dispatch diagnostics and assignment delays'):
        if 'failure_diagnostic' in d:st.dataframe(d.groupby(['failure_diagnostic','hour']).size().reset_index(name='failed_requests'),hide_index=True)
        chart(px.histogram(d.dropna(subset=['assignment_minutes']),x='assignment_minutes',nbins=25,labels=LABELS,color_discrete_sequence=COLORS))
        st.write(f'Mean completed service duration: {d.service_minutes.mean():.1f} minutes. Worker imbalance partly reflects the dispatch tie-break rule.')
    with st.expander('Hypothetical shift schedules · dispatch rerun'):
        st.caption('Same requests, latent durations, attendance days and paired cancellation propensities. Current filters apply to every replay. Hypothetical outcomes, not forecasts or wage savings.')
        rows=[]
        for name,(r,sh) in scenarios(signature).items():
            r=filter_data(r,*dates,locs,services);v=kpis(r);c=capacity(r,sh,*dates,locs);a=c.available_minutes.sum()
            rows.append({'Schedule':name,'Requests':v['requested'],'Completed':v['completed'],'Fulfillment':v['fulfillment'],'Shift hours':a/60,'Service utilization':r.service_minutes.sum()/a if a else None,'Boundary failures':int(r.failure_diagnostic.eq('Shift window / duration').sum()),'Contention failures':int(r.failure_diagnostic.eq('Reservation contention').sum())})
        st.dataframe(pd.DataFrame(rows),hide_index=True,column_config={'Fulfillment':st.column_config.NumberColumn(format='percent'),'Service utilization':st.column_config.NumberColumn(format='percent'),'Shift hours':st.column_config.NumberColumn(format='%,.0f')})
        for name,assumption in SCENARIOS.items():st.write(f'**{name}:** {assumption}')
        st.caption('Lean split tests removal of midday coverage. Unobserved cancellation propensities for previously unassigned requests use a separate deterministic seed. No schedule was optimized.')
else:
    cards([('Revenue',f"₹{k['revenue']:,.0f}",'Completed charges in selected creation cohort.'),('Attributable service costs',f"₹{k['revenue']-k['contribution_margin']:,.0f}",'Payouts, materials and processing, including accepted cancellations.'),('Contribution',f"₹{k['contribution_margin']:,.0f}",'Before fixed costs and guaranteed wages.'),('Average completed value',f"₹{k['abv']:,.2f}",'Revenue / completed bookings.')])
    st.subheader('Revenue and contribution trend');chart(px.line(summary(d,'month'),x='month',y=['revenue','margin'],labels=LABELS|{'value':'INR'},color_discrete_sequence=COLORS),currency=True)
    st.subheader('Service economics');chart(px.bar(summary(d,'service'),x='service',y=['revenue','margin'],barmode='group',labels=LABELS|{'value':'INR'},color_discrete_sequence=COLORS),currency=True)
    st.subheader('Location economics');location_table();weak=zones.loc[zones.margin.idxmin()]
    st.info(f'{weak.location} contributes ₹{weak.margin:,.0f} on {weak.requested:,.0f} requests. Review volume, completion and service mix together. Shift-hour reductions are not wage savings in this per-service payout model.')
with st.expander('Definitions, assumptions and simulation limits'):
    st.write('Requested = created in selected dates. Accepted = assigned at least once. Completed and cancelled are exclusive final statuses. Fulfillment = completed / requested. ABV = revenue / completed. Revenue belongs to the request cohort, not a completion-date ledger. Partial months are not annualized.')
    st.write('Service utilization counts completed service. Occupied utilization includes assignment-to-start travel, accepted cancellations and ten-minute turnaround, clipped to shift end. Pre-assignment wait is not occupied. Shared shift capacity uses selected dates/zones and is not allocated to service categories. Zero-capacity utilization is undefined (N/A).')
    st.write('Assumptions: 108 workers, 81% daily attendance, equal worker counts per zone, 8-hour shifts, all workers eligible for all services. No cross-zone dispatch. Services must fit before shift end and be assigned within 45 minutes. The baseline has ample aggregate supply and is not a calibrated staffing recommendation.')
    st.write('Limits: fixed ten-minute travel proxies, no explicit breaks, routing, advance booking, skill constraints, guaranteed wages, taxes, refunds or overhead. Demand peaks and cancellation propensities are inputs. Diagnostic and scenario findings describe the simulation and need real-world validation.')
