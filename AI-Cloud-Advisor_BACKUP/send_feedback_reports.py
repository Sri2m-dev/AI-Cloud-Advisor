from scipy.stats import mannwhitneyu, ks_2samp
import numpy as np
from scipy.stats import pearsonr, linregress, chi2_contingency
import os
import time
try:
    import schedule
except ImportError:
    print("Warning: 'schedule' package not found. Install with 'pip install schedule' if needed.")
import yagmail
import pandas as pd
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import tempfile
import matplotlib.pyplot as plt
from reportlab.platypus import Image

def create_pdf_table_report(df, title, filename, chart_path=None, chart_title=None):
    doc = SimpleDocTemplate(filename, pagesize=landscape(letter))
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph(title, styles['Title']))
    elements.append(Spacer(1, 12))
    # Add chart if provided
    if chart_path:
        elements.append(Paragraph(chart_title or "Chart", styles['Heading2']))
        elements.append(Image(chart_path, width=400, height=200))
        elements.append(Spacer(1, 12))
    # Convert DataFrame to list of lists
    data = [list(df.columns)] + df.astype(str).values.tolist()
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#dbeafe')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#1e293b')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f1f5f9')]),
    ]))
    elements.append(table)
    doc.build(elements)

def save_bar_chart(series, title, filename):
    plt.figure(figsize=(6,3))
    series.plot(kind='bar', color='#2563eb')
    plt.title(title)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

def save_pie_chart(series, title, filename):
    plt.figure(figsize=(4,4))
    series.plot.pie(autopct='%1.0f%%', colors=['#2563eb','#f59e42','#10b981','#f43f5e'])
    plt.title(title)
    plt.ylabel('')
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

def send_feedback_reports():
    email_to = os.getenv("FEEDBACK_REPORT_EMAIL_TO", "your@email.com")
    yag = yagmail.SMTP(user=os.getenv("YAGMAIL_USER"), password=os.getenv("YAGMAIL_PASSWORD"))
    attachments = []
    # Anomaly feedback
    if os.path.exists("anomaly_feedback.csv"):
        df_anom = pd.read_csv("anomaly_feedback.csv")
        # Bar chart for anomaly feedback
        bar_path = tempfile.mktemp(suffix="_anom_bar.png")
        save_bar_chart(df_anom['flag'].value_counts(), "Anomaly Feedback Distribution", bar_path)
        # Time series trend plot
        if 'date' in df_anom.columns:
            df_anom['date'] = pd.to_datetime(df_anom['date'])
            ts_trend = df_anom.groupby([df_anom['date'].dt.to_period('M'),'flag']).size().unstack(fill_value=0)
            ts_path = tempfile.mktemp(suffix="_anom_ts.png")
            ts_trend.plot(kind='line', marker='o', figsize=(6,3))
            plt.title('Anomaly Feedback Trend Over Time')
            plt.tight_layout()
            plt.savefig(ts_path)
            plt.close()
            # Advanced: regression on total feedback trend
            trend_total = ts_trend.sum(axis=1)
            if len(trend_total) > 1:
                x = range(len(trend_total))
                slope, intercept, r_value, p_value, std_err = linregress(x, trend_total.values)
                reg_text = f"Trend regression: slope={slope:.2f}, r={r_value:.2f}, p={p_value:.3f}"
                reg_pdf = tempfile.mktemp(suffix="_anom_regression.pdf")
                reg_df = pd.DataFrame({'Month': trend_total.index.astype(str), 'Total Feedback': trend_total.values})
                create_pdf_table_report(reg_df, "Anomaly Feedback Trend Regression", reg_pdf, chart_path=ts_path, chart_title=reg_text)
                attachments.append(reg_pdf)
        else:
            ts_path = None
        # User-level breakdown
        user_chart = None
        if 'user' in df_anom.columns:
            user_counts = df_anom.groupby(['user','flag']).size().unstack(fill_value=0)
            user_chart = tempfile.mktemp(suffix="_anom_user.png")
            user_counts.plot(kind='bar', stacked=True, figsize=(6,3))
            plt.title('Anomaly Feedback by User')
            plt.tight_layout()
            plt.savefig(user_chart)
            plt.close()
        pdf_path = tempfile.mktemp(suffix="_anomaly_feedback.pdf")
        create_pdf_table_report(df_anom, "Anomaly Feedback Report", pdf_path, chart_path=bar_path, chart_title="Anomaly Feedback Distribution")
        attachments.append(pdf_path)
        # Add summary report with pie chart and trend
        summary = df_anom['flag'].value_counts().rename_axis('Feedback').reset_index(name='Count')
        pie_path = tempfile.mktemp(suffix="_anom_pie.png")
        save_pie_chart(df_anom['flag'].value_counts(), "Anomaly Feedback Pie Chart", pie_path)
        pdf_sum = tempfile.mktemp(suffix="_anomaly_summary.pdf")
        create_pdf_table_report(summary, "Anomaly Feedback Summary", pdf_sum, chart_path=pie_path, chart_title="Anomaly Feedback Pie Chart")
        attachments.append(pdf_sum)
        # Add time series trend plot
        if ts_path:
            pdf_ts = tempfile.mktemp(suffix="_anomaly_trend.pdf")
            create_pdf_table_report(ts_trend.reset_index(), "Anomaly Feedback Trend Over Time", pdf_ts, chart_path=ts_path, chart_title="Monthly Trend")
            attachments.append(pdf_ts)
        # Add user-level breakdown chart
        if user_chart:
            pdf_user = tempfile.mktemp(suffix="_anomaly_user.pdf")
            create_pdf_table_report(user_counts.reset_index(), "Anomaly Feedback by User", pdf_user, chart_path=user_chart, chart_title="User Breakdown")
            attachments.append(pdf_user)
    # Recommendation feedback
    if os.path.exists("recommendation_feedback.csv"):
        df_rec = pd.read_csv("recommendation_feedback.csv")
        # Bar chart for recommendation feedback
        bar_path = tempfile.mktemp(suffix="_rec_bar.png")
        save_bar_chart(df_rec['flag'].value_counts(), "Recommendation Feedback Distribution", bar_path)
        # Time series trend plot
        if 'type' in df_rec.columns and 'flag' in df_rec.columns:
            if 'date' in df_rec.columns:
                df_rec['date'] = pd.to_datetime(df_rec['date'])
                ts_trend = df_rec.groupby([df_rec['date'].dt.to_period('M'),'type','flag']).size().unstack(fill_value=0)
                ts_path = tempfile.mktemp(suffix="_rec_ts.png")
                ts_trend.plot(kind='line', marker='o', figsize=(6,3))
                plt.title('Recommendation Feedback Trend Over Time')
                plt.tight_layout()
                plt.savefig(ts_path)
                plt.close()
                # Advanced: regression on total feedback trend
                trend_total = ts_trend.sum(axis=1)
                if len(trend_total) > 1:
                    x = range(len(trend_total))
                    slope, intercept, r_value, p_value, std_err = linregress(x, trend_total.values)
                    reg_text = f"Trend regression: slope={slope:.2f}, r={r_value:.2f}, p={p_value:.3f}"
                    reg_pdf = tempfile.mktemp(suffix="_rec_regression.pdf")
                    reg_df = pd.DataFrame({'Month': trend_total.index.astype(str), 'Total Feedback': trend_total.values})
                    create_pdf_table_report(reg_df, "Recommendation Feedback Trend Regression", reg_pdf, chart_path=ts_path, chart_title=reg_text)
                    attachments.append(reg_pdf)
            else:
                ts_path = None
        else:
            ts_path = None
        # User-level breakdown
        user_chart = None
        if 'user' in df_rec.columns:
            user_counts = df_rec.groupby(['user','type','flag']).size().unstack(fill_value=0)
            user_chart = tempfile.mktemp(suffix="_rec_user.png")
            user_counts.plot(kind='bar', stacked=True, figsize=(6,3))
            plt.title('Recommendation Feedback by User')
            plt.tight_layout()
            plt.savefig(user_chart)
            plt.close()
        pdf_path = tempfile.mktemp(suffix="_recommendation_feedback.pdf")
        create_pdf_table_report(df_rec, "Recommendation Feedback Report", pdf_path, chart_path=bar_path, chart_title="Recommendation Feedback Distribution")
        attachments.append(pdf_path)
        # Add summary by type with pie chart
        summary = df_rec.groupby(['type', 'flag']).size().reset_index(name='Count')
        pie_path = tempfile.mktemp(suffix="_rec_pie.png")
        save_pie_chart(df_rec['flag'].value_counts(), "Recommendation Feedback Pie Chart", pie_path)
        pdf_sum = tempfile.mktemp(suffix="_recommendation_summary.pdf")
        create_pdf_table_report(summary, "Recommendation Feedback by Type", pdf_sum, chart_path=pie_path, chart_title="Recommendation Feedback Pie Chart")
        attachments.append(pdf_sum)
        # Add time series trend plot
        if ts_path:
            pdf_ts = tempfile.mktemp(suffix="_recommendation_trend.pdf")
            create_pdf_table_report(ts_trend.reset_index(), "Recommendation Feedback Trend Over Time", pdf_ts, chart_path=ts_path, chart_title="Monthly Trend")
            attachments.append(pdf_ts)
        # Add user-level breakdown chart
        if user_chart:
            pdf_user = tempfile.mktemp(suffix="_recommendation_user.pdf")
            create_pdf_table_report(user_counts.reset_index(), "Recommendation Feedback by User", pdf_user, chart_path=user_chart, chart_title="User Breakdown")
            attachments.append(pdf_user)
    # Add overall feedback trend report if both exist
    if os.path.exists("anomaly_feedback.csv") and os.path.exists("recommendation_feedback.csv"):
        df_anom = pd.read_csv("anomaly_feedback.csv")
        df_rec = pd.read_csv("recommendation_feedback.csv")
        trend = pd.DataFrame({
            'Anomaly Feedback': df_anom['flag'].value_counts(),
            'Recommendation Feedback': df_rec['flag'].value_counts()
        }).fillna(0).astype(int)
        # Bar chart for overall trend
        bar_path = tempfile.mktemp(suffix="_trend_bar.png")
        trend.plot(kind='bar', figsize=(6,3)).get_figure().savefig(bar_path)
        plt.close()
        # Correlation analysis (if dates available)
        corr_chart = None
        if 'date' in df_anom.columns and 'date' in df_rec.columns:
            df_anom['date'] = pd.to_datetime(df_anom['date'])
            df_rec['date'] = pd.to_datetime(df_rec['date'])
            anom_month = df_anom.groupby(df_anom['date'].dt.to_period('M')).size()
            rec_month = df_rec.groupby(df_rec['date'].dt.to_period('M')).size()
            corr_df = pd.DataFrame({'Anomaly': anom_month, 'Recommendation': rec_month}).fillna(0)
            corr_chart = tempfile.mktemp(suffix="_corr.png")
            corr_df.plot(kind='line', marker='o', figsize=(6,3))
            plt.title('Monthly Feedback Correlation')
            plt.tight_layout()
            plt.savefig(corr_chart)
            plt.close()
            # Advanced: correlation coefficient
            if len(corr_df) > 1:
                corr_val, corr_p = pearsonr(corr_df['Anomaly'], corr_df['Recommendation'])
                corr_text = f"Pearson correlation: r={corr_val:.2f}, p={corr_p:.3f}"
                corr_pdf = tempfile.mktemp(suffix="_corr_stats.pdf")
                create_pdf_table_report(corr_df.reset_index(), "Monthly Feedback Correlation (Stats)", corr_pdf, chart_path=corr_chart, chart_title=corr_text)
                attachments.append(corr_pdf)
            # Advanced: chi-squared test for independence
            if len(trend) > 1:
                chi2, p, dof, expected = chi2_contingency(trend.values)
                chi_text = f"Chi-squared test: chi2={chi2:.2f}, p={p:.3f}, dof={dof}"
                chi_pdf = tempfile.mktemp(suffix="_chi2.pdf")
                chi_df = pd.DataFrame(trend)
                create_pdf_table_report(chi_df.reset_index(), "Feedback Independence Test", chi_pdf, chart_title=chi_text)
                attachments.append(chi_pdf)
            # Mann-Whitney U test (distribution difference)
            if len(corr_df) > 1:
                try:
                    u_stat, u_p = mannwhitneyu(corr_df['Anomaly'], corr_df['Recommendation'], alternative='two-sided')
                    u_text = f"Mann-Whitney U: U={u_stat:.2f}, p={u_p:.3f}"
                    u_pdf = tempfile.mktemp(suffix="_mannwhitney.pdf")
                    create_pdf_table_report(corr_df.reset_index(), "Mann-Whitney U Test", u_pdf, chart_title=u_text)
                    attachments.append(u_pdf)
                except Exception as e:
                    print(f"Mann-Whitney U test error: {e}")
            # Kolmogorov-Smirnov test (distribution shape)
            if len(corr_df) > 1:
                try:
                    ks_stat, ks_p = ks_2samp(corr_df['Anomaly'], corr_df['Recommendation'])
                    ks_text = f"Kolmogorov-Smirnov: D={ks_stat:.2f}, p={ks_p:.3f}"
                    ks_pdf = tempfile.mktemp(suffix="_ks.pdf")
                    create_pdf_table_report(corr_df.reset_index(), "Kolmogorov-Smirnov Test", ks_pdf, chart_title=ks_text)
                    attachments.append(ks_pdf)
                except Exception as e:
                    print(f"Kolmogorov-Smirnov test error: {e}")
            # Cramér's V (effect size for chi2)
            if len(trend) > 1:
                try:
                    chi2, p, dof, expected = chi2_contingency(trend.values)
                    n = np.sum(trend.values)
                    phi2 = chi2 / n
                    r, k = trend.shape
                    cramers_v = np.sqrt(phi2 / min(k-1, r-1))
                    cv_text = f"Cramér's V: {cramers_v:.2f} (effect size)"
                    cv_pdf = tempfile.mktemp(suffix="_cramersv.pdf")
                    create_pdf_table_report(trend.reset_index(), "Cramér's V Effect Size", cv_pdf, chart_title=cv_text)
                    attachments.append(cv_pdf)
                except Exception as e:
                    print(f"Cramér's V calculation error: {e}")
        pdf_trend = tempfile.mktemp(suffix="_feedback_trend.pdf")
        create_pdf_table_report(trend.reset_index(), "Overall Feedback Trend", pdf_trend, chart_path=bar_path, chart_title="Overall Feedback Trend Chart")
        attachments.append(pdf_trend)
        if corr_chart:
            pdf_corr = tempfile.mktemp(suffix="_feedback_correlation.pdf")
            create_pdf_table_report(corr_df.reset_index(), "Monthly Feedback Correlation", pdf_corr, chart_path=corr_chart, chart_title="Correlation of Feedback Volume")
            attachments.append(pdf_corr)
    if attachments:
        yag.send(to=email_to, subject="Cloud Advisor Feedback Analytics Reports (Automated)", contents="Attached are the latest feedback analytics reports, including summaries and trends.", attachments=attachments)
        print(f"Reports sent to {email_to}")
    else:
        print("No feedback data to send.")

def main():
    schedule.every().monday.at("08:00").do(send_feedback_reports)
    print("Scheduled feedback report emails every Monday at 08:00.")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
