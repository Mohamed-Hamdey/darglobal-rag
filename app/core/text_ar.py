# app/core/text_ar.py
import re, unicodedata

TASHKEEL = re.compile(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]')
ARABIC_INDIC = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
PERSIAN_INDIC = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')

def normalize_ar(text: str) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = TASHKEEL.sub("", t)
    t = t.replace('\u0640', '')            # tatweel
    t = t.translate(ARABIC_INDIC).translate(PERSIAN_INDIC)
    for a in ('أ', 'إ', 'آ'): t = t.replace(a, 'ا')
    t = t.replace('ى', 'ي').replace('ة', 'ه')
    return re.sub(r"\s+", " ", t).strip()

def detect_lang(text: str) -> str:
    return "ar" if re.search(r'[\u0600-\u06FF]', text) else "en"