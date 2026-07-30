import csv
import io
import pandas as pd
from datetime import datetime, timedelta
from src.infrastructure.database.models import Vendor, VendorComplianceStatus, FraudCheck, VendorDocument, VendorActivity, GeneratedReport, db
import logging

class ReportService:
    """Enterprise Report Generator Service assembling datasets and formatting CSV/Excel/HTML outputs."""
    
    @staticmethod
    def generate_report(report_type: str, export_format: str, generated_by: str = 'System') -> tuple:
        """Assembles data, stores a GeneratedReport log entry, and returns (file_content, mime_type, filename)."""
        try:
            # 1. Fetch raw dataset based on report type
            df, title = ReportService._get_report_data(report_type)
            
            filename = f"{report_type.lower().replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            
            # 2. Export to target format
            if export_format.upper() == 'CSV':
                content = df.to_csv(index=False)
                mime_type = "text/csv"
                filename += ".csv"
            elif export_format.upper() == 'EXCEL':
                # Use Pandas ExcelWriter with try-except fallback to CSV if openpyxl isn't installed
                try:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, sheet_name='Report', index=False)
                    content = output.getvalue()
                    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    filename += ".xlsx"
                except Exception as ex:
                    logging.warning(f"Excel generation failed, falling back to CSV: {str(ex)}")
                    content = df.to_csv(index=False).encode('utf-8')
                    mime_type = "text/csv"
                    filename += ".csv"
            elif export_format.upper() == 'PDF':
                content = ReportService._generate_printable_pdf(title, df, report_type)
                mime_type = "application/pdf"
                filename += ".pdf"
            elif export_format.upper() in ['HTML', 'PRINTABLE HTML']:
                content = ReportService._generate_printable_html(title, df, report_type)
                mime_type = "text/html"
                filename += ".html"
            else:
                raise ValueError(f"Unsupported format: {export_format}")
            
            # 3. Log report completion
            status = 'Completed'
            gen_rep = GeneratedReport(
                report_type=report_type,
                export_format=export_format,
                filename=filename,
                generated_by=generated_by,
                status=status
            )
            db.session.add(gen_rep)
            db.session.commit()
            
            return content, mime_type, filename
        except Exception as e:
            db.session.rollback()
            logging.error(f"Report generation failure: {str(e)}")
            # Log failure in database
            try:
                fail_rep = GeneratedReport(
                    report_type=report_type,
                    export_format=export_format,
                    filename=f"failed_{report_type.lower().replace(' ', '_')}",
                    generated_by=generated_by,
                    status='Failed'
                )
                db.session.add(fail_rep)
                db.session.commit()
            except Exception:
                pass
            raise e

    @staticmethod
    def _get_report_data(report_type: str) -> tuple:
        """Assembles dataframes matching the selected report type with bulk-fetched pre-cached relations."""
        vendors = Vendor.query.all()
        now = datetime.utcnow()
        
        # Pre-fetch lookup maps to eliminate N+1 query loops completely
        comp_map = {c.vendor_id: c for c in VendorComplianceStatus.query.all()}
        fraud_map = {f.vendor_id: f for f in FraudCheck.query.all()}
        docs_list = VendorDocument.query.filter_by(is_deleted=False).all()
        docs_map = {}
        for d in docs_list:
            docs_map.setdefault(d.vendor_id, []).append(d)
        
        data = []
        title = report_type
        
        if report_type in ['Vendor Summary', 'Executive Summary']:
            title = "Vendor Telemetry Executive Summary"
            for v in vendors:
                comp = comp_map.get(v.id)
                fraud = fraud_map.get(v.id)
                data.append({
                    'Vendor ID': v.id,
                    'Business Name': v.name,
                    'Trust Score': v.trust_score,
                    'Quality Rating': v.quality_rating,
                    'Status': v.status,
                    'Compliance Score': comp.compliance_score if comp else 85.0,
                    'Fraud Score': fraud.fraud_score if fraud else 0.0
                })
            df = pd.DataFrame(data)
            
        elif report_type == 'Vendor Quality Report':
            title = "Vendor Performance & Quality Audit"
            for v in vendors:
                data.append({
                    'Vendor ID': v.id,
                    'Business Name': v.name,
                    'Quality Rating': v.quality_rating,
                    'Category': v.category,
                    'Operational Status': v.status
                })
            df = pd.DataFrame(data)
            
        elif report_type == 'Trust Report':
            title = "Unified Trust Index Analytics"
            for v in vendors:
                data.append({
                    'Vendor ID': v.id,
                    'Business Name': v.name,
                    'Trust Score': v.trust_score,
                    'Trust Level': v.trust_level,
                    'Address': v.address
                })
            df = pd.DataFrame(data)
            
        elif report_type == 'Risk Report':
            title = "Predictive Risk & Security Assessment"
            for v in vendors:
                fraud = fraud_map.get(v.id)
                f_score = fraud.fraud_score if fraud else 0.0
                risk_score = max(5.0, 100.0 - v.trust_score)
                data.append({
                    'Vendor ID': v.id,
                    'Business Name': v.name,
                    'Risk Score': risk_score,
                    'Risk Level': v.trust_level,
                    'Fraud Score': f_score
                })
            df = pd.DataFrame(data)
            
        elif report_type == 'Compliance Report':
            title = "Regulatory Compliance Audit"
            for v in vendors:
                comp = comp_map.get(v.id)
                v_docs = docs_map.get(v.id, [])
                expired = len([d for d in v_docs if d.expiry_date and d.expiry_date < now])
                data.append({
                    'Vendor ID': v.id,
                    'Business Name': v.name,
                    'Compliance Score': comp.compliance_score if comp else 85.0,
                    'Approval Status': comp.approval_status if comp else 'Pending',
                    'Total Uploaded Docs': len(v_docs),
                    'Expired Docs': expired
                })
            df = pd.DataFrame(data)
            
        elif report_type == 'Fraud Report':
            title = "Fraud Threat & Overlapping Clusters"
            for v in vendors:
                fraud = fraud_map.get(v.id)
                data.append({
                    'Vendor ID': v.id,
                    'Business Name': v.name,
                    'Fraud Score': fraud.fraud_score if fraud else 0.0,
                    'Threat Status': fraud.status if fraud else 'Clear',
                    'Root Cause': fraud.root_cause if fraud else 'None'
                })
            df = pd.DataFrame(data)
            
        elif report_type == 'Executive Dashboard Report':
            title = "Executive Summary KPIs"
            total = len(vendors)
            avg_trust = sum(v.trust_score for v in vendors) / total if total > 0 else 0.0
            active_alerts = FraudCheck.query.filter_by(status='Alert').count()
            expired_docs = VendorDocument.query.filter(VendorDocument.expiry_date < now, VendorDocument.is_deleted == False).count()
            
            data.append({'Metric': 'Total Vendors', 'Value': total})
            data.append({'Metric': 'Average Trust Score', 'Value': round(avg_trust, 2)})
            data.append({'Metric': 'Active Fraud Warnings', 'Value': active_alerts})
            data.append({'Metric': 'Expired Compliance Credentials', 'Value': expired_docs})
            df = pd.DataFrame(data)
            
        elif report_type == 'Monthly Report':
            title = f"Operational Activity Logs - {now.strftime('%B %Y')}"
            start_date = now - timedelta(days=30)
            activities = VendorActivity.query.filter(VendorActivity.timestamp >= start_date).all()
            for act in activities:
                data.append({
                    'Timestamp': act.timestamp.strftime('%Y-%m-%d %H:%M'),
                    'Vendor ID': act.vendor_id,
                    'Activity Type': act.activity_type,
                    'Description': act.description,
                    'Operator': act.performed_by
                })
            df = pd.DataFrame(data) if data else pd.DataFrame(columns=['Timestamp', 'Vendor ID', 'Activity', 'Description', 'Operator'])
            
        elif report_type == 'Yearly Report':
            title = f"Annual Platform Telemetry - Year {now.strftime('%Y')}"
            start_date = now - timedelta(days=365)
            for v in vendors:
                comp = VendorComplianceStatus.query.filter_by(vendor_id=v.id).first()
                data.append({
                    'Vendor ID': v.id,
                    'Business Name': v.name,
                    'Trust Index': v.trust_score,
                    'Compliance rate': comp.compliance_score if comp else 85.0,
                    'Registration Date': v.created_at.strftime('%Y-%m-%d')
                })
            df = pd.DataFrame(data)
            
        elif report_type == 'Vendor Health Report':
            title = "Vendor Overall Health Index Analysis"
            from src.domain.services.health_engine import HealthEngine
            for v in vendors:
                health_res = HealthEngine.calculate_health(v.id)
                h_score = health_res.get('health_score', 50.0) if health_res.get('success') else 50.0
                h_cat = health_res.get('category', 'Average') if health_res.get('success') else 'Average'
                data.append({
                    'Vendor ID': v.id,
                    'Business Name': v.name,
                    'Health Score': h_score,
                    'Health Category': h_cat,
                    'Trust Component': v.trust_score,
                    'Quality Component': v.quality_rating
                })
            df = pd.DataFrame(data)
            
        else:
            raise ValueError(f"Unknown report type: {report_type}")
            
        return df, title

    @staticmethod
    def _generate_printable_html(title: str, df: pd.DataFrame, report_type: str) -> str:
        """Assembles a print-optimized, modern styled HTML report page."""
        rows_html = ""
        columns = df.columns
        
        # Build headers
        headers_html = "".join([f"<th>{col}</th>" for col in columns])
        
        # Build rows
        for _, row in df.iterrows():
            cells = "".join([f"<td>{row[col]}</td>" for col in columns])
            rows_html += f"<tr>{cells}</tr>"
            
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            color: #333;
            margin: 40px;
            background: #fff;
        }}
        .header-container {{
            border-bottom: 3px solid #00f2fe;
            padding-bottom: 20px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        h1 {{
            font-size: 24px;
            margin: 0;
            color: #0b0f19;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .meta-info {{
            font-size: 12px;
            color: #777;
            text-align: right;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th {{
            background-color: #0b0f19;
            color: #fff;
            text-align: left;
            padding: 10px;
            font-size: 13px;
            text-transform: uppercase;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
            font-size: 13px;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .print-btn {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: #00f2fe;
            color: #0b0f19;
            border: none;
            padding: 8px 16px;
            font-size: 12px;
            font-weight: bold;
            border-radius: 4px;
            cursor: pointer;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        @media print {{
            .print-btn {{
                display: none;
            }}
            body {{
                margin: 0;
            }}
        }}
    </style>
</head>
<body>
    <button class="print-btn" onclick="window.print()">Print Report / Save PDF</button>
    <div class="header-container">
        <div>
            <h1>{title}</h1>
            <span style="font-size: 12px; color: #555;">Report Category: {report_type}</span>
        </div>
        <div class="meta-info">
            <div>Generated At: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</div>
            <div>Generated By: Enterprise Dashboard System</div>
        </div>
    </div>
    <table>
        <thead>
            <tr>{headers_html}</tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
</body>
</html>"""
        return html

    @staticmethod
    def _generate_printable_pdf(title: str, df: pd.DataFrame, report_type: str) -> bytes:
        """Assembles a clean, professional print-ready PDF using ReportLab."""
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#0b0f19'),
            spaceAfter=6
        )
        
        meta_style = ParagraphStyle(
            'ReportMeta',
            parent=styles['Normal'],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#555555'),
            spaceAfter=15
        )
        
        cell_style = ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontSize=7,
            leading=9,
            textColor=colors.HexColor('#333333')
        )
        
        header_cell_style = ParagraphStyle(
            'TableHeaderCell',
            parent=styles['Normal'],
            fontSize=7,
            leading=9,
            textColor=colors.white,
            fontName='Helvetica-Bold'
        )

        elements = []
        
        # Add Title & Subtitle
        elements.append(Paragraph(title, title_style))
        elements.append(Paragraph(f"Category: {report_type} | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC", meta_style))
        elements.append(Spacer(1, 10))
        
        # Prepare table data
        columns = list(df.columns)
        table_data = []
        
        # Header row
        table_data.append([Paragraph(str(col), header_cell_style) for col in columns])
        
        # Content rows
        for _, row in df.iterrows():
            row_cells = []
            for col in columns:
                row_cells.append(Paragraph(str(row[col]), cell_style))
            table_data.append(row_cells)
            
        # Determine column widths
        col_count = len(columns)
        col_width = (612 - 72) / col_count if col_count > 0 else 100 # letter width is 612pt
        
        t = Table(table_data, colWidths=[col_width] * col_count)
        
        # Modern table styling
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0b0f19')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f9f9f9'), colors.white]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ]))
        
        elements.append(t)
        doc.build(elements)
        
        return buffer.getvalue()
