import pytest

from app.corpus import load_cards
from app.verify import money, periods, roleplay_issues, verify_plain, verify_points

CARDS = {c["id"]: c for c in load_cards()}


def run(text, sources, facts=None):
    return verify_points([{"text": text, "sources": sources}], CARDS, facts or {})


@pytest.mark.parametrize(
    "text,sources",
    [
        ("Monthly wages must be paid before the end of the 7th day of the next month.", ["COW-17"]),
        ("If you resigned, your wages are due within 2 working days.", ["COW-17"]),
        ("Under Section 17 of the Code on Wages, 2019, the employer must pay on time.", ["COW-17"]),
        ("The Code on Wages replaced the Payment of Wages Act, 1936.", ["COW-COMMENCE"]),
        ("You can file a claim within three years.", ["COW-45"]),
        ("The grievance officer must acknowledge in 48 hours and redress within one month.", ["ECOM-4"]),
        ("Call 1800-11-4000 or WhatsApp 8800001915.", ["NCH"]),
        ("File on e-jagriti.gov.in.", ["EJAGRITI"]),
        ("Keep copies of your receipts and chats.", []),
        ("मासिक वेतन अगले महीने के सातवें दिन तक देना होता है।", ["COW-17"]),
        ("वेतन संहिता, 2019 की धारा 45 के तहत तीन साल में दावा करें।", ["COW-45"]),
    ],
)
def test_supported_points_are_kept(text, sources):
    verdict = run(text, sources)
    assert verdict.kept and not verdict.dropped, verdict.dropped


@pytest.mark.parametrize(
    "text,sources,reason",
    [
        ("Under Section 15 of the Payment of Wages Act, 1936 you can claim.", ["COW-17"], "section or rule 15"),
        ("You can file a claim within 5 years.", ["COW-45"], "5 year"),
        ("In Ramesh Kumar v. State of UP the court held deposits must be returned.", ["MTA-11"], "case law"),
        ("See AIR 2019 SC 1234.", ["MTA-11"], "case law"),
        ("Call 1800-22-5555 for help.", ["NCH"], "number"),
        ("The landlord is legally required to pay interest.", [], "without citing"),
        ("You can claim Rs 2 lakh as compensation.", ["CPA-JURIS"], "2 lakh"),
        ("धारा 420 के तहत केस करें।", ["COW-45"], "420"),
        ("उपभोक्ता संरक्षण अधिनियम के तहत शिकायत करें।", ["COW-45"], "consumer protection act"),
        ("File on edaakhil.nic.in.", ["EJAGRITI"], "edaakhil"),
        ("The Code on Wages says pay on time.", ["NCH"], "code on wages"),
        ("Deposits are capped at two months' rent.", ["NOT-A-CARD"], "unknown source"),
    ],
)
def test_unsupported_points_are_dropped(text, sources, reason):
    verdict = run(text, sources)
    assert not verdict.kept
    assert any(reason in issue for issue in verdict.dropped[0]["issues"]), verdict.dropped


def test_user_facts_count_as_evidence_for_amounts():
    facts = {"amount": {"value": "Rs 15,000"}}
    assert run("You paid Rs 15,000, within the District Commission limit of Rs 50 lakh.", ["CPA-JURIS"], facts).kept
    assert not run("You paid Rs 16,000.", ["CPA-JURIS"], facts).kept


def test_number_words_and_digits_match():
    assert periods("two working days") == periods("2 working days")
    assert periods("forty-eight hours") == {"48 hour"}
    assert money("Rs 50,000") == money("₹50000")
    assert money("50 लाख") == {"50 lakh"}


def test_verdict_requires_majority_kept():
    points = [
        {"text": "In Sharma v. Gupta the court agreed.", "sources": ["ICA-73"]},
        {"text": "Section 999 helps you.", "sources": ["ICA-73"]},
        {"text": "Keep your receipts.", "sources": []},
    ]
    verdict = verify_points(points, CARDS, {})
    assert len(verdict.kept) == 1 and not verdict.ok


def test_roleplay_check_only_flags_legal_references():
    assert roleplay_issues("I will deduct Rs 5,000 for painting.") == []
    assert roleplay_issues("Under Section 108 of the Transfer of Property Act I keep it.")


def test_draft_paragraph_check():
    facts = {"deposit_amount": {"value": "Rs 50,000"}}
    assert verify_plain("I paid a security deposit of Rs 50,000.", [], facts) == []
    assert verify_plain("By law you must refund within 30 days.", [], facts)
