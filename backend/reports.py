import csv
import io
from html import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak


def export_csv(scenario):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(['Syntrix scenario report', safe_cell(scenario['config']['name'])])
    writer.writerow(['Model', 'Synthetic data; aggregate equivalent units; currency INR'])
    selected = next((p['name'] for p in scenario['plans'] if p['id'] == scenario.get('selected_plan')), 'Not selected')
    writer.writerow(['Selected recovery plan', selected])
    writer.writerow(['Strategy', 'Service level %', 'Unmet demand', 'Recovery days', 'Recovery cost INR', 'Feasible'])
    rows = [('Undisrupted baseline', scenario['baseline']['kpis'], True), ('Disrupted baseline', scenario['disrupted']['kpis'], True)]
    rows += [(p['name'], p['result']['kpis'], p['feasibility']['feasible']) for p in scenario['plans']]
    for name, k, feasible in rows:
        writer.writerow([name, k['service_level'], k['unmet_demand'], k['recovery_days'] if k['recovery_days'] is not None else 'Not recovered', k['recovery_cost'], feasible])
    writer.writerow([])
    writer.writerow(['Daily disrupted baseline'])
    writer.writerow(['Day', 'Service level %', 'Inventory', 'Backlog', 'Production', 'In transit', 'Recovery cost INR'])
    for day in scenario['disrupted']['daily']:
        writer.writerow([day[key] for key in ['day', 'service_level', 'inventory', 'backlog', 'production', 'in_transit', 'recovery_cost']])
    return stream.getvalue().encode('utf-8-sig')


def safe_cell(value):
    return "'"+value if value and value[0] in '=+-@\t\r' else value


def export_pdf(scenario):
    stream = io.BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=(210*mm, 297*mm), rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Brand', fontName='Helvetica-Bold', fontSize=24, spaceAfter=14, textColor=colors.HexColor('#111827')))
    styles.add(ParagraphStyle(name='Caption2', fontName='Helvetica', fontSize=9, leading=13, textColor=colors.HexColor('#475569'), spaceAfter=10))
    story = [Paragraph('SYNTRIX', styles['Brand']), Paragraph('RESILIENCE & RECOVERY / SCENARIO REPORT', styles['Caption2']),
             Paragraph(escape(scenario['config']['name']), styles['Heading1']),
             Paragraph(f"Synthetic network | {scenario['config']['horizon']}-day horizon | All costs in INR", styles['Caption2'])]
    for d in scenario['config']['disruptions']:
        story.append(Paragraph(f"{escape(d['type'].replace('_', ' ').title())}: {escape(d['target'])}, day {d['start_day']}, {d['duration']} days, {d['severity']}% severity.", styles['BodyText']))
    selected = next((p['name'] for p in scenario['plans'] if p['id'] == scenario.get('selected_plan')), None)
    if selected:
        story.extend([Spacer(1, 4*mm), Paragraph('Selected recovery plan: ' + escape(selected), styles['BodyText'])])
    story.extend([Spacer(1, 8*mm), Paragraph('Executive outcomes', styles['Heading2'])])
    data = [['Strategy', 'Service', 'Unmet units', 'Recovery', 'Cost (INR)']]
    rows = [('Undisrupted', scenario['baseline']['kpis']), ('Disrupted baseline', scenario['disrupted']['kpis'])]
    rows += [(p['name'], p['result']['kpis']) for p in scenario['plans']]
    for name, k in rows:
        data.append([Paragraph(name, styles['Caption2']), f"{k['service_level']:.1f}%", f"{k['unmet_demand']:,.0f}", f"{k['recovery_days']} days" if k['recovery_days'] is not None else 'Not reached', f"{k['recovery_cost']:,.0f}"])
    table = Table(data, colWidths=[54*mm, 26*mm, 30*mm, 30*mm, 34*mm], repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#111827')), ('TEXTCOLOR',(0,0),(-1,0),colors.white), ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'), ('FONTSIZE',(0,0),(-1,-1),9), ('VALIGN',(0,0),(-1,-1),'TOP'), ('TOPPADDING',(0,0),(-1,-1),9), ('BOTTOMPADDING',(0,0),(-1,-1),9), ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f1f5f9'),colors.white]), ('LINEBELOW',(0,0),(-1,0),1,colors.HexColor('#f59e0b'))]))
    story.extend([table, Spacer(1, 6*mm), Paragraph('Impact & interpretation', styles['Heading2']),
                  Paragraph(f"{len(scenario['impact']['affected_nodes'])} structurally exposed nodes; {scenario['impact']['affected_customers']} customer locations; {scenario['impact']['daily_demand_exposed']} units of exposed daily demand. Exposure is not the same as realized loss.", styles['BodyText']),
                  Spacer(1, 5*mm), Paragraph('Modelling boundaries', styles['Heading2']),
                  Paragraph('Deterministic aggregate-equivalent units with 1:1 production conversion, finite inventory, node/lane capacity and whole-day transit times. The product/BOM catalogue is descriptive, not a per-SKU production model. A steady-state initial shipment pipeline is included. Recovery cost is contracted commitment. Reserve stock and expedited supplier capacity are constrained. These are synthetic planning results, not live operational forecasts.', styles['Caption2']),
                  Paragraph(f"Recovery: service at least {scenario['config']['recovery_threshold']}% for {scenario['config']['consecutive_days']} consecutive days after the final service deterioration. No observed deterioration = 0 days; horizon exhausted = not reached.", styles['Caption2'])])
    if scenario['plans']:
        story.extend([PageBreak(), Paragraph('Recovery action register', styles['Brand'])])
        for plan in scenario['plans']:
            story.append(Paragraph(escape(plan['name']), styles['Heading2']))
            story.append(Paragraph(f"{escape(plan['method'])} | {'Feasible' if plan['feasibility']['feasible'] else 'Infeasible'} | {'Pareto-efficient' if plan.get('pareto') else 'Dominated trade-off'}", styles['Caption2']))
            for action in plan['actions']:
                story.append(Paragraph(escape(action['description'])+f". Committed cost: INR {action['cost']:,.0f}.", styles['BodyText']))
            if not plan['actions']:
                story.append(Paragraph('No additional physical allocation. See order policy or route feasibility constraints.', styles['Caption2']))
            for line in plan['solver_log']:
                story.append(Paragraph(escape(line), styles['Caption2']))
    def footer(canvas, document):
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.drawString(18*mm, 12*mm, 'SYNTRIX / Synthetic planning workspace')
        canvas.drawRightString(192*mm, 12*mm, f'{document.page}')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()
