from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "Human_Factors_SWELL_Case_Study.pdf"
W, H = A4

NAVY = HexColor("#123247")
TEAL = HexColor("#247985")
TEAL_DARK = HexColor("#185763")
CORAL = HexColor("#D9574F")
ORANGE = HexColor("#E39A34")
INK = HexColor("#24333D")
MID = HexColor("#667985")
LIGHT = HexColor("#F2F6F7")
PALE_TEAL = HexColor("#E7F1F2")
PALE_CORAL = HexColor("#FBEDEC")
LINE = HexColor("#D7E1E5")
WHITE = colors.white

MARGIN = 42
CONTENT_W = W - 2 * MARGIN

CJK = "NotoSansSC"
pdfmetrics.registerFont(TTFont(CJK, str(ROOT / "assets" / "fonts" / "NotoSansSC-Regular.ttf")))
SANS = "Helvetica"
SANS_BOLD = "Helvetica-Bold"


def tokens(text: str) -> list[str]:
    pattern = r"[\u3400-\u9fff]|[A-Za-z0-9][A-Za-z0-9_./%+−–—<>=\-]*|\s+|[^\s]"
    return re.findall(pattern, text)


def wrap(text: str, font: str, size: float, width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if paragraph == "":
            lines.append("")
            continue
        current = ""
        for token in tokens(paragraph):
            proposal = current + token
            if pdfmetrics.stringWidth(proposal, font, size) <= width or not current:
                current = proposal
            else:
                lines.append(current.rstrip())
                current = token.lstrip()
        if current:
            lines.append(current.rstrip())
    return lines


def paragraph(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    width: float,
    size: float = 9.4,
    leading: float = 13.2,
    color=INK,
    font: str = CJK,
) -> float:
    c.setFillColor(color)
    c.setFont(font, size)
    for line in wrap(text, font, size, width):
        if y < 35:
            raise RuntimeError("Text overflow while drawing report page")
        c.drawString(x, y, line)
        y -= leading
    return y


def bullet_list(c, items, x, y, width, size=9.2, leading=13.2, color=INK, gap=5):
    for item in items:
        c.setFillColor(TEAL)
        c.circle(x + 3, y - 3, 2.2, stroke=0, fill=1)
        y = paragraph(c, item, x + 13, y, width - 13, size, leading, color)
        y -= gap
    return y


def label(c, text, x, y, fill=TEAL, text_color=WHITE, width=None):
    font_size = 7.2
    natural = pdfmetrics.stringWidth(text, SANS_BOLD, font_size) + 16
    width = width or natural
    c.setFillColor(fill)
    c.roundRect(x, y - 15, width, 17, 4, stroke=0, fill=1)
    c.setFillColor(text_color)
    c.setFont(SANS_BOLD, font_size)
    c.drawString(x + 8, y - 10, text)
    return width


def page_header(c, page_num: int, section: str, title: str, subtitle: str | None = None):
    c.setFillColor(NAVY)
    c.rect(0, H - 9, W, 9, stroke=0, fill=1)
    c.setFillColor(TEAL)
    c.setFont(SANS_BOLD, 7.5)
    c.drawString(MARGIN, H - 32, f"{page_num:02d}  {section.upper()}")
    c.setFillColor(NAVY)
    c.setFont(CJK, 20)
    c.drawString(MARGIN, H - 62, title)
    y = H - 82
    if subtitle:
        y = paragraph(c, subtitle, MARGIN, y, CONTENT_W, 8.4, 11.5, MID)
    return y - 8


def footer(c, page_num: int):
    c.setStrokeColor(LINE)
    c.line(MARGIN, 30, W - MARGIN, 30)
    c.setFillColor(MID)
    c.setFont(SANS, 6.8)
    c.drawString(MARGIN, 18, "SWELL-KW independent secondary analysis · DOI 10.17026/DANS-X55-69ZP")
    c.drawRightString(W - MARGIN, 18, str(page_num))


def page_end(c, page_num: int):
    footer(c, page_num)
    c.showPage()


def card(c, x, y_top, width, height, title, body, accent=TEAL, body_size=8.8):
    c.setFillColor(LIGHT)
    c.roundRect(x, y_top - height, width, height, 8, stroke=0, fill=1)
    c.setFillColor(accent)
    c.roundRect(x, y_top - height, 5, height, 2, stroke=0, fill=1)
    c.setFillColor(NAVY)
    c.setFont(CJK, 11.2)
    c.drawString(x + 15, y_top - 23, title)
    paragraph(c, body, x + 15, y_top - 42, width - 28, body_size, body_size + 3.4, INK)


def metric_card(c, x, y_top, width, value, label_text, fill=PALE_TEAL, value_color=TEAL_DARK):
    c.setFillColor(fill)
    c.roundRect(x, y_top - 62, width, 62, 7, stroke=0, fill=1)
    c.setFillColor(value_color)
    c.setFont(SANS_BOLD, 19)
    c.drawString(x + 12, y_top - 27, value)
    paragraph(c, label_text, x + 12, y_top - 43, width - 22, 7.6, 9.5, INK)


def image_box(c, path: Path, x, y_bottom, width, height):
    image = ImageReader(str(path))
    iw, ih = image.getSize()
    scale = min(width / iw, height / ih)
    dw, dh = iw * scale, ih * scale
    c.drawImage(image, x + (width - dw) / 2, y_bottom + (height - dh) / 2, dw, dh, preserveAspectRatio=True, mask="auto")


def section_rule(c, y):
    c.setStrokeColor(LINE)
    c.line(MARGIN, y, W - MARGIN, y)


def small_table(c, x, y_top, widths, rows, header_fill=NAVY, row_height=24, font_size=7.6):
    total = sum(widths)
    y = y_top
    for row_idx, row in enumerate(rows):
        fill = header_fill if row_idx == 0 else (WHITE if row_idx % 2 else LIGHT)
        c.setFillColor(fill)
        c.rect(x, y - row_height, total, row_height, stroke=0, fill=1)
        xx = x
        for col_idx, value in enumerate(row):
            c.setStrokeColor(LINE)
            c.rect(xx, y - row_height, widths[col_idx], row_height, stroke=1, fill=0)
            c.setFillColor(WHITE if row_idx == 0 else INK)
            font = SANS_BOLD if row_idx == 0 and all(ord(ch) < 128 for ch in str(value)) else CJK
            if row_idx != 0:
                font = CJK
            lines = wrap(str(value), font, font_size, widths[col_idx] - 10)[:2]
            yy = y - 9 if len(lines) == 1 else y - 7
            for line in lines:
                c.setFont(font, font_size)
                c.drawString(xx + 5, yy, line)
                yy -= 9
            xx += widths[col_idx]
        y -= row_height
    return y


def contrast(table: pd.DataFrame, outcome: str, name: str) -> pd.Series:
    return table[(table.outcome == outcome) & (table.contrast == name)].iloc[0]


def model_metric(table: pd.DataFrame, target: str, feature_set: str, metric: str) -> pd.Series:
    return table[(table.target == target) & (table.feature_set == feature_set) & (table.metric == metric)].iloc[0]


def build() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    contrasts = pd.read_csv(ROOT / "tables" / "condition_contrasts.csv")
    associations = pd.read_csv(ROOT / "tables" / "within_person_correlations.csv")
    model_summary = pd.read_csv(ROOT / "tables" / "model_summary_metrics.csv")
    comparisons = pd.read_csv(ROOT / "tables" / "model_feature_set_comparisons.csv")

    c = canvas.Canvas(str(OUT), pagesize=A4, pageCompression=1)
    c.setTitle("Human Factors Analysis of Interruptions and Time Pressure in Knowledge Work")
    c.setAuthor("Independent secondary-analysis portfolio case study")
    c.setSubject("SWELL-KW multimodal human-factors analysis")

    # 1 · Cover
    c.setFillColor(NAVY)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(TEAL)
    c.circle(W - 55, H - 58, 78, stroke=0, fill=1)
    c.setFillColor(CORAL)
    c.circle(W - 26, H - 115, 28, stroke=0, fill=1)
    label(c, "HUMAN FACTORS CASE STUDY", MARGIN, H - 58, fill=CORAL)
    c.setFillColor(WHITE)
    c.setFont(CJK, 25)
    title_lines = ["办公场景下任务中断与时间压力", "对认知负荷和交互行为的影响"]
    y = H - 125
    for line in title_lines:
        c.drawString(MARGIN, y, line)
        y -= 36
    c.setFillColor(HexColor("#B7D7DA"))
    c.setFont(SANS, 12)
    c.drawString(MARGIN, y - 4, "Human Factors Analysis of Interruptions and Time Pressure in Knowledge Work")
    c.setStrokeColor(HexColor("#446174"))
    c.line(MARGIN, y - 31, W - MARGIN, y - 31)
    y -= 62
    paragraph(
        c,
        "基于公开 SWELL-KW 数据的独立二次分析：从主观负荷、自然交互行为与生理反应出发，评估工作负荷感知及其对自适应通知管理的工程价值。",
        MARGIN,
        y,
        CONTENT_W - 38,
        11,
        17,
        WHITE,
    )
    y -= 84
    values = [("25", "participants"), ("2,688", "work minutes"), ("LOSO", "participant-disjoint"), ("3", "modalities")]
    box_w = (CONTENT_W - 30) / 4
    for i, (value, lab) in enumerate(values):
        x = MARGIN + i * (box_w + 10)
        c.setFillColor(HexColor("#1A4258"))
        c.roundRect(x, y - 72, box_w, 72, 7, stroke=0, fill=1)
        c.setFillColor(WHITE)
        c.setFont(SANS_BOLD, 17)
        c.drawString(x + 10, y - 28, value)
        c.setFillColor(HexColor("#B7D7DA"))
        c.setFont(SANS, 7.3)
        c.drawString(x + 10, y - 48, lab)
    y -= 117
    c.setFillColor(HexColor("#163A4E"))
    c.roundRect(MARGIN, y - 116, CONTENT_W, 116, 10, stroke=0, fill=1)
    c.setFillColor(ORANGE)
    c.setFont(SANS_BOLD, 8)
    c.drawString(MARGIN + 18, y - 23, "EXECUTIVE TAKEAWAY")
    paragraph(
        c,
        "邮件打断与更高心理努力、更多应用切换相伴。行为数据可提供弱但低成本的状态线索；加入生理数据后的跨参与者性能增益很小且不确定，同时 HR/HRV 缺失率达 52.9%。现有证据不足以支持自动屏蔽通知，足以支持开展一项有用户控制、按任务边界触发的前瞻验证。",
        MARGIN + 18,
        y - 43,
        CONTENT_W - 36,
        9.5,
        14.2,
        WHITE,
    )
    c.setFillColor(HexColor("#A7C4CA"))
    c.setFont(CJK, 8)
    c.drawString(MARGIN, 54, "独立二次分析作品集 · 2026")
    c.setFont(SANS, 7)
    c.drawRightString(W - MARGIN, 54, "Data: SWELL-KW · DOI 10.17026/DANS-X55-69ZP")
    c.showPage()

    # 2 · Product problem
    y = page_header(c, 2, "Product / UX Problem", "数字打断为何是人因问题", "目标是把“通知很多”转化为可测量、可验证、可落地的系统决策。")
    card(c, MARGIN, y, 159, 126, "情境", "知识工作依赖持续的目标维持与跨应用整合。邮件到达时，用户可能处于写作、搜索或整合信息的关键阶段。", TEAL)
    card(c, MARGIN + 171, y, 159, 126, "人因机制", "打断需要任务脱离、线索保持、切换与恢复；时间压力压缩可用时间，也会改变策略和节奏。", ORANGE)
    card(c, MARGIN + 342, y, 169, 126, "产品风险", "若系统在高需求阶段立即推送，可能放大恢复成本；若过度延迟，又可能造成遗漏、失控感与信任下降。", CORAL)
    y -= 153
    c.setFillColor(NAVY)
    c.setFont(CJK, 13)
    c.drawString(MARGIN, y, "从机制到工程判断")
    y -= 24
    stages = [
        ("注意与目标维持", "用户当前是否处于不可轻易中断的认知阶段？"),
        ("可观测信号", "键鼠节奏、应用切换、生理唤醒是否留下稳定模式？"),
        ("系统策略", "何时展示、延迟或聚合低优先级通知？"),
        ("体验结果", "任务表现、恢复时间、烦扰、帮助感与接受度是否改善？"),
    ]
    flow_w = 112
    for i, (t, b) in enumerate(stages):
        x = MARGIN + i * 128
        c.setFillColor(PALE_TEAL if i < 2 else LIGHT)
        c.roundRect(x, y - 104, flow_w, 104, 8, stroke=0, fill=1)
        c.setFillColor(TEAL if i < 2 else NAVY)
        c.circle(x + 17, y - 18, 10, stroke=0, fill=1)
        c.setFillColor(WHITE)
        c.setFont(SANS_BOLD, 8)
        c.drawCentredString(x + 17, y - 21, str(i + 1))
        c.setFillColor(NAVY)
        c.setFont(CJK, 9.5)
        c.drawString(x + 10, y - 43, t)
        paragraph(c, b, x + 10, y - 60, flow_w - 20, 7.6, 10.4, INK)
        if i < 3:
            c.setStrokeColor(MID)
            c.line(x + flow_w + 4, y - 52, x + flow_w + 13, y - 52)
            c.line(x + flow_w + 10, y - 49, x + flow_w + 13, y - 52)
            c.line(x + flow_w + 10, y - 55, x + flow_w + 13, y - 52)
    y -= 136
    c.setFillColor(PALE_CORAL)
    c.roundRect(MARGIN, y - 96, CONTENT_W, 96, 9, stroke=0, fill=1)
    c.setFillColor(CORAL)
    c.setFont(CJK, 12)
    c.drawString(MARGIN + 16, y - 25, "本项目的决策问题")
    paragraph(c, "仅依赖终端已有的行为数据，能否获得足够有用的负荷线索？若加入生理传感器，性能提升是否足以抵消硬件、佩戴、缺失、隐私与解释成本？", MARGIN + 16, y - 46, CONTENT_W - 32, 10.2, 15, INK)
    y -= 121
    c.setFillColor(NAVY)
    c.setFont(CJK, 11)
    c.drawString(MARGIN, y, "证据边界")
    bullet_list(c, [
        "公开数据分析能够检验信号是否存在、模型能否跨人泛化。",
        "公开数据没有操纵通知策略，因此不能证明“延迟通知一定改善体验”。",
        "产品建议必须以新的随机实验作为进入开发决策的下一道门槛。",
    ], MARGIN, y - 20, CONTENT_W, 8.8, 12.3)
    page_end(c, 2)

    # 3 · Dataset and design
    y = page_header(c, 3, "Dataset & Design", "数据与实验设计", "公开数据由 Koldijk 等采集；本作品只声明独立二次分析贡献。")
    metric_card(c, MARGIN, y, 116, "25", "名参与者；学生样本")
    metric_card(c, MARGIN + 126, y, 116, "75", "participant-condition blocks")
    metric_card(c, MARGIN + 252, y, 116, "2,688", "工作分钟记录")
    metric_card(c, MARGIN + 378, y, 133, "3", "工作条件 + 放松段")
    y -= 88
    c.setFillColor(NAVY)
    c.setFont(CJK, 13)
    c.drawString(MARGIN, y, "实验情境")
    y -= 24
    y = bullet_list(c, [
        "任务包括写报告、制作演示文稿、阅读/回复邮件和信息搜索，接近桌面知识工作。",
        "Neutral：最长 45 分钟；Time pressure：中性用时的 2/3，最长 30 分钟；Interruptions：任务中收到 8 封邮件。",
        "每个工作块前约 8 分钟自然影片用于放松；中性块固定在第一阶段，后两个压力条件被试间平衡。",
    ], MARGIN, y, CONTENT_W, 9.1, 13)
    y -= 12
    c.setFillColor(LIGHT)
    c.roundRect(MARGIN, y - 98, CONTENT_W, 98, 8, stroke=0, fill=1)
    c.setFillColor(NAVY)
    c.setFont(SANS_BOLD, 8)
    c.drawString(MARGIN + 15, y - 19, "WITHIN-PARTICIPANT ORDER")
    x0 = MARGIN + 20
    yy = y - 52
    for i, (name, fill, w) in enumerate([("Neutral", TEAL, 126), ("Interruptions / Time pressure", ORANGE, 158), ("Time pressure / Interruptions", CORAL, 158)]):
        x = x0 + [0, 144, 320][i]
        c.setFillColor(fill)
        c.roundRect(x, yy - 22, w, 30, 6, stroke=0, fill=1)
        c.setFillColor(WHITE)
        c.setFont(SANS_BOLD, 7.2)
        c.drawCentredString(x + w / 2, yy - 11, name)
        if i < 2:
            c.setStrokeColor(MID)
            c.line(x + w + 5, yy - 7, x + w + 13, yy - 7)
    c.setFillColor(MID)
    c.setFont(SANS, 6.8)
    c.drawString(MARGIN + 20, y - 86, "NIT: 13 participants     ·     NTI: 12 participants")
    y -= 123
    c.setFillColor(PALE_CORAL)
    c.roundRect(MARGIN, y - 91, CONTENT_W, 91, 8, stroke=0, fill=1)
    c.setFillColor(CORAL)
    c.setFont(CJK, 11.5)
    c.drawString(MARGIN + 15, y - 23, "关键设计限制：Neutral 固定为 block 1")
    paragraph(c, "中性与压力条件的差异无法完全排除练习、疲劳、适应、时间进程与传感器漂移。报告因此使用“条件相关差异”，不把 Neutral 对比解释为纯粹的因果效应。", MARGIN + 15, y - 44, CONTENT_W - 30, 9.2, 13.3, INK)
    y -= 118
    c.setFillColor(NAVY)
    c.setFont(CJK, 12)
    c.drawString(MARGIN, y, "数据结构与分析单位")
    rows = [
        ["层级", "记录方式", "在本分析中的用途"],
        ["主观评分", "每条件 1 次；分钟表中重复", "每人×条件保留 1 条"],
        ["行为/生理", "每分钟聚合特征", "条件模型取块均值；预测保留分钟"],
        ["验证折", "按参与者划分", "每次完整留出 1 人"],
    ]
    small_table(c, MARGIN, y - 17, [100, 185, 226], rows, row_height=28, font_size=8)
    page_end(c, 3)

    # 4 · Measures and QC
    y = page_header(c, 4, "Measures & QC", "测量、清洗与质量控制", "优先使用已处理分钟特征；所有转换与排除均写入代码和分析决策日志。")
    card(c, MARGIN, y, 159, 118, "主观", "Weighted NASA-TLX、RSME mental effort、perceived stress。评分在分钟表内重复，统计时按块去重。", TEAL)
    card(c, MARGIN + 171, y, 159, 118, "行为", "键盘、鼠标、应用切换、tab focus、错误键等。每分钟聚合；13 项进入预测。", ORANGE)
    card(c, MARGIN + 342, y, 169, 118, "生理", "HR、RMSSD、SCL。仅选择三项便于解释，但数据可用性显著低于行为记录。", CORAL)
    y -= 139
    image_box(c, ROOT / "figures" / "sensor_missingness.png", MARGIN, y - 214, CONTENT_W, 214)
    y -= 226
    c.setFillColor(NAVY)
    c.setFont(CJK, 12)
    c.drawString(MARGIN, y, "质量控制规则")
    y = bullet_list(c, [
        "将数据集缺失码 999 转为 NA；排除 Relaxation，保留 N / I / T。",
        "核对 25 人、2,688 个工作分钟、75 个 participant-condition blocks；记录源文件 SHA-256。",
        "行为计数用 log1p；RMSSD 与 SCL 用 log；结果表保留原始均值便于产品解释。",
        "预测中的中位数填补与标准化只在训练折拟合，避免测试参与者信息泄漏。",
    ], MARGIN, y - 20, CONTENT_W, 8.7, 12.1)
    c.setFillColor(PALE_TEAL)
    c.roundRect(MARGIN, y - 77, CONTENT_W, 68, 8, stroke=0, fill=1)
    paragraph(c, "为什么不用全部传感器？作品集重心是可解释的人因判断与工程取舍。面部表情和 Kinect 姿态可作为后续扩展，但首版聚焦终端行为与少量生理指标，减少特征堆叠与事后选择。", MARGIN + 15, y - 28, CONTENT_W - 30, 8.8, 12.5, INK)
    page_end(c, 4)

    # 5 · Subjective results
    y = page_header(c, 5, "Results 1", "主观负荷：心理努力比综合负荷更敏感", "混合效应模型；误差线为参与者块均值的 95% CI，细线表示同一参与者。")
    image_box(c, ROOT / "figures" / "subjective_conditions.png", MARGIN, y - 205, CONTENT_W, 205)
    y -= 214
    me_i = contrast(contrasts, "MentalEffort", "I - N")
    me_t = contrast(contrasts, "MentalEffort", "T - N")
    tlx_t = contrast(contrasts, "NasaTLX", "T - N")
    rows = [
        ["Outcome / contrast", "Estimate [95% CI]", "Holm p", "Paired dz"],
        ["Mental effort · I − N", f"{me_i.estimate:.2f} [{me_i.CI_low:.2f}, {me_i.CI_high:.2f}]", f"{me_i.p_holm_within_outcome:.3f}", f"{me_i.paired_dz:.2f}"],
        ["Mental effort · T − N", f"{me_t.estimate:.2f} [{me_t.CI_low:.2f}, {me_t.CI_high:.2f}]", f"{me_t.p_holm_within_outcome:.3f}", f"{me_t.paired_dz:.2f}"],
        ["Weighted TLX · T − N", f"{tlx_t.estimate:.2f} [{tlx_t.CI_low:.2f}, {tlx_t.CI_high:.2f}]", f"{tlx_t.p_holm_within_outcome:.3f}", f"{tlx_t.paired_dz:.2f}"],
    ]
    y = small_table(c, MARGIN, y, [168, 173, 82, 88], rows, row_height=27, font_size=7.7) - 20
    card(c, MARGIN, y, 247, 112, "可靠发现", "邮件打断与时间压力均伴随更高心理努力。Interruptions 的效应较大：dz = 0.55。", TEAL, 9.1)
    card(c, MARGIN + 264, y, 247, 112, "没有支持的说法", "Weighted NASA-TLX 与 perceived stress 未出现经校正后的清晰差异；不能把三种主观指标当成同一概念。", CORAL, 9.1)
    y -= 132
    c.setFillColor(PALE_TEAL)
    c.roundRect(MARGIN, y - 55, CONTENT_W, 55, 7, stroke=0, fill=1)
    paragraph(c, "人因解释：不同压力源可能首先改变投入的心理努力或具体需求维度，未必同步推高一个综合负荷分数。产品测量应避免只依赖单一总分。", MARGIN + 14, y - 21, CONTENT_W - 28, 8.7, 12.2, INK)
    page_end(c, 5)

    # 6 · Behavior
    y = page_header(c, 6, "Results 2", "交互行为：打断在应用切换中留下清晰痕迹", "行为模型使用参与者-条件均值；偏态计数以 log1p 建模。")
    image_box(c, ROOT / "figures" / "behavior_conditions.png", MARGIN, y - 207, CONTENT_W, 207)
    y -= 218
    app_i = contrast(contrasts, "SnAppChange", "I - N")
    key_t = contrast(contrasts, "SnKeyStrokes", "T - N")
    metric_card(c, MARGIN, y, 155, f"+{app_i.model_percent_change:.1f}%", "Interruptions 下应用切换的模型估计变化", PALE_TEAL, TEAL_DARK)
    metric_card(c, MARGIN + 169, y, 155, f"dz = {app_i.paired_dz:.2f}", "应用切换的配对标准化差异", LIGHT, NAVY)
    metric_card(c, MARGIN + 338, y, 173, f"p < .001", "两项计划对比内 Holm 校正后", PALE_CORAL, CORAL)
    y -= 88
    c.setFillColor(NAVY)
    c.setFont(CJK, 12)
    c.drawString(MARGIN, y, "解释")
    y = bullet_list(c, [
        f"应用切换从 Neutral 的 {app_i.neutral_mean_raw:.2f}/min 上升到 Interruptions 的 {app_i.condition_mean_raw:.2f}/min；95% CI（log 对比）[{app_i.CI_low:.3f}, {app_i.CI_high:.3f}]。",
        "这一模式与任务上下文频繁重定位相容，具有直接的交互设计意义：通知到达不仅占用注意，还可能推动跨应用跳转。",
        f"Time pressure 下原始平均按键数比 Neutral 高 {key_t.raw_mean_difference:.1f}/min，但 log 模型不明确（Holm p = {key_t.p_holm_within_outcome:.3f}）；不作为稳健结论。",
    ], MARGIN, y - 18, CONTENT_W, 8.8, 12.4)
    c.setFillColor(PALE_CORAL)
    c.roundRect(MARGIN, y - 70, CONTENT_W, 61, 8, stroke=0, fill=1)
    paragraph(c, "工程含义：应用切换是无需新增硬件、可在终端侧连续获得的候选信号。但它也可能反映任务类型或工作流本身，因此不能单独等同于高负荷。", MARGIN + 14, y - 29, CONTENT_W - 28, 8.9, 12.5, INK)
    page_end(c, 6)

    # 7 · Physiology
    y = page_header(c, 7, "Results 3", "生理结果：有差异，但解释成本更高", "生理均值基于可用分钟；HR/RMSSD 缺失 52.9%，Neutral 固定第一阶段。")
    image_box(c, ROOT / "figures" / "physiology_conditions.png", MARGIN, y - 206, CONTENT_W, 206)
    y -= 219
    hr_i = contrast(contrasts, "HR", "I - N")
    hr_t = contrast(contrasts, "HR", "T - N")
    scl_i = contrast(contrasts, "SCL", "I - N")
    rows = [
        ["Outcome / contrast", "Estimate [95% CI]", "Holm p", "Reading"],
        ["HR · I − N", f"{hr_i.estimate:.2f} [{hr_i.CI_low:.2f}, {hr_i.CI_high:.2f}]", "< .001", "lower"],
        ["HR · T − N", f"{hr_t.estimate:.2f} [{hr_t.CI_low:.2f}, {hr_t.CI_high:.2f}]", "< .001", "lower"],
        ["SCL · I − N", f"{scl_i.model_percent_change:+.1f}%", f"{scl_i.p_holm_within_outcome:.3f}", "uncertain"],
    ]
    y = small_table(c, MARGIN, y, [155, 171, 82, 103], rows, row_height=27, font_size=7.5) - 18
    card(c, MARGIN, y, 247, 121, "为什么不把 HR 写成压力指标？", "HR 在两个压力条件下反而更低。该方向可能涉及时序、姿势、信号质量或固定顺序，现有设计无法区分。", CORAL, 8.8)
    card(c, MARGIN + 264, y, 247, 121, "可用性也是结果", "跨人部署不仅看显著性。HR/RMSSD 近半分钟不可用，会放大填补依赖、个体校准与产品失败风险。", TEAL, 8.8)
    y -= 143
    c.setFillColor(NAVY)
    c.setFont(CJK, 11.3)
    c.drawString(MARGIN, y, "结论层级")
    bullet_list(c, [
        "可报告：不同条件下观察到 HR 与 SCL 的差异。",
        "不可报告：时间压力导致某个确定方向的生理压力反应。",
        "产品上：生理信号只有在增益稳定、可用率足够并得到明确同意时才值得加入。",
    ], MARGIN, y - 19, CONTENT_W, 8.7, 12)
    page_end(c, 7)

    # 8 · Objective measurement
    y = page_header(c, 8, "Objective Measurement", "主观体验客观化：信号链尚未闭合", "目标不是追逐显著，而是检验哪些客观信号与个体内部的负荷变化一致。")
    layers = [
        ("Subjective workload", "Mental effort · Stress · NASA-TLX", TEAL),
        ("Behavioral indicators", "Keyboard · Mouse · App switching", ORANGE),
        ("Physiological indicators", "HR · RMSSD · SCL", CORAL),
    ]
    y0 = y - 8
    for i, (t, b, fill) in enumerate(layers):
        yy = y0 - i * 82
        c.setFillColor(fill)
        c.roundRect(MARGIN + 77, yy - 52, CONTENT_W - 154, 52, 9, stroke=0, fill=1)
        c.setFillColor(WHITE)
        c.setFont(SANS_BOLD, 10)
        c.drawString(MARGIN + 94, yy - 20, t)
        c.setFont(SANS, 7.8)
        c.drawString(MARGIN + 94, yy - 38, b)
        if i < 2:
            c.setStrokeColor(MID)
            c.line(W / 2, yy - 58, W / 2, yy - 72)
            c.line(W / 2 - 4, yy - 68, W / 2, yy - 72)
            c.line(W / 2 + 4, yy - 68, W / 2, yy - 72)
    y = y0 - 257
    c.setFillColor(NAVY)
    c.setFont(CJK, 12)
    c.drawString(MARGIN, y, "参与者内相关：最强的探索性信号")
    top = associations.sort_values("p_raw").head(4)
    name_map = {"Stress": "Stress", "NasaTLX": "NASA-TLX", "MentalEffort": "Mental effort", "SnAppChange": "App switching", "SnMouseAct": "Mouse activity", "SCL": "SCL"}
    rows = [["Pair", "r_rm [cluster-bootstrap 95% CI]", "raw p", "FDR p"]]
    for _, row in top.iterrows():
        pair = f"{name_map.get(row.outcome,row.outcome)} – {name_map.get(row.feature,row.feature)}"
        rows.append([pair, f"{row.r_rm:.2f} [{row.CI_low:.2f}, {row.CI_high:.2f}]", f"{row.p_raw:.3f}", f"{row.p_fdr_within_outcome:.3f}"])
    y = small_table(c, MARGIN, y - 17, [155, 210, 70, 76], rows, row_height=27, font_size=7.4) - 18
    c.setFillColor(PALE_CORAL)
    c.roundRect(MARGIN, y - 82, CONTENT_W, 82, 8, stroke=0, fill=1)
    c.setFillColor(CORAL)
    c.setFont(CJK, 11)
    c.drawString(MARGIN + 15, y - 22, "结果判定")
    paragraph(c, "所有相关在 FDR 校正后均不明确。因此，应用切换、鼠标活动或 SCL 只能称为候选客观指标，尚不能称为已验证的负荷标志物。", MARGIN + 15, y - 43, CONTENT_W - 30, 9.2, 13, INK)
    y -= 104
    paragraph(c, "下一步测量策略：以更密集、时间对齐的主观微评定或任务边界标记建立标签；同时评估个体基线、任务类型和设备差异。", MARGIN, y, CONTENT_W, 8.9, 12.6, MID)
    page_end(c, 8)

    # 9 · Modeling
    y = page_header(c, 9, "Prediction", "跨参与者多模态建模", "严格按参与者留一验证，避免相邻分钟或同一人的数据同时出现在训练与测试中。")
    methods = [("Train", "24 participants"), ("Fit", "Impute + scale + L2 logistic"), ("Test", "1 unseen participant")]
    for i, (t, b) in enumerate(methods):
        x = MARGIN + i * 172
        c.setFillColor([TEAL, ORANGE, CORAL][i])
        c.roundRect(x, y - 58, 150, 58, 8, stroke=0, fill=1)
        c.setFillColor(WHITE)
        c.setFont(SANS_BOLD, 9)
        c.drawString(x + 12, y - 20, t)
        c.setFont(SANS, 7.5)
        c.drawString(x + 12, y - 40, b)
        if i < 2:
            c.setStrokeColor(MID)
            c.line(x + 154, y - 29, x + 167, y - 29)
    y -= 75
    image_box(c, ROOT / "figures" / "model_comparison.png", MARGIN, y - 205, CONTENT_W, 205)
    y -= 214
    target = "Neutral vs stressor"
    rows = [["Feature set", "Balanced accuracy [95% CI]", "ROC-AUC [95% CI]"]]
    for fs in ["Behavior only", "Physiology only", "Combined"]:
        ba = model_metric(model_summary, target, fs, "balanced_accuracy")
        auc = model_metric(model_summary, target, fs, "roc_auc")
        rows.append([fs, f"{ba['mean']:.3f} [{ba.CI_low:.3f}, {ba.CI_high:.3f}]", f"{auc['mean']:.3f} [{auc.CI_low:.3f}, {auc.CI_high:.3f}]"])
    y = small_table(c, MARGIN, y, [140, 187, 184], rows, row_height=27, font_size=7.7) - 17
    ba_diff = comparisons[(comparisons.target == target) & (comparisons.metric == "balanced_accuracy")].iloc[0]
    auc_diff = comparisons[(comparisons.target == target) & (comparisons.metric == "roc_auc")].iloc[0]
    c.setFillColor(PALE_TEAL)
    c.roundRect(MARGIN, y - 93, CONTENT_W, 93, 8, stroke=0, fill=1)
    c.setFillColor(TEAL_DARK)
    c.setFont(CJK, 11)
    c.drawString(MARGIN + 15, y - 22, "增量价值")
    paragraph(c, f"Combined − Behavior only：balanced accuracy +{ba_diff.mean_difference:.3f}，95% CI [{ba_diff.CI_low:.3f}, {ba_diff.CI_high:.3f}]；ROC-AUC +{auc_diff.mean_difference:.3f}，95% CI [{auc_diff.CI_low:.3f}, {auc_diff.CI_high:.3f}]。两项区间均跨 0。", MARGIN + 15, y - 43, CONTENT_W - 30, 8.8, 12.5, INK)
    y -= 112
    paragraph(c, "三分类结果同样有限：Behavior-only balanced accuracy = 0.399；Combined = 0.409。模型证明存在可泛化信息，但性能距离自动决策仍远。", MARGIN, y, CONTENT_W, 8.8, 12.5, MID)
    page_end(c, 9)

    # 10 · Engineering tradeoff
    y = page_header(c, 10, "Engineering Trade-off", "从模型性能到产品取舍", "推荐以低成本行为信号作为弱上下文输入，不把生理传感器作为首版必需条件。")
    rows = [
        ["Dimension", "Behavior only", "Physiology added"],
        ["Incremental signal", "Modest; BA 0.575", "Small/uncertain; BA +0.012"],
        ["Availability", "≈98.8% minute rows", "HR/RMSSD only 47.1%"],
        ["Hardware", "Existing terminal telemetry", "Wearable/body sensing"],
        ["Privacy", "Sensitive interaction metadata", "More sensitive body data"],
        ["User burden", "Low if on-device", "Consent, wearing, calibration"],
        ["Recommendation", "Prototype as weak signal", "Optional research arm"],
    ]
    y = small_table(c, MARGIN, y, [126, 190, 195], rows, row_height=32, font_size=7.7) - 25
    c.setFillColor(NAVY)
    c.setFont(CJK, 12)
    c.drawString(MARGIN, y, "Adaptive Notification Management · 概念策略")
    y -= 23
    states = [
        ("低需求", "正常展示普通通知", TEAL),
        ("高需求候选", "延迟低优先级通知", ORANGE),
        ("自然任务边界", "聚合展示并允许撤销", CORAL),
    ]
    for i, (state, action, fill) in enumerate(states):
        x = MARGIN + i * 173
        c.setFillColor(fill)
        c.roundRect(x, y - 83, 157, 83, 9, stroke=0, fill=1)
        c.setFillColor(WHITE)
        c.setFont(CJK, 11)
        c.drawString(x + 13, y - 25, state)
        paragraph(c, action, x + 13, y - 49, 131, 8.3, 11.5, WHITE)
    y -= 108
    card(c, MARGIN, y, 247, 115, "护栏 1 · 用户控制", "用户可关闭、设置例外、查看延迟原因并立即取回通知；高优先级与安全类通知不延迟。", TEAL, 8.8)
    card(c, MARGIN + 264, y, 247, 115, "护栏 2 · 不确定性", "模型置信度低或传感器缺失时回退到默认策略；不向用户展示“你压力很大”等心理诊断。", CORAL, 8.8)
    y -= 136
    c.setFillColor(PALE_CORAL)
    c.roundRect(MARGIN, y - 64, CONTENT_W, 64, 8, stroke=0, fill=1)
    paragraph(c, "当前结论：workload-sensitive interruption management 值得验证；现有数据不足以证明延迟策略有效，也不足以支持无监督的自动通知抑制。", MARGIN + 14, y - 25, CONTENT_W - 28, 9.3, 13.2, INK)
    page_end(c, 10)

    # 11 · Prospective experiment
    y = page_header(c, 11, "Next Experiment", "前瞻验证：2 × 3 通知策略实验", "真正回答产品问题：基于负荷与任务边界的通知策略是否改善表现与体验？")
    c.setFillColor(LIGHT)
    c.roundRect(MARGIN, y - 182, CONTENT_W, 182, 9, stroke=0, fill=1)
    c.setFillColor(NAVY)
    c.setFont(CJK, 12)
    c.drawString(MARGIN + 15, y - 24, "因子设计")
    rows = [
        ["Cognitive load", "Immediate", "Delayed", "Task-boundary"],
        ["Low", "L × I", "L × D", "L × B"],
        ["High", "H × I", "H × D", "H × B"],
    ]
    small_table(c, MARGIN + 15, y - 40, [121, 115, 115, 115], rows, row_height=33, font_size=8)
    paragraph(c, "随机化通知策略；任务内容与通知优先级预先平衡。系统检测器可以作为第二阶段因素加入，避免把“策略有效性”与“检测准确性”混为同一问题。", MARGIN + 15, y - 150, CONTENT_W - 30, 8.4, 11.8, MID)
    y -= 205
    card(c, MARGIN, y, 247, 156, "主要因变量", "• primary task RT / completion time\n• error rate / task quality\n• interruption recovery time\n• NASA-TLX / mental effort", TEAL, 8.8)
    card(c, MARGIN + 264, y, 247, 156, "UX 与接受度", "• annoyance\n• perceived helpfulness\n• sense of control\n• acceptance / opt-out\n• missed urgent information", ORANGE, 8.8)
    y -= 180
    c.setFillColor(NAVY)
    c.setFont(CJK, 12)
    c.drawString(MARGIN, y, "分析与成功标准")
    y = bullet_list(c, [
        "按参与者和任务建混合效应模型，检验 Load × Notification Policy；预注册主要对比：boundary vs immediate、delayed vs immediate。",
        "效应必须同时满足：主任务恢复/错误改善，烦扰降低，且关键通知遗漏不增加；报告效应量与置信区间。",
        "在正式实验前进行模拟或先导研究确定样本量；模型阈值和通知优先级固定后再测试。",
        "若检测器参与决策，单独报告检测错误造成的体验后果，特别是错误延迟与错误打断。",
    ], MARGIN, y - 19, CONTENT_W, 8.7, 12.2)
    c.setFillColor(PALE_TEAL)
    c.roundRect(MARGIN, y - 65, CONTENT_W, 57, 8, stroke=0, fill=1)
    paragraph(c, "决策门槛：只有当策略收益在跨参与者、跨任务与真实通知优先级下稳定，才进入长期场景测试。", MARGIN + 14, y - 30, CONTENT_W - 28, 9, 12.5, INK)
    page_end(c, 11)

    # 12 · Reproducibility and limitations
    y = page_header(c, 12, "Reproducibility", "可追溯性、贡献与限制", "所有图表均由同一分析管线生成；原始数据来源、处理规则和随机种子均已记录。")
    c.setFillColor(NAVY)
    c.setFont(CJK, 12)
    c.drawString(MARGIN, y, "本人独立完成的部分")
    y = bullet_list(c, [
        "产品问题与研究问题定义；变量选择与数据质量控制。",
        "混合效应模型、计划对比、参与者内关联与多重比较。",
        "按参与者 LOSO 的预测建模、模态比较与工程取舍。",
        "可视化、人因解释、产品策略边界与前瞻实验设计。",
    ], MARGIN, y - 18, CONTENT_W, 8.7, 11.8, gap=3)
    c.setFillColor(NAVY)
    c.setFont(CJK, 12)
    c.drawString(MARGIN, y - 2, "复现包")
    y -= 22
    rows = [
        ["Artifact", "Role"],
        ["01_data_cleaning.ipynb", "结构验证、缺失、去重、块级聚合"],
        ["02_human_factors_analysis.ipynb", "混合模型、对比、相关、图"],
        ["03_workload_model.ipynb", "LOSO 模型与工程比较"],
        ["tables/*.csv", "报告数字的直接来源"],
        ["qc_summary.json", "SHA-256、行数、顺序、缺失率"],
    ]
    y = small_table(c, MARGIN, y, [190, 321], rows, row_height=25, font_size=7.6) - 17
    c.setFillColor(NAVY)
    c.setFont(CJK, 12)
    c.drawString(MARGIN, y, "限制")
    y = bullet_list(c, [
        "Neutral 固定第一阶段；条件与顺序/时间进程无法完全分离。",
        "N = 25，学生样本；实验室桌面任务与当前终端生态存在差距。",
        "主观评分为块级标签，不能充当每分钟的高负荷真值。",
        "生理缺失高；填补后的预测性能不能代表稳定在线可用性。",
        "没有操纵通知策略，无法得出延迟通知改善体验的因果结论。",
    ], MARGIN, y - 18, CONTENT_W, 8.4, 11.5, gap=2)
    section_rule(c, y - 2)
    y -= 19
    c.setFillColor(NAVY)
    c.setFont(CJK, 10.5)
    c.drawString(MARGIN, y, "数据与主要参考")
    y -= 16
    refs = [
        "SWELL-KW open dataset. DOI: 10.17026/DANS-X55-69ZP.",
        "Koldijk, S., Sappelli, M., Verberne, S., Neerincx, M. A., & Kraaij, W. (2014). The SWELL Knowledge Work Dataset for Stress and User Modeling Research. ICMI. DOI: 10.1145/2663204.2663257.",
        "Koldijk, S., Neerincx, M. A., & Kraaij, W. (2018). Detecting Work Stress in Offices by Combining Unobtrusive Sensors. IEEE Transactions on Affective Computing. DOI: 10.1109/TAFFC.2016.2610975.",
        "Hart, S. G., & Staveland, L. E. (1988). Development of NASA-TLX. DOI: 10.1016/S0166-4115(08)62386-9.",
    ]
    for ref in refs:
        y = paragraph(c, ref, MARGIN, y, CONTENT_W, 6.8, 9, MID, CJK)
        y -= 3
    c.setFillColor(PALE_TEAL)
    c.roundRect(MARGIN, 42, CONTENT_W, 48, 7, stroke=0, fill=1)
    paragraph(c, "声明：I conducted an independent secondary human-factors analysis using the publicly available SWELL-KW dataset. 本作品不声称参与原始实验招募或数据采集。", MARGIN + 12, 72, CONTENT_W - 24, 7.7, 10.5, INK)
    page_end(c, 12)

    c.save()
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
