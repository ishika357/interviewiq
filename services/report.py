"""PDF report generation with ReportLab (pure Python, no system dependencies)."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PURPLE = colors.HexColor("#8667F5")


def build_pdf(interview: dict, turns: list[dict], user_name: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"InterviewIQ report #{interview['id']}", author="InterviewIQ")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=PURPLE, fontSize=22, alignment=0)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=colors.HexColor("#222244"), spaceBefore=10)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=13)
    small = ParagraphStyle("s", parent=body, fontSize=8.5, textColor=colors.HexColor("#555566"))

    def p(text, style=body):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)

    rep = interview.get("report") or {}
    avg = rep.get("averages", {})
    story = [Paragraph("InterviewIQ Interview Report", h1),
             p(f"{user_name} | {interview['role']} | {interview['difficulty']} | {(interview.get('completed_at') or '')[:16]}", small),
             p(f"Evaluation engine: {rep.get('engine', 'heuristic')}. Scores are 0-100 and computed from the candidate's recorded answers.", small), Spacer(1, 6)]
    t = Table([["Overall", "Technical", "Communication", "Relevance", "Answer quality"],
               [f"{avg.get(k, 0):.0f}" for k in ("overall", "technical", "communication", "relevance", "quality")]], hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), PURPLE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTSIZE", (0, 1), (-1, 1), 16), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                           ("BOX", (0, 0), (-1, -1), 0.5, colors.grey), ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                           ("TOPPADDING", (0, 1), (-1, 1), 8), ("BOTTOMPADDING", (0, 1), (-1, 1), 8)]))
    story += [t]
    for title, items in (("Strengths", rep.get("strengths")), ("Weaknesses", rep.get("weaknesses")), ("Recommendations", rep.get("recommendations"))):
        story.append(Paragraph(title, h2))
        story += [p("- " + i) for i in (items or ["None identified."])]
    story.append(Paragraph("Question-wise feedback", h2))
    for tr in turns:
        ev = tr.get("eval") or {}
        story.append(p(f"Q{tr['idx'] + 1}. {tr['question']}", ParagraphStyle("q", parent=body, fontName="Helvetica-Bold")))
        story.append(p(f"Score {tr['overall']:.0f}/100 (technical {tr['technical']:.0f}, relevance {tr['relevance']:.0f}, quality {tr['quality']:.0f}, communication {tr['communication']:.0f})", small))
        story.append(p("Your answer: " + (tr.get("answer_text") or "(skipped)")))
        story.append(p("Feedback: " + ev.get("feedback", "")))
        if ev.get("improved_answer"):
            story.append(p(f"Suggested answer ({ev.get('improved_answer_source', '')}): {ev['improved_answer']}", small))
        story.append(Spacer(1, 6))
    rm = rep.get("roadmap") or {}
    if rm.get("days"):
        story.append(Paragraph("7-day learning roadmap", h2))
        for d in rm["days"]:
            story.append(p(f"{d['day']}: {d['title']}", ParagraphStyle("d", parent=body, fontName="Helvetica-Bold")))
            story += [p("- " + x, small) for x in d["tasks"]]
    doc.build(story)
    return buf.getvalue()
