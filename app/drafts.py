import io

from docx import Document as DocxDocument
from docx.shared import Pt

DOCS = {
    "deposit": {
        "kind": {"en": "letter asking for the security deposit back", "hi": "सिक्योरिटी डिपॉज़िट वापसी की मांग का पत्र"},
        "party": {"en": "landlord", "hi": "मकान मालिक"},
        "to": "landlord",
        "subject": {"en": "Return of security deposit for {property}", "hi": "{property} की सिक्योरिटी डिपॉज़िट की वापसी"},
        "cards": ["ICA-73", "MTA-11"],
    },
    "refund": {
        "kind": {"en": "complaint to the seller's grievance officer", "hi": "विक्रेता के शिकायत अधिकारी को शिकायत"},
        "party": {"en": "grievance officer", "hi": "शिकायत अधिकारी"},
        "to": "seller",
        "subject": {"en": "Complaint about {product}", "hi": "{product} के बारे में शिकायत"},
        "cards": ["ECOM-4", "ECOM-REFUND", "CPA-69"],
    },
    "salary": {
        "kind": {"en": "letter asking for unpaid salary", "hi": "बकाया वेतन की मांग का पत्र"},
        "party": {"en": "employer", "hi": "नियोक्ता"},
        "to": "employer",
        "subject": {"en": "Payment of unpaid salary for {unpaid_period}", "hi": "{unpaid_period} के बकाया वेतन का भुगतान"},
        "cards": ["COW-17", "COW-45"],
    },
}

LABELS = {
    "en": {
        "banner": "DRAFT - CHECK EVERY LINE BEFORE SENDING",
        "note": "Prepared with Nyaya, a self-help tool. This is not a notice issued by a lawyer.",
        "from": "From: [Your full name]\n[Your address and phone number]",
        "to": "To: {name}\n[Their address]",
        "to_officer": "To: The Grievance Officer, {name}\n[Address or email shown on the platform]",
        "date": "Date: [DD/MM/YYYY]",
        "subject": "Subject: {subject}",
        "greeting": "Dear Sir/Madam,",
        "request": "I request: {resolution}.",
        "reply_by": "Please reply in writing within [number] days of receiving this letter.",
        "rules": "Rules that may be relevant (confirm with a lawyer before relying on them):",
        "proof": "Proof I have: {evidence}",
        "attached": "Attached: [List only the documents you are actually attaching]",
        "close": "Yours faithfully,\n[Your name and signature]",
        "blank": "[fill in]",
    },
    "hi": {
        "banner": "ड्राफ्ट - भेजने से पहले हर पंक्ति जांचें",
        "note": "Nyaya स्वयं-सहायता टूल से तैयार। यह किसी वकील द्वारा जारी नोटिस नहीं है।",
        "from": "प्रेषक: [आपका पूरा नाम]\n[आपका पता और फ़ोन नंबर]",
        "to": "प्रति: {name}\n[उनका पता]",
        "to_officer": "प्रति: शिकायत अधिकारी, {name}\n[प्लेटफॉर्म पर दिया पता या ईमेल]",
        "date": "दिनांक: [दिन/महीना/वर्ष]",
        "subject": "विषय: {subject}",
        "greeting": "महोदय/महोदया,",
        "request": "मेरा अनुरोध है: {resolution}।",
        "reply_by": "कृपया यह पत्र मिलने के [संख्या] दिनों के भीतर लिखित उत्तर दें।",
        "rules": "संभावित रूप से लागू नियम (भरोसा करने से पहले वकील से पुष्टि करें):",
        "proof": "मेरे पास प्रमाण: {evidence}",
        "attached": "संलग्न: [केवल वही दस्तावेज़ लिखें जो आप सच में लगा रहे हैं]",
        "close": "भवदीय,\n[आपका नाम और हस्ताक्षर]",
        "blank": "[भरें]",
    },
}


def doc_lang(lang: str) -> str:
    return "hi" if lang == "hi" else "en"


def _v(facts: dict, key: str, blank: str) -> str:
    return facts.get(key, {}).get("value") or blank


def fallback_paragraphs(domain: str, lang: str, facts: dict) -> list[str]:
    L = doc_lang(lang)
    b = LABELS[L]["blank"]
    v = lambda k: _v(facts, k, b)
    if L == "hi":
        if domain == "deposit":
            out = [f"मैंने आपसे {v('property')} किराये पर ली थी और {v('deposit_amount')} सिक्योरिटी डिपॉज़िट दी थी। मैंने {v('move_out_date')} को घर खाली किया।"]
            if "actions" in facts:
                out.append(f"मैंने पहले ही डिपॉज़िट वापस मांगी है: {v('actions')}।")
        elif domain == "refund":
            out = [f"मैंने {v('seller')} से {v('product')} {v('amount')} में {v('purchase_date')} को खरीदा। समस्या: {v('problem')}।"]
            if "actions" in facts:
                out.append(f"मैंने पहले ही शिकायत की है: {v('actions')}।")
        else:
            out = [f"मैं आपके यहां {v('role')} के रूप में काम करता/करती हूं या करता/करती था/थी। {v('unpaid_period')} का वेतन, कुल {v('unpaid_amount')}, अभी तक नहीं मिला है।"]
            if "actions" in facts:
                out.append(f"मैंने पहले ही वेतन मांगा है: {v('actions')}।")
        return out
    if domain == "deposit":
        out = [f"I rented {v('property')} from you and paid a security deposit of {v('deposit_amount')}. I moved out on {v('move_out_date')}."]
        if "deductions" in facts:
            out.append(f"About deductions, the position so far is: {v('deductions')}.")
        if "actions" in facts:
            out.append(f"I have already asked for the deposit back: {v('actions')}.")
    elif domain == "refund":
        out = [f"I bought {v('product')} from {v('seller')} for {v('amount')} on {v('purchase_date')}. The problem: {v('problem')}."]
        if "order_id" in facts:
            out.append(f"Order reference: {v('order_id')}.")
        if "actions" in facts:
            out.append(f"I have already complained: {v('actions')}.")
    else:
        out = [f"I work or worked for you as {v('role')}. My salary for {v('unpaid_period')}, a total of {v('unpaid_amount')}, has not been paid."]
        if "employment_status" in facts:
            out.append(f"Employment status: {v('employment_status')}.")
        if "actions" in facts:
            out.append(f"I have already asked for payment: {v('actions')}.")
    return out


def render(domain: str, lang: str, facts: dict, paragraphs: list[str], cards: list[dict]) -> str:
    L = doc_lang(lang)
    lab = LABELS[L]
    spec = DOCS[domain]
    b = lab["blank"]
    fill = {k: v["value"] for k, v in facts.items()}

    class Blank(dict):
        def __missing__(self, key):
            return b

    subject = spec["subject"][L].format_map(Blank(fill))
    to_name = _v(facts, spec["to"], b)
    to_line = lab["to_officer"] if domain == "refund" else lab["to"]
    parts = [
        lab["banner"],
        lab["note"],
        "",
        lab["from"],
        "",
        to_line.format(name=to_name),
        "",
        lab["date"],
        "",
        lab["subject"].format(subject=subject),
        "",
        lab["greeting"],
        "",
    ]
    for p in paragraphs:
        parts += [p, ""]
    parts += [lab["request"].format(resolution=_v(facts, "resolution", b)), "", lab["reply_by"], ""]
    if "evidence" in facts:
        parts += [lab["proof"].format(evidence=facts["evidence"]["value"]), ""]
    if cards:
        parts.append(lab["rules"])
        for c in cards:
            summary = c["summary_hi"] if L == "hi" else c["summary_en"]
            line = f"- {c['citation']}: {summary}"
            if c.get("caveat"):
                line += f" ({c['caveat']})"
            parts.append(line)
        parts.append("")
    parts += [lab["attached"], "", lab["close"]]
    return "\n".join(parts)


def to_docx(content: str) -> bytes:
    doc = DocxDocument()
    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(11)
    lines = content.split("\n")
    for i, line in enumerate(lines):
        para = doc.add_paragraph()
        run = para.add_run(line)
        if i == 0:
            run.bold = True
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
