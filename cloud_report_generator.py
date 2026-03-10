from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, PageBreak, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import tempfile
from datetime import date
import pandas as pd

print("Report generator loaded")


def generate_boardroom_pdf(client):
    """
    Generate a professional boardroom-style PDF with just client parameter.
    
    Args:
        client (str): Client name
    
    Returns:
        str: Path to the generated PDF file
    """
    # Default values for demo purposes
    monthly_spend = 150000
    savings_monthly = 25000
    top_service_name = "EC2 Instances"
    maturity_score = 78
    
    file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(file.name, pagesize=letter)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "Title",
        fontSize=22,
        leading=28,
        alignment=1,
        spaceAfter=20
    )

    section_style = ParagraphStyle(
        "Section",
        fontSize=16,
        spaceAfter=12,
        textColor=colors.darkblue
    )

    content = []

    # ===== COVER PAGE =====
    content.append(Spacer(1, 120))
    content.append(Paragraph("Cloud Executive Advisory Report", title_style))
    content.append(Spacer(1, 40))

    content.append(Paragraph(f"Client: {client}", styles["Normal"]))
    content.append(Paragraph(f"Date: {date.today()}", styles["Normal"]))
    content.append(Paragraph("Confidential — For Executive Review", styles["Italic"]))

    content.append(PageBreak())

    # ===== EXECUTIVE SNAPSHOT =====
    content.append(Paragraph("Executive Snapshot", ParagraphStyle(
        "Header",
        fontSize=18,
        textColor=colors.darkblue,
        spaceAfter=12
    )))

    snapshot_data = [
        ["Metric", "Value"],
        ["Monthly Spend", f"₹{monthly_spend:,.0f}"],
        ["Annual Run Rate", f"₹{monthly_spend*12:,.0f}"],
        ["Savings Opportunity", f"₹{savings_monthly:,.0f}"],
        ["Top Cost Driver", top_service_name],
        ["Cloud Maturity", f"{maturity_score}/100"]
    ]

    snapshot_table = Table(snapshot_data, colWidths=[220, 180])

    snapshot_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
            [colors.whitesmoke, colors.lightgrey]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey)
    ]))

    content.append(snapshot_table)
    content.append(PageBreak())

    # ===== PRIORITY ACTIONS =====
    content.append(Paragraph("Priority Actions — Next 30 Days", section_style))

    actions = [
        "Optimize high-cost service footprint",
        "Implement Savings Plans / Reserved Instances",
        "Remove idle resources and unused assets"
    ]

    for action in actions:
        content.append(Paragraph(f"• {action}", styles["Normal"]))

    content.append(PageBreak())

    # ===== FINANCIAL IMPACT =====
    content.append(Paragraph("Financial Impact", section_style))

    content.append(Paragraph("Cost Distribution", section_style))
    content.append(Image("cost_distribution.png", width=400, height=300))

    content.append(Paragraph(
        f"<b>Monthly Spend:</b> ₹{monthly_spend:,.0f}",
        ParagraphStyle("KPI", fontSize=16, spaceAfter=12)
    ))

    content.append(Paragraph(
        f"Estimated Annual Savings: ₹{savings_monthly*12:,.0f}",
        ParagraphStyle("Highlight",
            backColor=colors.lightblue,
            borderPadding=8,
            fontSize=12
        )
    ))
    content.append(Paragraph(
        "Estimated ROI Timeline: Less than 12 months",
        styles["Normal"]
    ))
    content.append(Paragraph(
        "Savings can be reinvested into innovation and modernization initiatives.",
        styles["Normal"]
    ))

    content.append(PageBreak())

    content.append(Paragraph("Executive Dashboard — " + client, section_style))

    content.append(Paragraph(
        f"Cloud Maturity: {maturity_score}/100",
        styles["Normal"]
    ))

    content.append(Paragraph(
        f"Transformation Readiness: {readiness_score}/100",
        styles["Normal"]
    ))

    doc.build(content)

    return file.name


def generate_executive_pdf(client):
    """
    Generate a simplified executive PDF with just client parameter.
    
    Args:
        client (str): Client name
    
    Returns:
        str: Path to the generated PDF file
    """
    # Default values for demo purposes
    monthly_spend = 150000
    savings_monthly = 25000
    top_service_name = "EC2 Instances"
    maturity_score = 78
    
    file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(file.name, pagesize=letter)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "Title",
        fontSize=22,
        leading=28,
        alignment=1,
        spaceAfter=20
    )

    section_style = ParagraphStyle(
        "Section",
        fontSize=16,
        spaceAfter=12,
        textColor=colors.darkblue
    )

    content = []

    # ===== COVER PAGE =====
    content.append(Spacer(1, 120))
    content.append(Paragraph("Cloud Executive Advisory Report", title_style))
    content.append(Spacer(1, 40))

    content.append(Paragraph(f"Client: {client}", styles["Normal"]))
    content.append(Paragraph(f"Date: {date.today()}", styles["Normal"]))
    content.append(Paragraph("Confidential — For Executive Review", styles["Italic"]))

    content.append(PageBreak())

    # ===== EXECUTIVE SNAPSHOT =====
    content.append(Paragraph("Executive Snapshot", ParagraphStyle(
        "Header",
        fontSize=18,
        textColor=colors.darkblue,
        spaceAfter=12
    )))

    snapshot_data = [
        ["Metric", "Value"],
        ["Monthly Spend", f"₹{monthly_spend:,.0f}"],
        ["Annual Run Rate", f"₹{monthly_spend*12:,.0f}"],
        ["Savings Opportunity", f"₹{savings_monthly:,.0f}"],
        ["Top Cost Driver", top_service_name],
        ["Cloud Maturity", f"{maturity_score}/100"]
    ]

    snapshot_table = Table(snapshot_data, colWidths=[220, 180])

    snapshot_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
            [colors.whitesmoke, colors.lightgrey]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey)
    ]))

    content.append(snapshot_table)
    content.append(PageBreak())

    # ===== PRIORITY ACTIONS =====
    content.append(Paragraph("Priority Actions — Next 30 Days", section_style))

    actions = [
        "Optimize high-cost service footprint",
        "Implement Savings Plans / Reserved Instances",
        "Remove idle resources and unused assets"
    ]

    for action in actions:
        content.append(Paragraph(f"• {action}", styles["Normal"]))

    content.append(PageBreak())

    # ===== FINANCIAL IMPACT =====
    content.append(Paragraph("Financial Impact", section_style))

    content.append(Paragraph("Cost Distribution", section_style))
    content.append(Image("cost_distribution.png", width=400, height=300))

    content.append(Paragraph(
        f"<b>Monthly Spend:</b> ₹{monthly_spend:,.0f}",
        ParagraphStyle("KPI", fontSize=16, spaceAfter=12)
    ))

    content.append(Paragraph(
        f"Estimated Annual Savings: ₹{savings_monthly*12:,.0f}",
        ParagraphStyle("Highlight",
            backColor=colors.lightblue,
            borderPadding=8,
            fontSize=12
        )
    ))
    content.append(Paragraph(
        "Estimated ROI Timeline: Less than 12 months",
        styles["Normal"]
    ))
    content.append(Paragraph(
        "Savings can be reinvested into innovation and modernization initiatives.",
        styles["Normal"]
    ))

    content.append(PageBreak())

    content.append(Paragraph("Executive Dashboard — " + client, section_style))

    content.append(Paragraph(
        f"Cloud Maturity: {maturity_score}/100",
        styles["Normal"]
    ))

    content.append(Paragraph(
        f"Transformation Readiness: {readiness_score}/100",
        styles["Normal"]
    ))

    doc.build(content)

    return file.name


def generate_boardroom_pdf(client, monthly_spend=None, savings_monthly=None, top_service_name=None, maturity_score=None):
    """
    Generate a professional boardroom-style PDF cloud executive report.
    
    Args:
        client (str): Client name
        monthly_spend (float, optional): Monthly cloud spend amount
        savings_monthly (float, optional): Potential monthly savings
        top_service_name (str, optional): Name of top cost-driving service
        maturity_score (int, optional): Cloud maturity score (0-100)
    
    Returns:
        str: Path to the generated PDF file
    """
    # Use default values if not provided
    if monthly_spend is None:
        monthly_spend = 150000
    if savings_monthly is None:
        savings_monthly = 25000
    if top_service_name is None:
        top_service_name = "EC2 Instances"
    if maturity_score is None:
        maturity_score = 78
    
    file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(file.name, pagesize=letter)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "Title",
        fontSize=22,
        leading=28,
        alignment=1,
        spaceAfter=20
    )

    section_style = ParagraphStyle(
        "Section",
        fontSize=16,
        spaceAfter=12,
        textColor=colors.darkblue
    )

    content = []

    # ===== COVER PAGE =====
    content.append(Spacer(1, 120))
    content.append(Paragraph("Cloud Executive Advisory Report", title_style))
    content.append(Spacer(1, 40))

    content.append(Paragraph(f"Client: {client}", styles["Normal"]))
    content.append(Paragraph(f"Date: {date.today()}", styles["Normal"]))
    content.append(Paragraph("Confidential — For Executive Review", styles["Italic"]))

    content.append(PageBreak())

    # ===== EXECUTIVE SNAPSHOT =====
    content.append(Paragraph("Executive Snapshot", ParagraphStyle(
        "Header",
        fontSize=18,
        textColor=colors.darkblue,
        spaceAfter=12
    )))

    snapshot_data = [
        ["Metric", "Value"],
        ["Monthly Spend", f"₹{monthly_spend:,.0f}"],
        ["Annual Run Rate", f"₹{monthly_spend*12:,.0f}"],
        ["Savings Opportunity", f"₹{savings_monthly:,.0f}"],
        ["Top Cost Driver", top_service_name],
        ["Cloud Maturity", f"{maturity_score}/100"]
    ]

    snapshot_table = Table(snapshot_data, colWidths=[220, 180])

    snapshot_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
            [colors.whitesmoke, colors.lightgrey]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey)
    ]))

    content.append(snapshot_table)
    content.append(PageBreak())

    # ===== PRIORITY ACTIONS =====
    content.append(Paragraph("Priority Actions — Next 30 Days", section_style))

    actions = [
        "Optimize high-cost service footprint",
        "Implement Savings Plans / Reserved Instances",
        "Remove idle resources and unused assets"
    ]

    for action in actions:
        content.append(Paragraph(f"• {action}", styles["Normal"]))

    content.append(PageBreak())

    # ===== FINANCIAL IMPACT =====
    content.append(Paragraph("Financial Impact", section_style))

    content.append(Paragraph("Cost Distribution", section_style))
    content.append(Image("cost_distribution.png", width=400, height=300))

    content.append(Paragraph(
        f"<b>Monthly Spend:</b> ₹{monthly_spend:,.0f}",
        ParagraphStyle("KPI", fontSize=16, spaceAfter=12)
    ))

    content.append(Paragraph(
        f"Estimated Annual Savings: ₹{savings_monthly*12:,.0f}",
        ParagraphStyle("Highlight",
            backColor=colors.lightblue,
            borderPadding=8,
            fontSize=12
        )
    ))
    content.append(Paragraph(
        "Estimated ROI Timeline: Less than 12 months",
        styles["Normal"]
    ))
    content.append(Paragraph(
        "Savings can be reinvested into innovation and modernization initiatives.",
        styles["Normal"]
    ))

    content.append(PageBreak())

    content.append(Paragraph("Executive Dashboard — " + client, section_style))

    content.append(Paragraph(
        f"Cloud Maturity: {maturity_score}/100",
        styles["Normal"]
    ))

    content.append(Paragraph(
        f"Transformation Readiness: {readiness_score}/100",
        styles["Normal"]
    ))

    doc.build(content)

    return file.name

def generate_excel_report(client, monthly_spend=None, savings_monthly=None, top_service_name=None, maturity_score=None, service_cost=None, df=None):
    """
    Generate a comprehensive Excel report with multiple sheets.
    
    Args:
        client (str): Client name
        monthly_spend (float, optional): Monthly cloud spend amount
        savings_monthly (float, optional): Potential monthly savings
        top_service_name (str, optional): Name of top cost-driving service
        maturity_score (int, optional): Cloud maturity score (0-100)
        service_cost (pd.DataFrame, optional): Service cost breakdown
        df (pd.DataFrame, optional): Raw billing data
    
    Returns:
        str: Path to the generated Excel file
    """
    # Use default values if not provided
    if monthly_spend is None:
        monthly_spend = 150000
    if savings_monthly is None:
        savings_monthly = 25000
    if top_service_name is None:
        top_service_name = "EC2 Instances"
    if maturity_score is None:
        maturity_score = 78
    
    file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")

    with pd.ExcelWriter(file.name, engine="openpyxl") as writer:

        # ===== Sheet 1 — Executive Summary =====
        summary_df = pd.DataFrame({
            "Metric": [
                "Client",
                "Date",
                "Monthly Spend",
                "Annual Run Rate",
                "Savings Opportunity",
                "Top Cost Driver",
                "Cloud Maturity"
            ],
            "Value": [
                client,
                date.today(),
                f"₹{monthly_spend:,.0f}",
                f"₹{monthly_spend*12:,.0f}",
                f"₹{savings_monthly:,.0f}",
                top_service_name,
                f"{maturity_score}/100"
            ]
        })

        summary_df.to_excel(writer, sheet_name="Executive Summary", index=False)
        
        # Format Executive Summary columns
        worksheet = writer.book["Executive Summary"]
        worksheet.column_dimensions["A"].width = 30
        worksheet.column_dimensions["B"].width = 25

        # ===== Sheet 2 — Top Services =====
        if service_cost is not None:
            service_cost.to_excel(writer, sheet_name="Cost by Service", index=False)
        else:
            # Create sample service cost data
            sample_services = pd.DataFrame({
                "Service": ["EC2 Instances", "RDS Database", "S3 Storage", "CloudFront", "Lambda"],
                "Cost": [75000, 30000, 22500, 15000, 7500]
            })
            sample_services.to_excel(writer, sheet_name="Cost by Service", index=False)

        # ===== Sheet 3 — Raw Data =====
        if df is not None:
            df.to_excel(writer, sheet_name="Raw Billing Data", index=False)
        else:
            # Create sample raw data
            sample_raw = pd.DataFrame({
                "Service": ["EC2", "RDS", "S3", "CloudFront", "Lambda"],
                "Cost": [75000, 30000, 22500, 15000, 7500],
                "Usage": ["High", "Medium", "Low", "Medium", "Low"]
            })
            sample_raw.to_excel(writer, sheet_name="Raw Billing Data", index=False)

    return file.name


def generate_dashboard_pdf(client, monthly_spend=None, savings_monthly=None, maturity_score=None, readiness_score=None):
    """
    Generate a dashboard-style PDF report with charts and metrics.
    
    Args:
        client (str): Client name
        monthly_spend (float, optional): Monthly cloud spend amount
        savings_monthly (float, optional): Potential monthly savings
        maturity_score (int, optional): Cloud maturity score (0-100)
        readiness_score (int, optional): Transformation readiness score (0-100)
    
    Returns:
        str: Path to the generated PDF file
    """
    # Use default values if not provided
    if monthly_spend is None:
        monthly_spend = 150000
    if savings_monthly is None:
        savings_monthly = 25000
    if maturity_score is None:
        maturity_score = 78
    if readiness_score is None:
        readiness_score = 70

    file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(file.name, pagesize=letter)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "Title", fontSize=20, alignment=1, spaceAfter=20
    )

    section_style = ParagraphStyle(
        "Section", fontSize=16, textColor=colors.darkblue, spaceAfter=10
    )

    content = []

    # ===== COVER =====
    content.append(Spacer(1, 120))
    content.append(Paragraph("Cloud Executive Dashboard Report", title_style))
    content.append(Paragraph(f"Client: {client}", styles["Normal"]))
    content.append(Paragraph(f"Date: {date.today()}", styles["Normal"]))
    content.append(PageBreak())

    # ===== EXECUTIVE DASHBOARD =====
    content.append(Paragraph(f"Executive Dashboard — {client}", section_style))

    content.append(Paragraph(
        f"Monthly Spend: ₹{monthly_spend:,.0f}", styles["Normal"]
    ))
    content.append(Paragraph(
        f"Savings Opportunity: ₹{savings_monthly:,.0f}", styles["Normal"]
    ))
    content.append(Paragraph(
        f"Cloud Maturity: {maturity_score}/100", styles["Normal"]
    ))
    content.append(Paragraph(
        f"Transformation Readiness: {readiness_score}/100", styles["Normal"]
    ))

    content.append(PageBreak())

    # ===== COST DISTRIBUTION CHART =====
    content.append(Paragraph("Cost Distribution", section_style))
    content.append(Image("cost_distribution.png", width=400, height=300))

    content.append(PageBreak())

    # ===== COST BY SERVICE =====
    content.append(Paragraph("Cost by Service", section_style))
    content.append(Image("cost_by_service.png", width=400, height=300))

    content.append(PageBreak())

    # ===== PRIORITY ACTIONS =====
    content.append(Paragraph("Priority Actions", section_style))

    actions = [
        "Optimize high-cost services",
        "Implement Savings Plans",
        "Remove idle resources"
    ]

    for action in actions:
        content.append(Paragraph(f"• {action}", styles["Normal"]))

    doc.build(content)

    return file.name


# Legacy function for backward compatibility
def generate_pdf(monthly_spend, savings_monthly, top_service_name, maturity_score, top_services_data=None):
    """
    Generate a PDF cloud executive report (legacy function).
    
    Args:
        monthly_spend (float): Monthly cloud spend amount
        savings_monthly (float): Potential monthly savings
        top_service_name (str): Name of top cost-driving service
        maturity_score (int): Cloud maturity score (0-100)
        top_services_data (list, optional): List of tuples with service data for table
    
    Returns:
        str: Path to the generated PDF file
    """
    file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")

    doc = SimpleDocTemplate(file.name, pagesize=letter)
    styles = getSampleStyleSheet()

    content = []

    content.append(Paragraph("Cloud Executive Report", styles["Title"]))
    content.append(Spacer(1, 12))

    content.append(Paragraph(f"Monthly Spend: ₹{monthly_spend:,.0f}", styles["Normal"]))
    content.append(Paragraph(f"Savings Opportunity: ₹{savings_monthly:,.0f}", styles["Normal"]))
    content.append(Paragraph(f"Top Cost Driver: {top_service_name}", styles["Normal"]))
    content.append(Paragraph(f"Cloud Maturity Score: {maturity_score}/100", styles["Normal"]))
    
    if top_services_data:
        content.append(Spacer(1, 12))
        content.append(Paragraph("Top Services", styles["Heading2"]))
        
        # Create table using tabulate
        table_text = tabulate(top_services_data, headers=["Service", "Cost (₹)", "Percentage"], 
                              tablefmt="grid", floatfmt=".2f")
        
        # Add table as paragraph (simple approach)
        content.append(Paragraph(table_text, styles["Code"]))

    content.append(PageBreak())

    content.append(Paragraph("Executive Dashboard — " + client, section_style))

    content.append(Paragraph(
        f"Cloud Maturity: {maturity_score}/100",
        styles["Normal"]
    ))

    content.append(Paragraph(
        f"Transformation Readiness: {readiness_score}/100",
        styles["Normal"]
    ))

    doc.build(content)

    return file.name

# Example usage
if __name__ == "__main__":
    # Sample data
    monthly_spend = 150000
    savings_monthly = 25000
    top_service_name = "EC2 Instances"
    maturity_score = 78
    client = "Acme Corp"
    
    # Generate executive PDF
    pdf_path = generate_executive_pdf(client, monthly_spend, savings_monthly, top_service_name, maturity_score)
    print(f"Executive PDF generated: {pdf_path}")

# Streamlit integration example
def streamlit_export_button(client, monthly_spend, savings_monthly, top_service_name, maturity_score, top_services_data=None):
    """
    Streamlit sidebar button and download functionality for PDF export.
    
    Args:
        client (str): Client name
        monthly_spend (float): Monthly cloud spend amount
        savings_monthly (float): Potential monthly savings
        top_service_name (str): Name of top cost-driving service
        maturity_score (int): Cloud maturity score (0-100)
        top_services_data (list, optional): List of tuples with service data for table
    """
    import streamlit as st
    
    if st.sidebar.button("Export Executive Report (PDF)"):
        pdf_file = generate_executive_pdf(client, monthly_spend, savings_monthly, top_service_name, maturity_score)

        with open(pdf_file, "rb") as f:
            st.sidebar.download_button(
                label="Download Report",
                data=f,
                file_name="Cloud_Executive_Report.pdf",
                mime="application/pdf"
            )

# Example usage
if __name__ == "__main__":
    # Sample data
    monthly_spend = 150000
    savings_monthly = 25000
    top_service_name = "EC2 Instances"
    maturity_score = 78
    
    # Sample top services data for table
    top_services_data = [
        ("EC2 Instances", 75000, 50.0),
        ("RDS Database", 30000, 20.0),
        ("S3 Storage", 22500, 15.0),
        ("CloudFront", 15000, 10.0),
        ("Lambda", 7500, 5.0)
    ]
    
    # Generate PDF
    pdf_path = generate_pdf(monthly_spend, savings_monthly, top_service_name, maturity_score, top_services_data)
    print(f"PDF generated: {pdf_path}")

# Streamlit integration example
def streamlit_export_button(monthly_spend, savings_monthly, top_service_name, maturity_score, top_services_data=None):
    """
    Streamlit sidebar button and download functionality for PDF export.
    
    Args:
        monthly_spend (float): Monthly cloud spend amount
        savings_monthly (float): Potential monthly savings
        top_service_name (str): Name of top cost-driving service
        maturity_score (int): Cloud maturity score (0-100)
        top_services_data (list, optional): List of tuples with service data for table
    """
    import streamlit as st
    
    if st.sidebar.button("Export Executive Report (PDF)"):
        pdf_file = generate_pdf(monthly_spend, savings_monthly, top_service_name, maturity_score, top_services_data)

        with open(pdf_file, "rb") as f:
            st.sidebar.download_button(
                label="Download Report",
                data=f,
                file_name="Cloud_Executive_Report.pdf",
                mime="application/pdf"
            )
