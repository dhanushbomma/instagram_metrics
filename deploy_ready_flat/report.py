"""Report generation module for Excel (.xlsx) and PDF exports with accurate views, likes, comments, and shares."""

import io
import datetime
from typing import List, Dict, Any
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_excel_report(posts: List[Dict[str, Any]], summary_stats: Dict[str, Any]) -> bytes:
    """
    Generates a professionally styled multi-sheet Excel (.xlsx) workbook containing:
    1. 'Performance Dashboard': Summary KPI blocks (Views, Likes, Comments, Shares) and full results table.
    2. 'Top 5 by Views': Top 5 posts ranked by views with accurate shares count.
    """
    wb = openpyxl.Workbook()

    # Style definitions
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    kpi_title_fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
    kpi_title_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    kpi_val_font = Font(name="Calibri", size=14, bold=True, color="1E1B4B")
    data_font = Font(name="Calibri", size=10)
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")
    thin_border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0")
    )

    # ---------------- SHEET 1: Executive Summary ----------------
    ws_summary = wb.active
    ws_summary.title = "Executive Summary"
    ws_summary.sheet_view.showGridLines = False

    ws_summary["A1"] = "INSTAGRAM PERFORMANCE REPORT"
    ws_summary["A1"].font = Font(name="Calibri", size=18, bold=True, color="0F172A")
    ws_summary["A2"] = "Client-ready executive summary for performance review"
    ws_summary["A2"].font = Font(name="Calibri", size=10, italic=True, color="475569")
    ws_summary["A4"] = f"Report Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
    ws_summary["A4"].font = Font(name="Calibri", size=10, bold=True, color="1E293B")
    ws_summary["A5"] = "Metric standard: videoPlayCount (Plays) for Reels and video posts"
    ws_summary["A5"].font = Font(name="Calibri", size=9, color="475569")

    summary_kpis = [
        ("A8", "Total Posts", summary_stats.get("total_posts", 0)),
        ("D8", "Total Views", f"{summary_stats.get('total_views', 0):,}"),
        ("A11", "Total Likes", f"{summary_stats.get('total_likes', 0):,}"),
        ("D11", "Total Comments", f"{summary_stats.get('total_comments', 0):,}"),
        ("A14", "Total Shares", f"{summary_stats.get('total_shares', 0):,}"),
    ]
    for cell_ref, title, value in summary_kpis:
        ws_summary[cell_ref] = title
        ws_summary[cell_ref].font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        ws_summary[cell_ref].fill = PatternFill(start_color="312E81", end_color="312E81", fill_type="solid")
        ws_summary[cell_ref].alignment = align_center

        value_cell = ws_summary[cell_ref.replace('A', 'B') if cell_ref.startswith('A') else cell_ref.replace('D', 'E')]
        value_cell.value = value
        value_cell.font = Font(name="Calibri", size=14, bold=True, color="1E1B4B")
        value_cell.fill = PatternFill(start_color="EEF2FF", end_color="EEF2FF", fill_type="solid")
        value_cell.alignment = align_center

    ws_summary["A18"] = "Executive Highlights"
    ws_summary["A18"].font = Font(name="Calibri", size=11, bold=True, color="0F172A")
    exec_points = [
        "Performance report generated from current Instagram dataset and cache-aware fetches.",
        "Reel and video views are normalized to public plays for consistent comparison.",
        "Hidden likes are reported as Hidden rather than forced to zero for accuracy.",
        "All metrics are organized for stakeholder-ready export and review."
    ]
    for idx, line in enumerate(exec_points, start=19):
        ws_summary[f"A{idx}"] = f"• {line}"
        ws_summary[f"A{idx}"].font = Font(name="Calibri", size=9, color="334155")

    ws_summary["H1"] = "Report Notes"
    ws_summary["H1"].font = Font(name="Calibri", size=11, bold=True, color="0F172A")
    ws_summary["H3"] = "This report is designed for executive review and client-ready sharing."
    ws_summary["H3"].font = Font(name="Calibri", size=9, color="475569")

    for col in ["A", "B", "C", "D", "E", "F", "G", "H"]:
        ws_summary.column_dimensions[col].width = 18 if col in ["A", "B", "D", "E"] else 16

    # ---------------- SHEET 2: All Posts & KPIs ----------------
    ws1 = wb.create_sheet("Performance Dashboard")
    ws1.sheet_view.showGridLines = True

    # Title block
    ws1["A1"] = "INSTAGRAM STATS REPORT"
    ws1["A1"].font = Font(name="Calibri", size=16, bold=True, color="1E293B")
    ws1["A2"] = f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')} | Primary Reel View standard: videoPlayCount (Plays)"
    ws1["A2"].font = Font(name="Calibri", size=9, italic=True, color="64748B")

    # KPI summary boxes (Rows 4-5) across 5 metrics
    kpis = [
        ("Total Posts", summary_stats.get("total_posts", 0), "A", "B"),
        ("Total Views", f"{summary_stats.get('total_views', 0):,}", "C", "D"),
        ("Total Likes", f"{summary_stats.get('total_likes', 0):,}", "E", "F"),
        ("Total Comments", f"{summary_stats.get('total_comments', 0):,}", "G", "H"),
        ("Total Shares", f"{summary_stats.get('total_shares', 0):,}", "I", "J"),
    ]

    for title, val, col1, col2 in kpis:
        cell_header = f"{col1}4"
        cell_val = f"{col1}5"
        ws1.merge_cells(f"{col1}4:{col2}4")
        ws1.merge_cells(f"{col1}5:{col2}5")

        ws1[cell_header] = title
        ws1[cell_header].fill = kpi_title_fill
        ws1[cell_header].font = kpi_title_font
        ws1[cell_header].alignment = align_center

        ws1[cell_val] = val
        ws1[cell_val].font = kpi_val_font
        ws1[cell_val].alignment = align_center
        ws1[cell_val].fill = PatternFill(start_color="EEF2FF", end_color="EEF2FF", fill_type="solid")

    # Table Headers at Row 7
    columns = [
        ("Status", 14, align_center),
        ("Username", 16, align_left),
        ("Post Type", 12, align_center),
        ("Views (Plays)", 14, align_right),
        ("Likes", 14, align_right),
        ("Comments", 14, align_right),
        ("Shares", 14, align_right),
        ("Posted At", 18, align_center),
        ("Last Updated", 20, align_center),
        ("Instagram URL", 45, align_left),
    ]

    for col_idx, (col_name, col_width, alignment) in enumerate(columns, start=1):
        cell = ws1.cell(row=7, column=col_idx, value=col_name)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = alignment
        ws1.column_dimensions[get_column_letter(col_idx)].width = col_width

    # Populate Data Rows
    current_row = 8
    for post in posts:
        # Format Views
        if post.get("post_type") in ["Photo", "Carousel"]:
            views_val = "N/A"
        elif post.get("views") is not None:
            views_val = post["views"]
        else:
            views_val = "N/A"

        # Format Likes
        if post.get("status") == "Hidden likes" or post.get("likes") is None:
            likes_val = "Hidden"
        else:
            likes_val = post["likes"]

        # Format Comments
        comments_val = post.get("comments") if post.get("comments") is not None else "N/A"

        # Format Shares
        shares_val = post.get("shares") if post.get("shares") is not None else "N/A"

        row_values = [
            post.get("status", "Unknown"),
            post.get("username", "N/A"),
            post.get("post_type", "Unknown"),
            views_val,
            likes_val,
            comments_val,
            shares_val,
            post.get("posted_at", "N/A"),
            str(post.get("fetched_at", ""))[:19].replace("T", " "),
            post.get("url", "")
        ]

        for col_idx, val in enumerate(row_values, start=1):
            cell = ws1.cell(row=current_row, column=col_idx, value=val)
            cell.font = data_font
            cell.border = thin_border
            align = columns[col_idx - 1][2]
            cell.alignment = align

            if isinstance(val, (int, float)):
                cell.number_format = "#,##0"

            if col_idx == 1:
                if val == "Success":
                    cell.fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
                    cell.font = Font(name="Calibri", size=10, color="166534", bold=True)
                elif val == "Hidden likes":
                    cell.fill = PatternFill(start_color="FEF9C3", end_color="FEF9C3", fill_type="solid")
                    cell.font = Font(name="Calibri", size=10, color="854D0E", bold=True)
                else:
                    cell.fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
                    cell.font = Font(name="Calibri", size=10, color="991B1B", bold=True)

        current_row += 1

    # ---------------- SHEET 3: Top 5 Posts by Views ----------------
    ws2 = wb.create_sheet(title="Top 5 by Views")
    ws2.sheet_view.showGridLines = True

    ws2["A1"] = "TOP 5 POSTS BY VIEWS"
    ws2["A1"].font = Font(name="Calibri", size=14, bold=True, color="1E293B")
    ws2["A2"] = "Ranked by Play Count / Video Views (Reels and Videos)"
    ws2["A2"].font = Font(name="Calibri", size=9, italic=True, color="64748B")

    top_columns = [
        ("Rank", 8, align_center),
        ("Username", 16, align_left),
        ("Type", 12, align_center),
        ("Views", 16, align_right),
        ("Likes", 14, align_right),
        ("Comments", 14, align_right),
        ("Shares", 14, align_right),
        ("URL", 50, align_left),
    ]

    for col_idx, (col_name, col_width, align) in enumerate(top_columns, start=1):
        cell = ws2.cell(row=4, column=col_idx, value=col_name)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = align
        ws2.column_dimensions[get_column_letter(col_idx)].width = col_width

    posts_with_views = [p for p in posts if p.get("views") is not None and isinstance(p.get("views"), (int, float))]
    sorted_posts = sorted(posts_with_views, key=lambda x: x["views"], reverse=True)[:5]

    for rank, post in enumerate(sorted_posts, start=1):
        r_row = 4 + rank
        likes_val = "Hidden" if (post.get("status") == "Hidden likes" or post.get("likes") is None) else post["likes"]
        shares_val = post.get("shares") if post.get("shares") is not None else "N/A"
        vals = [
            f"#{rank}",
            post.get("username", "N/A"),
            post.get("post_type", "Reel"),
            post["views"],
            likes_val,
            post.get("comments", "N/A"),
            shares_val,
            post.get("url", "")
        ]
        for c_idx, val in enumerate(vals, start=1):
            cell = ws2.cell(row=r_row, column=c_idx, value=val)
            cell.font = data_font
            cell.border = thin_border
            cell.alignment = top_columns[c_idx - 1][2]
            if isinstance(val, (int, float)):
                cell.number_format = "#,##0"

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def generate_pdf_report(posts: List[Dict[str, Any]], summary_stats: Dict[str, Any]) -> bytes:
    """Generates a styled landscape PDF report with accurate KPIs, Top 5 table, and full records."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=2
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748B"),
        spaceAfter=12
    )
    section_title = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=10,
        spaceAfter=6
    )
    cell_bold = ParagraphStyle(
        "CellBold",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0F172A")
    )
    url_style = ParagraphStyle(
        "UrlStyle",
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#2563EB")
    )

    story = []

    # Title & Header
    story.append(Paragraph("Instagram Stats Dashboard Report", title_style))
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    story.append(Paragraph(f"Generated at: {now_str} | Metric standard: videoPlayCount (Plays)", subtitle_style))

    story.append(Paragraph("Executive Summary", section_title))
    summary_lines = [
        f"Total posts analyzed: {summary_stats.get('total_posts', 0)}",
        f"Total views: {summary_stats.get('total_views', 0):,}",
        f"Total likes: {summary_stats.get('total_likes', 0):,}",
        f"Total comments: {summary_stats.get('total_comments', 0):,}",
        f"Total shares: {summary_stats.get('total_shares', 0):,}",
    ]
    for line in summary_lines:
        story.append(Paragraph(f"• {line}", styles["Normal"]))
    story.append(Spacer(1, 8))

    # Summary KPI Table (5 columns)
    kpi_data = [
        [
            Paragraph("<b>Total Posts</b>", cell_bold),
            Paragraph("<b>Total Views</b>", cell_bold),
            Paragraph("<b>Total Likes</b>", cell_bold),
            Paragraph("<b>Total Comments</b>", cell_bold),
            Paragraph("<b>Total Shares</b>", cell_bold),
        ],
        [
            Paragraph(f"<font size=12><b>{summary_stats.get('total_posts', 0)}</b></font>", cell_bold),
            Paragraph(f"<font size=12><b>{summary_stats.get('total_views', 0):,}</b></font>", cell_bold),
            Paragraph(f"<font size=12><b>{summary_stats.get('total_likes', 0):,}</b></font>", cell_bold),
            Paragraph(f"<font size=12><b>{summary_stats.get('total_comments', 0):,}</b></font>", cell_bold),
            Paragraph(f"<font size=12><b>{summary_stats.get('total_shares', 0):,}</b></font>", cell_bold),
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[145, 145, 145, 145, 145])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F8FAFC")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 10))

    # Top 5 Highlights
    posts_with_views = [p for p in posts if p.get("views") is not None and isinstance(p.get("views"), (int, float))]
    sorted_top = sorted(posts_with_views, key=lambda x: x["views"], reverse=True)[:5]
    if sorted_top:
        story.append(Paragraph("Top 5 Posts by Views", section_title))
        top_data = [
            ["Rank", "Username", "Type", "Views", "Likes", "Comments", "Shares", "Post URL"]
        ]
        for rank, p in enumerate(sorted_top, start=1):
            likes_str = "Hidden" if (p.get("status") == "Hidden likes" or p.get("likes") is None) else f"{p['likes']:,}"
            shares_str = f"{p['shares']:,}" if p.get("shares") is not None else "N/A"
            top_data.append([
                f"#{rank}",
                p.get("username", "N/A"),
                p.get("post_type", "Reel"),
                f"{p['views']:,}",
                likes_str,
                f"{p.get('comments', 0):,}" if p.get("comments") is not None else "N/A",
                shares_str,
                Paragraph(p.get("url", ""), url_style)
            ])

        top_table = Table(top_data, colWidths=[35, 100, 55, 75, 70, 70, 65, 255])
        top_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4338CA")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (3, 0), (6, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ]))
        story.append(top_table)
        story.append(Spacer(1, 12))

    # Full Data Table
    story.append(Paragraph("Complete Posts Table", section_title))
    table_header = ["Status", "Username", "Type", "Views", "Likes", "Comments", "Shares", "Posted At", "URL"]
    table_data = [table_header]

    for p in posts:
        if p.get("post_type") in ["Photo", "Carousel"]:
            views_str = "N/A"
        elif p.get("views") is not None:
            views_str = f"{p['views']:,}"
        else:
            views_str = "N/A"

        if p.get("status") == "Hidden likes" or p.get("likes") is None:
            likes_str = "Hidden"
        else:
            likes_str = f"{p['likes']:,}"

        comments_str = f"{p.get('comments', 0):,}" if p.get("comments") is not None else "N/A"
        shares_str = f"{p.get('shares', 0):,}" if p.get("shares") is not None else "N/A"

        table_data.append([
            p.get("status", "Unknown"),
            p.get("username", "N/A"),
            p.get("post_type", "Unknown"),
            views_str,
            likes_str,
            comments_str,
            shares_str,
            p.get("posted_at", "N/A"),
            Paragraph(p.get("url", ""), url_style)
        ])

    posts_table = Table(table_data, colWidths=[75, 90, 55, 65, 65, 60, 60, 85, 170], repeatRows=1)
    posts_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (2, -1), "LEFT"),
        ("ALIGN", (3, 0), (6, -1), "RIGHT"),
        ("ALIGN", (7, 0), (7, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
    ]))

    story.append(posts_table)
    doc.build(story)
    return buffer.getvalue()
