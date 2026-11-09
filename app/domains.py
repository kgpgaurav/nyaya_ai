from dataclasses import dataclass

LANGS = ("en", "hi", "hinglish")


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: dict
    question: dict


def _f(name, en, hi, q_en, q_hi, q_hl):
    return FieldSpec(name, {"en": en, "hi": hi, "hinglish": en}, {"en": q_en, "hi": q_hi, "hinglish": q_hl})


DOMAIN_FIELDS: dict[str, list[FieldSpec]] = {
    "deposit": [
        _f("landlord", "Landlord", "मकान मालिक",
           "What is the landlord's name?", "मकान मालिक का नाम क्या है?", "Landlord ka naam kya hai?"),
        _f("property", "Property", "संपत्ति",
           "Which property was it, and in which city?", "कौन सी संपत्ति थी और किस शहर में?", "Kaunsi property thi, aur kis city mein?"),
        _f("state", "State", "राज्य",
           "Which state is the property in? Rent rules differ by state.", "संपत्ति किस राज्य में है? किराये के नियम राज्य के हिसाब से अलग होते हैं।",
           "Property kis state mein hai? Rent ke rules state ke hisaab se alag hote hain."),
        _f("deposit_amount", "Deposit paid", "जमा राशि",
           "How much security deposit did you pay?", "आपने कितनी सिक्योरिटी डिपॉज़िट दी थी?", "Aapne kitna security deposit diya tha?"),
        _f("rent", "Monthly rent", "मासिक किराया",
           "What was the monthly rent?", "मासिक किराया कितना था?", "Monthly rent kitna tha?"),
        _f("move_out_date", "Move-out date", "घर खाली करने की तारीख",
           "When did you move out and hand over the keys?", "आपने घर कब खाली किया और चाबी कब सौंपी?", "Aapne ghar kab khaali kiya aur chaabi kab di?"),
        _f("agreement", "Rent agreement", "किराया समझौता",
           "Do you have a written rent agreement? What does it say about the deposit?",
           "क्या लिखित किराया समझौता है? उसमें डिपॉज़िट के बारे में क्या लिखा है?",
           "Kya written rent agreement hai? Usmein deposit ke baare mein kya likha hai?"),
        _f("deductions", "Deductions claimed", "बताई गई कटौती",
           "Has the landlord given any reason or deductions for not returning it?",
           "क्या मकान मालिक ने डिपॉज़िट न लौटाने का कोई कारण या कटौती बताई है?",
           "Kya landlord ne deposit na lautane ka koi reason ya deduction bataya hai?"),
        _f("actions", "Steps already taken", "पहले किए गए प्रयास",
           "Have you asked for it back? How, and what did they say?", "क्या आपने वापस मांगा? कैसे, और उन्होंने क्या कहा?",
           "Kya aapne wapas maanga? Kaise, aur unhone kya kaha?"),
        _f("evidence", "Proof you have", "आपके पास प्रमाण",
           "What proof do you have: agreement, payment receipts, chats, move-out photos? Say if none.",
           "आपके पास क्या प्रमाण है: समझौता, भुगतान रसीद, चैट, घर छोड़ते समय की फोटो? कुछ नहीं है तो बताएं।",
           "Aapke paas kya proof hai: agreement, payment receipt, chats, move-out photos? Kuch nahi hai to batayein."),
        _f("resolution", "What you want", "आपकी मांग",
           "What outcome do you want: the full deposit, part of it, or something else?",
           "आप क्या चाहते हैं: पूरी जमा राशि, उसका कुछ हिस्सा, या कुछ और?",
           "Aap kya chahte hain: poora deposit, kuch hissa, ya kuch aur?"),
    ],
    "refund": [
        _f("seller", "Seller / platform", "विक्रेता / प्लेटफॉर्म",
           "Who sold it, and on which website or app?", "किसने बेचा और किस वेबसाइट या ऐप पर?", "Kisne becha aur kis website ya app par?"),
        _f("product", "Product or service", "सामान या सेवा",
           "What did you buy?", "आपने क्या खरीदा?", "Aapne kya kharida?"),
        _f("amount", "Amount paid", "भुगतान राशि",
           "How much did you pay?", "आपने कितना भुगतान किया?", "Aapne kitna pay kiya?"),
        _f("purchase_date", "Purchase date", "खरीद की तारीख",
           "When did you buy it? An approximate date is fine.", "कब खरीदा? अनुमानित तारीख भी चलेगी।", "Kab kharida? Approx date bhi chalega."),
        _f("problem", "What went wrong", "समस्या",
           "What went wrong with the order or refund?", "ऑर्डर या रिफंड में क्या गड़बड़ हुई?", "Order ya refund mein kya problem hui?"),
        _f("order_id", "Order reference", "ऑर्डर नंबर",
           "Do you have an order or transaction number?", "क्या आपके पास ऑर्डर या ट्रांज़ैक्शन नंबर है?", "Kya aapke paas order ya transaction number hai?"),
        _f("actions", "Steps already taken", "पहले किए गए प्रयास",
           "Have you complained to the seller or platform? What did they say?",
           "क्या आपने विक्रेता या प्लेटफॉर्म से शिकायत की? उन्होंने क्या कहा?",
           "Kya aapne seller ya platform se complaint ki? Unhone kya kaha?"),
        _f("evidence", "Proof you have", "आपके पास प्रमाण",
           "What proof do you have: invoice, payment record, photos, support chats? Say if none.",
           "आपके पास क्या प्रमाण है: बिल, भुगतान रिकॉर्ड, फोटो, सपोर्ट चैट? कुछ नहीं है तो बताएं।",
           "Aapke paas kya proof hai: invoice, payment record, photos, support chats? Kuch nahi hai to batayein."),
        _f("resolution", "What you want", "आपकी मांग",
           "What do you want: a refund, a replacement, or something else?", "आप क्या चाहते हैं: रिफंड, बदलाव, या कुछ और?",
           "Aap kya chahte hain: refund, replacement, ya kuch aur?"),
        _f("purpose", "Purchase purpose", "खरीद का उद्देश्य",
           "Was this for personal use, or for resale or a business?", "क्या यह निजी उपयोग के लिए था, या दोबारा बेचने या व्यापार के लिए?",
           "Kya yeh personal use ke liye tha, ya resale ya business ke liye?"),
    ],
    "salary": [
        _f("employer", "Employer", "नियोक्ता",
           "Who is the employer (company or person)?", "नियोक्ता कौन है (कंपनी या व्यक्ति)?", "Employer kaun hai (company ya person)?"),
        _f("role", "Your job", "आपका काम",
           "What was your job there?", "वहां आपका काम क्या था?", "Wahan aapka kaam kya tha?"),
        _f("state", "State", "राज्य",
           "Which state do you work in? Claim offices differ by state.", "आप किस राज्य में काम करते हैं? दावे के दफ्तर राज्य के हिसाब से अलग होते हैं।",
           "Aap kis state mein kaam karte hain? Claim office state ke hisaab se alag hote hain."),
        _f("salary", "Salary", "वेतन",
           "What is your monthly salary?", "आपका मासिक वेतन कितना है?", "Aapki monthly salary kitni hai?"),
        _f("unpaid_period", "Unpaid period", "बकाया अवधि",
           "For which months or period has salary not been paid?", "किन महीनों या अवधि का वेतन नहीं मिला?", "Kin mahino ya period ki salary nahi mili?"),
        _f("unpaid_amount", "Amount owed", "बकाया राशि",
           "How much is owed in total, roughly?", "कुल कितना बकाया है, लगभग?", "Total kitna baaki hai, roughly?"),
        _f("employment_status", "Still working?", "अभी भी काम कर रहे हैं?",
           "Are you still working there, or did you resign or get removed? When?",
           "क्या आप अभी भी वहां काम करते हैं, या इस्तीफ़ा दिया या निकाले गए? कब?",
           "Kya aap abhi bhi wahan kaam karte hain, ya resign kiya ya nikaale gaye? Kab?"),
        _f("actions", "Steps already taken", "पहले किए गए प्रयास",
           "Have you asked for the salary? How, and what did they say?", "क्या आपने वेतन मांगा? कैसे, और उन्होंने क्या कहा?",
           "Kya aapne salary maangi? Kaise, aur unhone kya kaha?"),
        _f("evidence", "Proof you have", "आपके पास प्रमाण",
           "What proof do you have: offer letter, salary slips, bank statements, emails, attendance? Say if none.",
           "आपके पास क्या प्रमाण है: ऑफर लेटर, सैलरी स्लिप, बैंक स्टेटमेंट, ईमेल, हाज़िरी? कुछ नहीं है तो बताएं।",
           "Aapke paas kya proof hai: offer letter, salary slip, bank statement, emails, attendance? Kuch nahi hai to batayein."),
        _f("resolution", "What you want", "आपकी मांग",
           "What outcome do you want?", "आप क्या परिणाम चाहते हैं?", "Aap kya result chahte hain?"),
    ],
    "notice": [
        _f("sender", "Sent by", "भेजने वाला",
           "Who sent the notice?", "नोटिस किसने भेजा?", "Notice kisne bheja?"),
        _f("received_date", "Received on", "मिलने की तारीख",
           "When did you receive it?", "आपको यह कब मिला?", "Aapko yeh kab mila?"),
        _f("notice_text", "What it says", "इसमें क्या लिखा है",
           "Paste or read out the main part of the notice.", "नोटिस का मुख्य हिस्सा चिपकाएं या पढ़कर बताएं।", "Notice ka main part paste karein ya padh kar batayein."),
    ],
}

DRAFT_REQUIRED = {
    "deposit": ["landlord", "property", "deposit_amount", "move_out_date", "resolution"],
    "refund": ["seller", "product", "amount", "purchase_date", "problem", "resolution"],
    "salary": ["employer", "unpaid_period", "unpaid_amount", "resolution"],
}

OPPONENT = {
    "deposit": {"en": "landlord", "hi": "मकान मालिक", "hinglish": "landlord"},
    "refund": {"en": "seller's support agent", "hi": "विक्रेता का सपोर्ट एजेंट", "hinglish": "seller ka support agent"},
    "salary": {"en": "employer", "hi": "नियोक्ता", "hinglish": "employer"},
}


def field_names(domain: str) -> list[str]:
    return [f.name for f in DOMAIN_FIELDS.get(domain, [])]


def spec(domain: str, name: str) -> FieldSpec | None:
    for f in DOMAIN_FIELDS.get(domain, []):
        if f.name == name:
            return f
    return None


def missing_fields(domain: str, facts: dict) -> list[str]:
    return [f.name for f in DOMAIN_FIELDS.get(domain, []) if f.name not in facts]


def next_question(domain: str, facts: dict, lang: str) -> str | None:
    for name in missing_fields(domain, facts):
        return spec(domain, name).question[lang]
    return None


def draft_missing(domain: str, facts: dict) -> list[str]:
    return [f for f in DRAFT_REQUIRED.get(domain, []) if f not in facts]
