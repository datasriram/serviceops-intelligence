"""Portable local refresh of the delivered Excel snapshot from calculated summaries."""
import json
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
from src.analytics import ROOT
def export():
    data=json.loads((ROOT/'reports/workbook_data.json').read_text());w=Workbook();w.remove(w.active)
    for name,d in data.items():
        s=w.create_sheet(name);s.sheet_view.showGridLines=False
        s.append([name+' performance']);s.append(['SIMULATED | 2025 | Asia/Kolkata | INR']);s.append([]);s.append(d['columns'])
        for row in d['rows']:s.append(row)
        for c in s[4]:c.fill=PatternFill('solid',fgColor='353535');c.font=Font(name='Calibri',bold=True,color='FFFFFF')
        for row in s.iter_rows(min_row=5):
            for c in row:c.font=Font(name='Calibri',size=11);c.number_format='#,##0.0' if isinstance(c.value,(float,int)) else 'General'
        for col in s.columns:s.column_dimensions[col[0].column_letter].width=22
        s.row_dimensions[4].height=36
        for c in s[4]:c.alignment=Alignment(wrap_text=True)
        for j,key in enumerate(d['columns'],1):
            for r in range(5,s.max_row+1):
                cell=s.cell(r,j)
                if key in ['fulfillment','utilization','service_utilization','occupied_utilization']:cell.number_format='0.0%'
                elif key in ['revenue','cost','materials','processing','margin']:cell.number_format='"₹"#,##0.00'
                elif key in ['requested','completed','accepted','worker_id','hour','shifts','boundary_cancellations','contention_cancellations']:cell.number_format='#,##0'
        if name=='Definitions':
            s.column_dimensions['B'].width=100
            s.column_dimensions['A'].width=26
            for row in s.iter_rows(min_row=5):s.row_dimensions[row[0].row].height=56;row[1].alignment=Alignment(wrap_text=True)
        else:s.freeze_panes='A5';s.auto_filter.ref=f'A4:{s.cell(s.max_row,len(d["columns"])).coordinate}'
        if name in ['Monthly','Locations','Services']:
            for j,label in enumerate(['Fulfillment','Cancellation','ABV INR'],11):s.cell(4,j,label)._style=s.cell(4,10)._style; s.column_dimensions[s.cell(4,j).column_letter].width=22
            for r in range(5,s.max_row+1):
                s.cell(r,11,f'=IF(B{r}=0,0,C{r}/B{r})').number_format='0.0%'
                s.cell(r,12,f'=IF(B{r}=0,0,(B{r}-C{r})/B{r})').number_format='0.0%'
                s.cell(r,13,f'=IF(C{r}=0,0,E{r}/C{r})').number_format='"₹"#,##0.00'
        if name=='Hourly capacity':
            for r in range(5,s.max_row+1):
                s.cell(r,8,f'=IF(C{r}=0,"",D{r}/C{r})').number_format='0.0%'
                s.cell(r,9,f'=IF(C{r}=0,"",E{r}/C{r})').number_format='0.0%'
        if name=='Scenarios':
            for r in range(5,s.max_row+1):s.cell(r,4,f'=IF(B{r}=0,"",C{r}/B{r})').number_format='0.0%'
    w.save(ROOT/'reports/serviceops_operations.xlsx')
if __name__=='__main__':export()
