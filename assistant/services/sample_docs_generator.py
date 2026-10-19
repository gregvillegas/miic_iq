import os
from pathlib import Path
import docx
import openpyxl
from pypdf import PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def create_sample_docs():
    """Generates realistic sample enterprise documents in DOCX, PDF, MD, and XLSX."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    docs_dir = base_dir / 'sample_documents'
    docs_dir.mkdir(exist_ok=True)

    # 1. Sales Order Workflow SOP (.docx)
    docx_path = docs_dir / 'SO_Process_Workflow_SOP_v2.docx'
    doc = docx.Document()
    doc.add_heading('MIIC Standard Operating Procedure: Sales Order (SO) Fulfillment Workflow', level=0)
    doc.add_paragraph('Document ID: SOP-SALES-2026-004 | Version: 2.3 | Effective Date: January 1, 2026')
    doc.add_paragraph('Owner: Sales Operations & Commercial Excellence | Classification: Internal Use Only')
    
    doc.add_heading('1. Overview & Purpose', level=1)
    doc.add_paragraph(
        'This Standard Operating Procedure governs the complete lifecycle of Sales Orders (SO) from customer inquiry '
        'to final delivery and invoicing. Adherence to this workflow is mandatory for all Sales Representatives, '
        'Account Executives, Sales Operations Specialists, and Finance personnel.'
    )

    doc.add_heading('2. Step-by-Step Sales Order Procedure', level=1)
    doc.add_paragraph(
        'Step 1: Quotation Generation & Customer PO\n'
        'The Account Executive prepares the official price quotation in the CRM. Upon customer agreement, an official '
        'Customer Purchase Order (PO) with signed terms must be obtained.'
    )
    doc.add_paragraph(
        'Step 2: Credit Check & Verification\n'
        'For orders exceeding $10,000 or new clients, Finance must conduct a credit check within 4 business hours. '
        'Credit limit overrides require written approval from the Credit Controller.'
    )
    doc.add_paragraph(
        'Step 3: SO Creation in ERP (System Code: SO-101)\n'
        'Sales Operations creates the Sales Order in the ERP system under transaction code SO-101. '
        'Required fields include: Customer Account ID, Billing/Shipping Address, Incoterms (default DDP for domestic, FOB for international), '
        'and confirmed line items with part numbers.'
    )
    doc.add_paragraph(
        'Step 4: Management Approval Thresholds\n'
        '• Orders up to $25,000: Auto-approved upon valid PO upload\n'
        '• Orders $25,001 - $100,000: Sales Director approval required\n'
        '• Orders > $100,000: Vice President of Sales and CFO co-approval required'
    )
    doc.add_paragraph(
        'Step 5: Warehouse Allocation, Picking & Packing\n'
        'Once approved, the ERP automatically generates a Warehouse Pick List (WPL). The logistics team retrieves items '
        'within 24 hours and issues a Delivery Order (DO) with packing slip.'
    )
    doc.add_paragraph(
        'Step 6: Dispatch & Logistics Tracking\n'
        'Carrier tracking number is attached to the SO record. Customer receives automated dispatch notification with SLA estimated arrival.'
    )
    doc.add_paragraph(
        'Step 7: Delivery Confirmation & Invoicing\n'
        'Upon signed Proof of Delivery (POD) upload, Finance triggers the tax invoice (Net 30 payment terms by default).'
    )

    doc.add_heading('3. Exceptions & Expedited Orders', level=1)
    doc.add_paragraph(
        'Emergency rush orders requiring same-day dispatch must carry the "RUSH-PRIORITY" tag in SO-101 and incur a $150 '
        'handling surcharge. Must be logged before 11:30 AM local warehouse time.'
    )
    doc.save(str(docx_path))

    # 2. Markdown IT Security Policy (.md)
    md_path = docs_dir / 'IT_Security_and_Acceptable_Use_Policy.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("""# MIIC Corporate IT Security & Acceptable Use Policy
**Document Ref:** POL-IT-2026-01  
**Version:** 3.1  
**Effective Date:** February 1, 2026  
**Applicability:** All Full-Time, Part-Time Employees, and Contractors  

---

## 1. Authentication & Password Standards
- **Minimum Length:** Passwords must be at least 14 characters in length.
- **Complexity:** Must contain at least one uppercase letter, one lowercase letter, one number, and one special symbol.
- **Two-Factor Authentication (2FA):** Mandatory for all corporate Google Workspace, VPN, ERP, and GitHub accounts using an approved authenticator app (1Password, Google Authenticator, or YubiKey). SMS-based 2FA is prohibited.
- **Password Rotation:** Rotation is only enforced upon suspected compromise or every 365 days.

## 2. Remote Work & Device Security
- Company data must never be saved onto unencrypted personal devices (BYOD).
- Full disk encryption (FileVault for macOS, BitLocker for Windows) must remain enabled at all times.
- Connecting to public Wi-Fi without the corporate WireGuard/Tailscale VPN active is strictly forbidden.
- Screen timeout must be locked after a maximum of 5 minutes of inactivity.

## 3. Removable Media & USB Restrictions
- Direct writing to unauthorized external USB drives is blocked by Endpoint Management.
- If data transfer via USB is required for client air-gapped environments, submit a ticket to `it-security@company.com` for a pre-encrypted corporate hardware drive.

## 4. Phishing & Security Incident Reporting
- If you receive a suspicious email, do not click any links or download attachments.
- Click the **"Report Phishing"** button in Gmail or forward the raw headers to `soc@company.com`.
- In the event of a lost device or ransomware alert, immediately call the Emergency IT Incident Hotline at **+1 (800) 555-0199** available 24/7.
""")

    # 3. Excel Sales Discount & Approval Matrix (.xlsx)
    xlsx_path = docs_dir / 'Sales_Discount_Matrix_and_Payment_Terms.xlsx'
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Discount Approval Matrix"
    
    headers = ["Discount Percentage Range", "Minimum Order Value", "Required Approver Role", "Standard SLA", "Documentation Required"]
    ws.append(headers)
    ws.append(["0% - 5.0%", "Any value", "Account Executive (Self-approval)", "Immediate", "Standard Quote"])
    ws.append(["5.1% - 15.0%", "$5,000", "Regional Sales Manager", "2 Business Hours", "Deal Registration form"])
    ws.append(["15.1% - 25.0%", "$25,000", "Director of Commercial Sales", "4 Business Hours", "Competitive Displacement memo"])
    ws.append(["25.1% - 40.0%", "$100,000", "VP of Global Sales & Finance Director", "1 Business Day", "Executive Business Case"])
    ws.append(["> 40.0% (Special Deal)", "$250,000", "CEO & Board Committee", "2 Business Days", "Multi-Year Contract Agreement"])

    ws2 = wb.create_sheet(title="Payment Terms Schedule")
    ws2.append(["Customer Tier", "Default Payment Terms", "Credit Limit", "Early Payment Discount"])
    ws2.append(["Standard SMB", "Net 30 Days", "$25,000", "1% 10 Net 30"])
    ws2.append(["Enterprise Tier 1", "Net 45 Days", "$250,000", "2% 10 Net 45"])
    ws2.append(["Government / Public Sector", "Net 60 Days", "$1,000,000", "None"])
    ws2.append(["Pre-paid / Proforma", "100% Advance Payment", "$0", "3% Cash Discount"])
    wb.save(str(xlsx_path))

    # 4. Multi-page HR Leave and Remote Work Policy (PDF)
    pdf_hr_path = docs_dir / 'HR_Leave_and_Remote_Work_Policy_v3.pdf'
    doc_hr = SimpleDocTemplate(str(pdf_hr_path), pagesize=letter, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    story_hr = []

    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Heading1'], fontSize=18, leading=22, textColor=colors.HexColor('#1E293B')
    )
    h2_style = ParagraphStyle(
        'DocH2', parent=styles['Heading2'], fontSize=13, leading=17, textColor=colors.HexColor('#0F766E')
    )
    body_style = ParagraphStyle(
        'DocBody', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor('#334155')
    )

    # Page 1: Annual Leave & Sick Leave
    story_hr.append(Paragraph("MIIC Global Human Resources Policy: Leave & Flexible Working", title_style))
    story_hr.append(Paragraph("Document Code: POL-HR-2026-03 | Version: 3.2 | Effective Date: Jan 15, 2026", body_style))
    story_hr.append(Spacer(1, 15))
    story_hr.append(Paragraph("Section 1: Annual Paid Time Off (PTO)", h2_style))
    story_hr.append(Paragraph(
        "• Standard Full-time Employees are entitled to 18 working days of annual paid leave per calendar year.<br/>"
        "• Senior Staff (Managers and Directors) accrue 22 working days annually.<br/>"
        "• Leave accrues monthly at a rate of 1.5 days per completed month of service.<br/>"
        "• Maximum rollover to the next calendar year is 5 working days, which must be utilized before March 31.<br/>"
        "• Advance Notice: Applications for leave exceeding 3 consecutive days must be submitted at least 10 business days prior via the HR portal.",
        body_style
    ))
    story_hr.append(Spacer(1, 12))
    story_hr.append(Paragraph("Section 2: Medical & Sick Leave", h2_style))
    story_hr.append(Paragraph(
        "• Employees receive up to 14 days of paid outpatient medical leave per year.<br/>"
        "• A registered medical practitioner's Medical Certificate (MC) must be uploaded within 48 hours of return to work.<br/>"
        "• Hospitalization Leave: In cases requiring inpatient hospitalization, employees are entitled to up to 60 days of paid medical leave per year (inclusive of any outpatient sick leave taken).",
        body_style
    ))
    story_hr.append(Spacer(1, 40))

    # Page 2: Parental, Compassionate & Study Leave
    story_hr.append(Paragraph("Section 3: Parental & Family Support Leaves", h2_style))
    story_hr.append(Paragraph(
        "• Maternity Leave: 16 weeks of 100% paid leave for eligible female employees.<br/>"
        "• Paternity Leave: 4 weeks of paid paternity leave, available within the child's first 12 months.<br/>"
        "• Adoption Leave: 12 weeks of paid leave for primary adoptive caregivers.<br/>"
        "• Compassionate Leave: Up to 5 consecutive paid days upon bereavement of an immediate family member (spouse, child, parent, sibling).",
        body_style
    ))
    story_hr.append(Spacer(1, 15))
    story_hr.append(Paragraph("Section 4: Remote Work & Equipment Stipend", h2_style))
    story_hr.append(Paragraph(
        "• Hybrid Schedule: Employees in eligible roles may work remotely up to 2 days per week with manager approval.<br/>"
        "• Core Collaboration Hours: All employees must be accessible between 10:00 AM and 4:00 PM local time.<br/>"
        "• Home Office Allowance: A one-time tax-free equipment stipend of $500 USD is available for new full-time hires to procure ergonomic monitors, keyboards, and desk chairs.<br/>"
        "• Monthly Broadband Subsidy: Remote employees receive a $45 monthly internet reimbursement automatically added to payroll.",
        body_style
    ))
    doc_hr.build(story_hr)

    # 5. Multi-page Travel & Expense Reimbursement Policy (PDF)
    pdf_travel_path = docs_dir / 'Travel_and_Expense_Reimbursement_Policy_v2.pdf'
    doc_tr = SimpleDocTemplate(str(pdf_travel_path), pagesize=letter, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    story_tr = []

    story_tr.append(Paragraph("MIIC Corporate Travel & Expense Reimbursement Guidelines", title_style))
    story_tr.append(Paragraph("Document Code: POL-FIN-2026-08 | Version: 2.0 | Effective: March 1, 2026", body_style))
    story_tr.append(Spacer(1, 15))

    story_tr.append(Paragraph("1. Air Travel & Lodging Entitlements", h2_style))
    story_tr.append(Paragraph(
        "• Flights under 6 hours: Economy Class booking via corporate travel partner (Navan).<br/>"
        "• Flights exceeding 6 continuous hours: Premium Economy eligible. Business Class requires prior written authorization from the Department VP.<br/>"
        "• Hotel Daily Room Caps: Tier 1 Cities (New York, London, Tokyo, Singapore) max $280/night. Tier 2 Cities max $190/night.",
        body_style
    ))
    story_tr.append(Spacer(1, 12))

    story_tr.append(Paragraph("2. Daily Meals & Incidentals (Per Diem)", h2_style))
    story_tr.append(Paragraph(
        "• Domestic Travel Per Diem: Breakfast $20, Lunch $30, Dinner $55 (Daily Maximum $105).<br/>"
        "• International Travel Per Diem: Breakfast $25, Lunch $40, Dinner $75 (Daily Maximum $140).<br/>"
        "• Alcohol Policy: Moderate consumption during client business dinners is reimbursable (max 2 beverages per attendee). Solo traveler alcoholic beverages are strictly non-reimbursable.",
        body_style
    ))
    story_tr.append(Spacer(1, 12))

    story_tr.append(Paragraph("3. Mileage & Ground Transportation", h2_style))
    story_tr.append(Paragraph(
        "• Personal Vehicle Mileage: Reimbursed at $0.67 per business mile (includes gas and wear-and-tear).<br/>"
        "• Rideshare (Uber/Lyft): Standard UberX or Lyft ride options must be selected. Uber Black or Lux is prohibited.",
        body_style
    ))
    story_tr.append(Spacer(1, 12))

    story_tr.append(Paragraph("4. Submission Deadlines & Receipts", h2_style))
    story_tr.append(Paragraph(
        "• Submission Window: All expense reports must be submitted in the Concur portal within 30 calendar days of expense occurrence.<br/>"
        "• Itemized Receipts: Mandatory for all individual expenses of $25.00 USD and above. Credit card charge slips alone are insufficient.",
        body_style
    ))
    doc_tr.build(story_tr)

    return [docx_path, md_path, xlsx_path, pdf_hr_path, pdf_travel_path]


if __name__ == '__main__':
    created = create_sample_docs()
    print(f"Created {len(created)} sample docs in sample_documents/")

