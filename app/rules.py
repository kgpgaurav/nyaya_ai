import re

DEVANAGARI = re.compile(r"[ऀ-ॿ]")

_PATTERNS = {
    "danger": [
        r"\b(kill|murder|beat(?:ing)?|hit me|attack(?:ed)?|threat(?:en(?:ed|ing)?)?|weapon|knife|acid|suicide|end my life)\b",
        r"\b(maar\s*(?:dunga|denge|diya)|jaan se|dhamki)\b",
        r"(मार\s*(?:दूंगा|देंगे|डालूंगा)|जान से|धमकी|आत्महत्या|हमला)",
    ],
    "police": [
        r"\b(police|fir|arrest(?:ed)?|thana|thane|chargesheet|bail)\b",
        r"(पुलिस|एफआईआर|गिरफ्तार|थाना|जमानत)",
    ],
    "criminal": [
        r"\b(criminal case|cheating case|420|ipc|bns|crpc|bnss|jail|prison|fraud case)\b",
        r"(आपराधिक|जेल|धोखाधड़ी का केस)",
    ],
    "family": [
        r"\b(divorce|custody|maintenance|alimony|dowry|domestic violence|talaq|498a)\b",
        r"(तलाक|हिरासत|भरण-पोषण|गुज़ारा भत्ता|दहेज|घरेलू हिंसा)",
    ],
    "court_deadline": [
        r"\b(summons|hearing date|next hearing|court date|appear before|ex[- ]parte|warrant)\b",
        r"(समन|सुनवाई|पेशी|अदालत में हाज़िर|वारंट)",
    ],
    "fabrication": [
        r"\b(fake|forge|fabricate|backdate|back-date|make up|create a fake|false evidence|fake receipt|fake bill)\b",
        r"\b(nakli|jhooth[a]? (?:saboot|bill))\b",
        r"(नकली|झूठा सबूत|फर्जी)",
    ],
    "injection": [
        r"\b(ignore (?:all|previous|the above) instructions|system prompt|you are now|developer mode|jailbreak)\b",
    ],
}

_COMPILED = {k: [re.compile(p, re.I) for p in v] for k, v in _PATTERNS.items()}


def rule_risks(text: str) -> set[str]:
    found = set()
    for risk, patterns in _COMPILED.items():
        if any(p.search(text) for p in patterns):
            found.add(risk)
    return found


def detect_script(text: str) -> str:
    return "hi" if DEVANAGARI.search(text) else "en"
