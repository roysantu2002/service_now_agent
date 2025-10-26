import os
import json
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet

class LogReportGenerator:
    """Generate Markdown and PDF reports from log analysis results."""

    def __init__(self, output_dir: str = "logs_reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def _generate_pdf(self, analysis_id: str, results: dict) -> str:
        pdf_path = os.path.join(self.output_dir, f"{analysis_id}.pdf")
        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = [
            Paragraph(f"<b>Log Analysis Report</b>", styles["Title"]),
            Paragraph(f"Analysis ID: {analysis_id}", styles["Normal"]),
            Paragraph(f"Generated at: {datetime.utcnow().isoformat()}", styles["Normal"]),
            Spacer(1, 12)
        ]

        # Summary section
        summary = results.get("summary") or "No summary available"
        elements.append(Paragraph("<b>Summary:</b>", styles["Heading2"]))
        elements.append(Paragraph(summary, styles["Normal"]))
        elements.append(Spacer(1, 12))

        # Findings
        findings = results.get("findings", [])
        elements.append(Paragraph("<b>Findings:</b>", styles["Heading2"]))
        if findings:
            elements.append(ListFlowable([ListItem(Paragraph(f, styles["Normal"])) for f in findings]))
        else:
            elements.append(Paragraph("No findings.", styles["Normal"]))
        elements.append(Spacer(1, 12))

        # Detailed logs
        logs = results.get("logs", [])
        elements.append(Paragraph("<b>Relevant Log Entries:</b>", styles["Heading2"]))
        if logs:
            for log in logs[:50]:  # limit for PDF readability
                elements.append(Paragraph(log, styles["Normal"]))
        else:
            elements.append(Paragraph("No logs available.", styles["Normal"]))

        doc.build(elements)
        return pdf_path

    def _generate_md(self, analysis_id: str, results: dict) -> str:
        md_path = os.path.join(self.output_dir, f"{analysis_id}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# Log Analysis Report\n\n")
            f.write(f"**Analysis ID:** {analysis_id}\n\n")
            f.write(f"**Generated at:** {datetime.utcnow().isoformat()}\n\n")

            f.write("## Summary\n")
            f.write(f"{results.get('summary', 'No summary available')}\n\n")

            f.write("## Findings\n")
            findings = results.get("findings", [])
            if findings:
                for fitem in findings:
                    f.write(f"- {fitem}\n")
            else:
                f.write("- No findings.\n")
            f.write("\n")

            f.write("## Relevant Logs\n")
            logs = results.get("logs", [])
            if logs:
                for log in logs[:100]:  # limit for readability
                    f.write(f"- {log}\n")
            else:
                f.write("- No logs available.\n")

        return md_path

    def generate_reports(self, analysis_id: str, results: dict) -> dict:
        """Generate PDF and Markdown reports and return their paths."""
        pdf_path = self._generate_pdf(analysis_id, results)
        md_path = self._generate_md(analysis_id, results)
        return {"pdf": pdf_path, "md": md_path}
