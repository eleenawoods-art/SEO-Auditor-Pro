from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether
)


def _safe(value, default=""):
    if value is None:
        return default
    return str(value)


def _severity_color(severity):
    s = _safe(severity).lower()
    if s == "critical":
        return colors.HexColor("#dc2626")
    if s == "warning":
        return colors.HexColor("#d97706")
    if s == "passed":
        return colors.HexColor("#15803d")
    return colors.HexColor("#475569")


def _page_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#e2e8f0"))
    canvas.line(18 * mm, 14 * mm, 192 * mm, 14 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(18 * mm, 9 * mm, "Agency SEO Auditor v6.0")
    canvas.drawRightString(192 * mm, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _box(title, value, width=84 * mm):
    data = [
        [Paragraph(_safe(title), ParagraphStyle(
            "box_title", fontName="Helvetica-Bold", fontSize=8,
            textColor=colors.HexColor("#64748b"), leading=10
        ))],
        [Paragraph(_safe(value) or "—", ParagraphStyle(
            "box_value", fontName="Helvetica-Bold", fontSize=12,
            textColor=colors.HexColor("#111827"), leading=15
        ))],
    ]
    t = Table(data, colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#dbe3ee")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def build_pdf_report(report_data, *args, **kwargs):
    """Create a client-ready PDF with high-contrast, light report boxes.

    Accepts the v6 report-data dictionary used by app.py. Extra positional
    or keyword arguments are tolerated for backward compatibility.
    """
    if not isinstance(report_data, dict):
        report_data = {}

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title="SEO Audit Report",
        author="Agency SEO Auditor v6.0",
    )

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=24, leading=29, textColor=colors.HexColor("#0f172a"),
        alignment=TA_LEFT, spaceAfter=5
    )
    subtitle = ParagraphStyle(
        "Subtitle", parent=styles["Normal"], fontName="Helvetica",
        fontSize=10.5, leading=15, textColor=colors.HexColor("#475569"),
        spaceAfter=12
    )
    h1 = ParagraphStyle(
        "H1", parent=styles["Heading1"], fontName="Helvetica-Bold",
        fontSize=17, leading=21, textColor=colors.HexColor("#0f172a"),
        spaceBefore=8, spaceAfter=9
    )
    h2 = ParagraphStyle(
        "H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=12.5, leading=16, textColor=colors.HexColor("#1e293b"),
        spaceBefore=7, spaceAfter=5
    )
    body = ParagraphStyle(
        "Body", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=9.5, leading=14, textColor=colors.HexColor("#1f2937"),
        spaceAfter=5
    )
    small = ParagraphStyle(
        "Small", parent=body, fontSize=8.2, leading=11,
        textColor=colors.HexColor("#475569")
    )
    white_small = ParagraphStyle(
        "WhiteSmall", parent=small, textColor=colors.white
    )

    agency = _safe(report_data.get("agency_name"), "Agency SEO Auditor")
    agency_website = _safe(report_data.get("agency_website"))
    agency_email = _safe(report_data.get("agency_email"))
    client = _safe(report_data.get("client_name"), "Client")
    client_website = _safe(report_data.get("client_website"))
    audit_url = _safe(report_data.get("audit_url"))
    score = _safe(report_data.get("score"), "0")
    score_label = _safe(report_data.get("score_label"), "Good")
    critical = _safe(report_data.get("critical"), "0")
    warnings = _safe(report_data.get("warnings"), "0")
    passed = _safe(report_data.get("passed"), "0")
    aggregated = report_data.get("aggregated") or []
    results = report_data.get("results") or []
    pages = report_data.get("pages") or []
    broken_links = report_data.get("broken_links") or []
    technical = report_data.get("technical") or {}

    story = []

    # Header — deliberately light/white, never black text on black background.
    header = Table([
        [Paragraph("AGENCY SEO AUDITOR", white_small),
         Paragraph("CLIENT SEO REPORT", ParagraphStyle(
             "HeaderRight", parent=white_small, alignment=2,
             fontName="Helvetica-Bold"
         ))]
    ], colWidths=[87 * mm, 87 * mm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#2563eb")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [header, Spacer(1, 8), Paragraph("SEO Audit Report", title),
              Paragraph("Professional website health analysis and prioritized SEO recommendations.", subtitle)]

    info = Table([
        [_box("AGENCY", agency), _box("CLIENT / COMPANY", client)],
        [_box("AGENCY WEBSITE", agency_website), _box("CLIENT WEBSITE", client_website or audit_url)],
        [_box("AGENCY EMAIL", agency_email), _box("AUDITED URL", audit_url)],
    ], colWidths=[88 * mm, 88 * mm], hAlign="LEFT")
    info.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [info, Spacer(1, 12)]

    story.append(Paragraph("Executive Summary", h1))
    score_table = Table([
        [Paragraph("OVERALL SEO SCORE", small), Paragraph("CRITICAL", small),
         Paragraph("WARNINGS", small), Paragraph("PASSED", small)],
        [Paragraph(f"<b>{score}/100</b><br/><font size='9'>{score_label}</font>",
                   ParagraphStyle("Score", parent=body, fontSize=20, leading=23,
                                  textColor=colors.HexColor("#2563eb"))),
         Paragraph(f"<b>{critical}</b>", ParagraphStyle("Crit", parent=body, fontSize=17, textColor=colors.HexColor("#dc2626"))),
         Paragraph(f"<b>{warnings}</b>", ParagraphStyle("Warn", parent=body, fontSize=17, textColor=colors.HexColor("#d97706"))),
         Paragraph(f"<b>{passed}</b>", ParagraphStyle("Pass", parent=body, fontSize=17, textColor=colors.HexColor("#15803d")))],
    ], colWidths=[44 * mm] * 4)
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#dbe3ee")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [score_table, Spacer(1, 10)]

    story.append(Paragraph("Prioritized SEO Findings", h1))
    finding_items = [x for x in aggregated if isinstance(x, dict)]
    if not finding_items:
        finding_items = [x for x in results if isinstance(x, dict)]

    for item in finding_items[:12]:
        severity = _safe(item.get("severity"), "Warning")
        issue = _safe(item.get("issue"), item.get("message", "SEO issue"))
        category = _safe(item.get("category"), "SEO")
        recommendation = _safe(item.get("recommendation"), item.get("fix", "Review and fix this issue."))
        occurrence = _safe(item.get("occurrences"), "1")
        affected = item.get("affected_pages")
        if affected is None:
            pgs = item.get("pages") or []
            affected = len(pgs) if isinstance(pgs, (list, tuple, set)) else 0

        sev = _severity_color(severity)
        content = [
            Paragraph(f"<b>{_safe(severity).upper()}</b>  {_safe(issue)}", ParagraphStyle(
                "IssueTitle", parent=body, fontName="Helvetica-Bold", fontSize=10.5,
                textColor=sev, leading=14
            )),
            Paragraph(f"{category}  •  {occurrence} occurrence(s)  •  {affected} affected page(s)", small),
            Paragraph(f"<b>Recommended Fix:</b> {_safe(recommendation)}", body),
        ]
        box = Table([[content]], colWidths=[176 * mm])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#dbe3ee")),
            ("LINEBEFORE", (0, 0), (0, -1), 4, sev),
            ("LEFTPADDING", (0, 0), (-1, -1), 11),
            ("RIGHTPADDING", (0, 0), (-1, -1), 11),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story += [box, Spacer(1, 6)]

    story.append(PageBreak())
    story.append(Paragraph("Affected URLs", h1))
    url_rows = [[Paragraph("URL", ParagraphStyle("TH", parent=body, fontName="Helvetica-Bold", textColor=colors.white)),
                 Paragraph("Status", ParagraphStyle("TH2", parent=body, fontName="Helvetica-Bold", textColor=colors.white))]]
    for p in pages[:50]:
        if isinstance(p, dict):
            url = p.get("URL") or p.get("url") or ""
            status = p.get("Status") or p.get("status") or p.get("status_code") or ""
        else:
            url, status = _safe(p), ""
        url_rows.append([Paragraph(_safe(url), small), Paragraph(_safe(status), small)])
    if len(url_rows) == 1:
        url_rows.append([Paragraph("No page data available.", small), Paragraph("", small)])
    urls_table = Table(url_rows, colWidths=[145 * mm, 31 * mm], repeatRows=1)
    urls_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbe3ee")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [urls_table, Spacer(1, 12)]

    story.append(Paragraph("Broken Links", h1))
    if broken_links:
        rows = [[Paragraph("URL", ParagraphStyle("BTH", parent=body, fontName="Helvetica-Bold", textColor=colors.white)),
                 Paragraph("Status", ParagraphStyle("BTH2", parent=body, fontName="Helvetica-Bold", textColor=colors.white)),
                 Paragraph("State", ParagraphStyle("BTH3", parent=body, fontName="Helvetica-Bold", textColor=colors.white))]]
        for link in broken_links[:100]:
            if isinstance(link, dict):
                url = link.get("URL") or link.get("url") or ""
                status = link.get("Status") or link.get("status") or ""
                state = link.get("State") or link.get("state") or link.get("Error") or ""
            else:
                url, status, state = _safe(link), "", ""
            rows.append([Paragraph(_safe(url), small), Paragraph(_safe(status), small), Paragraph(_safe(state), small)])
        bt = Table(rows, colWidths=[112 * mm, 24 * mm, 40 * mm], repeatRows=1)
        bt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbe3ee")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(bt)
    else:
        story.append(Paragraph("No broken-link records were returned for this audit.", body))

    story += [Spacer(1, 12), Paragraph("Technical Checks", h1)]
    if isinstance(technical, dict) and technical:
        tech_rows = []
        for key, value in list(technical.items())[:40]:
            tech_rows.append([Paragraph(_safe(key), body), Paragraph(_safe(value), small)])
        tt = Table(tech_rows, colWidths=[60 * mm, 116 * mm])
        tt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbe3ee")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(tt)
    else:
        story.append(Paragraph("No additional technical data available.", body))

    story += [Spacer(1, 16), Paragraph(
        "This report was generated by Agency SEO Auditor v6.0. Recommendations should be reviewed in the context of the client's website and business goals.",
        small
    )]

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()
