"""注文依頼書 / 加工依頼書 の PDF 生成（reportlab）。
日本語は reportlab 同梱の CID フォント（HeiseiKakuGo-W5）を使うため外部フォント不要。
"""
from io import BytesIO

from reportlab.lib.pagesizes import A5, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

FONT = "HeiseiKakuGo-W5"
_registered = False


def _ensure_font():
    global _registered
    if not _registered:
        pdfmetrics.registerFont(UnicodeCIDFont(FONT))
        _registered = True


def _ymd(d):
    return f"{d.year}年{d.month}月{d.day}日" if d else ""


def _md(d):
    return f"{d.month}/{d.day}" if d else ""


def order_sheet_pdf(po, lines, company: dict) -> bytes:
    """注文依頼書: A5横、1ページ最大4明細。lines は (line, item) のリスト。"""
    _ensure_font()
    buf = BytesIO()
    W, H = landscape(A5)  # 約 595 x 420 pt
    c = canvas.Canvas(buf, pagesize=(W, H))

    pages = [lines[i:i + 4] for i in range(0, len(lines), 4)] or [[]]
    for page in pages:
        _draw_order_page(c, W, H, po, page, company)
        c.showPage()
    c.save()
    return buf.getvalue()


def _draw_order_page(c, W, H, po, page_lines, company):
    left = 12 * mm
    right = W - 12 * mm
    top = H - 12 * mm

    # タイトル
    c.setFont(FONT, 18)
    c.drawCentredString(W / 2, top - 4 * mm, "注 文 依 頼 書")
    c.setLineWidth(1)
    c.line(W / 2 - 45 * mm, top - 6 * mm, W / 2 + 45 * mm, top - 6 * mm)

    # 伝票NO・日付（右上）
    c.setFont(FONT, 9)
    c.drawRightString(right, top, f"伝票NO  {po.order_no or ''}")
    c.drawRightString(right, top - 5 * mm, _ymd(po.order_date))

    # 宛先・納入場所
    y = top - 16 * mm
    c.setFont(FONT, 12)
    c.drawString(left, y, f"{po.supplier or ''}　殿")
    c.setFont(FONT, 9)
    c.drawRightString(right, y, f"納入場所： {po.deliver_to or ''}")

    # 明細テーブル
    cols = [
        ("材質/部品番号", 70 * mm),
        ("種類", 22 * mm),
        ("板厚", 20 * mm),
        ("サイズ", 30 * mm),
        ("数量", 18 * mm),
        ("単位", 14 * mm),
    ]
    table_w = right - left
    # 列幅を実幅に合わせて調整（合計を table_w にスケール）
    base = sum(w for _, w in cols)
    scale = table_w / base
    widths = [w * scale for _, w in cols]

    ty = y - 8 * mm
    row_h = 8 * mm
    remark_h = 7 * mm

    # ヘッダ行
    c.setFont(FONT, 9)
    c.setLineWidth(0.7)
    x = left
    c.line(left, ty, right, ty)
    for (label, _), w in zip(cols, widths):
        c.drawCentredString(x + w / 2, ty - 6 * mm, label)
        x += w
    ty -= row_h
    c.line(left, ty, right, ty)

    # 明細＋備考（1明細 = 値行 + 備考行）
    for line, item in page_lines:
        # 値行
        x = left
        vals = [
            item.material or item.item_code,
            item.category or "",
            item.thickness or "",
            item.size or "",
            str(line.qty),
            item.unit or "",
        ]
        for v, w in zip(vals, widths):
            c.drawCentredString(x + w / 2, ty - 5.5 * mm, str(v))
            x += w
        ty -= row_h
        # 備考行
        price = f"@{line.unit_price:.0f}" if line.unit_price is not None else ""
        rep = "リピート" if line.repeat_flag else ""
        remark = f"※備考　納期: {_md(line.due_date)}　{price}　{rep}"
        if line.note:
            remark += f"　{line.note}"
        c.setFont(FONT, 8.5)
        c.drawString(left + 2 * mm, ty - 5 * mm, remark)
        c.setFont(FONT, 9)
        ty -= remark_h
        c.line(left, ty, right, ty)

    # 縦罫線（ヘッダ〜最終行）
    # （簡易のため外枠と列区切りのみ）
    # フッター（自社情報）
    c.setFont(FONT, 10)
    fy = 16 * mm
    c.drawRightString(right, fy, company.get("company_name", ""))
    c.setFont(FONT, 8)
    c.drawRightString(right, fy - 5 * mm, company.get("company_address", ""))
    c.drawRightString(
        right, fy - 9 * mm,
        f"TEL {company.get('company_tel','')}　FAX {company.get('company_fax','')}",
    )


def process_sheet_pdf(lines_with_items, drawings_by_item: dict, company: dict) -> bytes:
    """加工依頼書: A5縦、1品目1ページ。調達品のみ。
    lines_with_items: (line, item) のリスト。drawings_by_item: {item_id: Drawing}。
    """
    _ensure_font()
    buf = BytesIO()
    W, H = A5  # 縦
    c = canvas.Canvas(buf, pagesize=(W, H))

    for line, item in lines_with_items:
        _draw_process_page(c, W, H, line, item, drawings_by_item.get(item.id))
        c.showPage()
    if not lines_with_items:
        c.showPage()
    c.save()
    return buf.getvalue()


def _draw_process_page(c, W, H, line, item, drawing):
    left = 12 * mm
    right = W - 12 * mm
    top = H - 14 * mm

    c.setFont(FONT, 16)
    c.drawCentredString(W / 2, top, "加 工 依 頼 書")
    c.line(left, top - 4 * mm, right, top - 4 * mm)

    c.setFont(FONT, 10)
    y = top - 14 * mm
    rows = [
        ("品番", item.item_code),
        ("名称", item.name),
        ("材質", item.material or ""),
        ("種類", item.category or ""),
        ("板厚", item.thickness or ""),
        ("サイズ", item.size or ""),
        ("数量", f"{line.qty} {item.unit or ''}"),
        ("納期", _md(line.due_date)),
        ("備考", line.note or ""),
    ]
    for label, val in rows:
        c.setFont(FONT, 9)
        c.drawString(left, y, f"{label}")
        c.setFont(FONT, 10)
        c.drawString(left + 22 * mm, y, str(val))
        c.line(left, y - 2 * mm, right, y - 2 * mm)
        y -= 9 * mm

    # 図面エリア
    box_top = y - 2 * mm
    box_bottom = 16 * mm
    c.rect(left, box_bottom, right - left, box_top - box_bottom)
    if drawing and drawing.data:
        try:
            img = ImageReader(BytesIO(drawing.data))
            iw, ih = img.getSize()
            bw = (right - left) - 6 * mm
            bh = (box_top - box_bottom) - 6 * mm
            ratio = min(bw / iw, bh / ih)
            dw, dh = iw * ratio, ih * ratio
            c.drawImage(img, left + (right - left - dw) / 2,
                        box_bottom + (box_top - box_bottom - dh) / 2,
                        dw, dh, preserveAspectRatio=True, mask="auto")
        except Exception:
            c.setFont(FONT, 9)
            c.drawCentredString(W / 2, (box_top + box_bottom) / 2, "（図面の読み込みに失敗）")
    else:
        c.setFont(FONT, 9)
        c.drawCentredString(W / 2, (box_top + box_bottom) / 2, "図面（未登録）")
