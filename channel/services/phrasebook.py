"""Every farmer-facing string, in every language we speak.

One module so that adding a language is a data change with a test that fails
loudly when it is incomplete, rather than a hunt through pipeline.py, composer.py
and routers/alerts.py for hardcoded Devanagari.

Three rules for anything added here:

1. **Write in the language, do not translate word-for-word from Marathi.** These
   are read aloud. "करपा", "झुलसा" and "ধসা" are the words farmers actually use
   for blight in their own language; the dictionary translation is not.
2. **No Latin script outside `en`.** It reaches a non-Latin TTS voice and comes
   out as noise. languages.strip_to_speakable is the net, not the plan.
3. **An escalation names no dose and no cost, in any language.** That is
   BRAIN.md §6 and DPG conformance rule 4, and it is a property of the string,
   not only of the branch that selects it.
"""

from typing import Dict

from contracts.languages import DEFAULT_LANGUAGE, LANGUAGES
from channel.services.languages import menu_position

# --- Disease names ----------------------------------------------------------
# Keyed on the lowercased English name with the botanical binomial stripped. A
# disease missing from a language's table renders as a generic phrase rather
# than leaking its English name into a non-Latin voice — see disease_name().

DISEASE_NAMES: Dict[str, Dict[str, str]] = {
    "mr": {
        "early blight": "अर्ली ब्लाइट म्हणजेच करपा",
        "late blight": "लेट ब्लाइट म्हणजेच उशिरा येणारा करपा",
        "bacterial blight": "जिवाणूजन्य करपा",
        "septoria leaf spot": "सेप्टोरिया पानावरील ठिपके",
        "purple blotch": "जांभळा करपा",
        "powdery mildew": "भुरी रोग",
        "downy mildew": "केवडा रोग",
        "anthracnose": "अँथ्रॅक्नोज",
        "fusarium wilt": "मर रोग",
        "leaf curl": "पाने गुंडाळणारा रोग",
        "nitrogen deficiency": "नत्राची कमतरता",
        "potassium deficiency": "पालाशची कमतरता",
        "nutrient deficiency": "अन्नद्रव्यांची कमतरता",
        "blast": "भाताचा करपा",
        "bacterial leaf blight": "जिवाणूजन्य पानांचा करपा",
        "sheath blight": "पर्णकोष करपा",
        "brown spot": "तपकिरी ठिपके",
        "yellow rust": "पिवळा तांबेरा",
        "karnal bunt": "करनाल बंट",
        "turcicum leaf blight": "टर्सिकम पानांचा करपा",
        "fall armyworm": "लष्करी अळी",
        "pink bollworm": "गुलाबी बोंडअळी",
        "red rot": "लाल कूज",
        "smut": "काणी रोग",
        "ascochyta blight": "अस्कोकायटा करपा",
        "pod borer": "घाटे अळी",
        "sterility mosaic": "वांझ मोझॅक रोग",
        "alternaria blight": "अल्टरनेरिया करपा",
        "white rust": "पांढरा तांबेरा",
        "aphid": "मावा कीड",
        "tikka leaf spot": "टिक्का पानावरील ठिपके",
        "collar rot": "मूळकूज",
        "black scurf": "काळी खरूज",
        "rust": "तांबेरा",
        "wilt": "मर रोग",
        "yellow mosaic": "पिवळा मोझॅक रोग",
        "charcoal rot": "खोडकूज",
    },
    "hi": {
        "early blight": "अगेती झुलसा",
        "late blight": "पछेती झुलसा",
        "bacterial blight": "जीवाणु झुलसा",
        "septoria leaf spot": "सेप्टोरिया पर्ण धब्बा",
        "purple blotch": "बैंगनी धब्बा रोग",
        "powdery mildew": "चूर्णिल आसिता यानी भभूतिया रोग",
        "downy mildew": "मृदुरोमिल आसिता",
        "anthracnose": "एंथ्रेक्नोज",
        "fusarium wilt": "उकठा रोग",
        "leaf curl": "पत्ती मरोड़ रोग",
        "nitrogen deficiency": "नाइट्रोजन की कमी",
        "potassium deficiency": "पोटाश की कमी",
        "nutrient deficiency": "पोषक तत्वों की कमी",
        "blast": "झोंका रोग",
        "bacterial leaf blight": "जीवाणु पर्ण झुलसा",
        "sheath blight": "आवरण झुलसा",
        "brown spot": "भूरा धब्बा रोग",
        "yellow rust": "पीला रतुआ",
        "karnal bunt": "करनाल बंट",
        "turcicum leaf blight": "टर्सिकम पत्ती झुलसा",
        "fall armyworm": "फॉल आर्मीवर्म यानी सैनिक कीड़ा",
        "pink bollworm": "गुलाबी सुंडी",
        "red rot": "लाल सड़न रोग",
        "smut": "कंडुआ रोग",
        "ascochyta blight": "एस्कोकाइटा झुलसा",
        "pod borer": "फली छेदक कीड़ा",
        "sterility mosaic": "बंध्यता मोज़ेक रोग",
        "alternaria blight": "अल्टरनेरिया झुलसा",
        "white rust": "सफेद रतुआ",
        "aphid": "माहू कीट",
        "tikka leaf spot": "टिक्का पर्ण धब्बा",
        "collar rot": "कॉलर सड़न",
        "black scurf": "काली पपड़ी रोग",
        "rust": "रतुआ रोग",
        "wilt": "उकठा रोग",
        "yellow mosaic": "पीला मोज़ेक रोग",
        "charcoal rot": "चारकोल सड़न",
    },
    "bn": {
        "early blight": "আগাম ধসা",
        "late blight": "নাবি ধসা",
        "bacterial blight": "ব্যাকটেরিয়াজনিত ধসা",
        "septoria leaf spot": "সেপ্টোরিয়া পাতার দাগ",
        "purple blotch": "বেগুনি দাগ রোগ",
        "powdery mildew": "গুঁড়ো ছাতা রোগ",
        "downy mildew": "কোঁকড়া ছাতা রোগ",
        "anthracnose": "অ্যানথ্রাকনোজ",
        "fusarium wilt": "ঢলে পড়া রোগ",
        "leaf curl": "পাতা কোঁকড়ানো রোগ",
        "nitrogen deficiency": "নাইট্রোজেনের ঘাটতি",
        "potassium deficiency": "পটাশের ঘাটতি",
        "nutrient deficiency": "পুষ্টির ঘাটতি",
        "blast": "ব্লাস্ট রোগ",
        "bacterial leaf blight": "ব্যাকটেরিয়াজনিত পাতা ঝলসা",
        "sheath blight": "খোলপচা রোগ",
        "brown spot": "বাদামী দাগ রোগ",
        "yellow rust": "হলুদ মরিচা",
        "karnal bunt": "কারনাল বান্ট",
        "turcicum leaf blight": "টারসিকাম পাতা ঝলসা",
        "fall armyworm": "ফল আর্মিওয়ার্ম পোকা",
        "pink bollworm": "গোলাপি বোলওয়ার্ম পোকা",
        "red rot": "লাল পচা রোগ",
        "smut": "স্মাট রোগ",
        "ascochyta blight": "অ্যাসকোকাইটা ধসা",
        "pod borer": "শুঁটি ছিদ্রকারী পোকা",
        "sterility mosaic": "বন্ধ্যা মোজাইক রোগ",
        "alternaria blight": "অলটারনারিয়া ধসা",
        "white rust": "সাদা মরিচা",
        "aphid": "জাব পোকা",
        "tikka leaf spot": "টিক্কা পাতার দাগ",
        "collar rot": "গোড়া পচা রোগ",
        "black scurf": "কালো আঁশ রোগ",
        "rust": "মরিচা রোগ",
        "wilt": "ঢলে পড়া রোগ",
        "yellow mosaic": "হলুদ মোজাইক রোগ",
        "charcoal rot": "চারকোল পচা রোগ",
    },
    # English needs no table: the diagnosis already arrives in English, and
    # disease_name() passes it through. Present so completeness tests can see it.
    "en": {},
}

# --- Dose units -------------------------------------------------------------

UNITS: Dict[str, Dict[str, str]] = {
    "mr": {"g": "ग्रॅम", "ml": "मिली", "l": "लिटर", "kg": "किलो"},
    "hi": {"g": "ग्राम", "ml": "मिली", "l": "लीटर", "kg": "किलो"},
    "bn": {"g": "গ্রাম", "ml": "মিলি", "l": "লিটার", "kg": "কেজি"},
    "en": {"g": "g", "ml": "ml", "l": "litre", "kg": "kg"},
}


PHRASES: Dict[str, Dict[str, Dict[str, str]]] = {
    # ---------------------------------------------------------------- Marathi
    "mr": {
        "ui": {
            "ack": "Got it, checking your field 🌱\nतुमच्या शेताची पाहणी करत आहोत...",
            "need_photo": (
                "🌱 *अन्नदाता सेतु*\n\n"
                "पिकाच्या तपासणीसाठी कृपया प्रभावित पानाचा एक स्पष्ट फोटो पाठवा."
            ),
            "location_saved": (
                "📍 तुमचे स्थान नोंदवले आहे.\n\n"
                "आता प्रभावित पानाचा एक स्पष्ट फोटो पाठवा."
            ),
            "language_set": "✅ भाषा मराठी केली आहे. आता पानाचा फोटो पाठवा.",
        },
        "labels": {
            "header": "🌱 *अन्नदाता सेतु | पिक आरोग्य सल्ला*",
            "diagnosis": "🔍 *निदान (Diagnosis):*",
            "confidence": "📊 *विश्वासार्हता (Confidence):*",
            "context": "📋 *विश्लेषण (Context):*",
            "action": "*सल्ला (Action):*",
            "dosage": "💊 *प्रमाण (Dosage):*",
            "cost": "💰 *अंदाजे खर्च:*",
            "urgency": "⏳ *कालावधी:* {hours} तासांच्या आत",
            "no_spray": "🎉 *फवारणीची गरज नाही — खताचा/औषधाचा अनावश्यक खर्च वाचवा.*",
            "sources": "📚 *संदर्भ:*",
        },
        "escalation_text": (
            "🌱 *अन्नदाता सेतु | पिक आरोग्य सल्ला*\n\n"
            "🔍 *निदान (Diagnosis):* अनिश्चित — तपासणी सुरू आहे\n\n"
            "🔬 *सल्ला (Action):*\n"
            "तुमच्या फोटोवरून आम्ही खात्रीशीर निदान करू शकलो नाही.\n\n"
            "⚠️ *कृपया आत्ता कोणतीही फवारणी करू नका.*\n"
            "आमचे कृषी तज्ज्ञ तुमचा फोटो तपासून लवकरच सल्ला देतील.\n\n"
            "📷 मदतीसाठी: दिवसाच्या उजेडात, प्रभावित पानाचा जवळून स्पष्ट फोटो पुन्हा पाठवा."
        ),
        "voice": {
            "subject_known": "{disease} दिसत आहे",
            "subject_unknown": "रोगाची लक्षणे दिसत आहेत",
            "dose_known": "{dosage} या प्रमाणात मिसळून फवारणी करा. ",
            "dose_unknown": "औषधाच्या पाकिटावर दिलेल्या प्रमाणानुसार फवारणी करा. ",
            "dosage_pattern": "{per_qty} {per_unit} पाण्यात {qty} {unit}",
            "dosage_pattern_single": "{per_qty} {per_unit} पाण्यात {qty} {unit}",
            "treatment": (
                "नमस्कार. तुमच्या पिकावर {subject}. "
                "हवामानातील आर्द्रतेमुळे याचा प्रसार वेगाने होऊ शकतो. "
                "{advice}{dose}"
                "याचा अंदाजे खर्च ₹{cost} येईल आणि ही फवारणी पुढील {hours} तासांत पूर्ण करा."
            ),
            "dont_spray": (
                "नमस्कार. तुमच्या पिकावर {subject}. "
                "ही रोगाची लागण नसून अन्नद्रव्यांची कमतरता आहे. "
                "{advice}"
                "त्यामुळे कोणतीही रासायनिक फवारणी करण्याची गरज नाही. "
                "यामुळे तुमचे अंदाजे ₹{saved} वाचतील."
            ),
            "escalation": (
                "नमस्कार. तुमचा फोटो आम्हाला नीट तपासता आला नाही. "
                "त्यामुळे आत्ता कोणतीही फवारणी करू नका. "
                "आमचे कृषी तज्ज्ञ तुमचा फोटो पाहून लवकरच तुम्हाला सल्ला देतील. "
                "शक्य असल्यास दिवसाच्या उजेडात पानाचा स्पष्ट फोटो पुन्हा पाठवा."
            ),
        },
        "alert": {
            "text": (
                "🚨 *सावधान! पूर्वसूचना (Outbreak Alert)* 🚨\n\n"
                "तुमच्या परिसरामध्ये ({district}) *{disease}* रोगाचा प्रादुर्भाव आढळून आला आहे. "
                "एकूण {count} शेतांमध्ये हा रोग पसरला आहे.\n\n"
                "🛡️ *संरक्षक उपाय:* आपल्या पिकाची पाहणी करा. रोग तुमच्या शेतात येण्यापूर्वी "
                "खबरदारीची फवारणी करा किंवा पानाचा फोटो काढून येथे पाठवा."
            ),
            "voice": (
                "सावधान! तुमच्या {district} परिसरामध्ये {disease} रोगाचा प्रादुर्भाव सुरू झाला आहे. "
                "{count} शेतांमध्ये हा रोग दिसून आला आहे. "
                "रोग तुमच्या पिकावर येण्यापूर्वी खबरदारी घ्या किंवा तुमच्या शेताचा फोटो आम्हाला पाठवा."
            ),
        },
    },
    # ------------------------------------------------------------------ Hindi
    "hi": {
        "ui": {
            "ack": "Got it, checking your field 🌱\nआपके खेत की जाँच की जा रही है...",
            "need_photo": (
                "🌱 *अन्नदाता सेतु*\n\n"
                "फसल की जाँच के लिए कृपया प्रभावित पत्ते की एक साफ़ तस्वीर भेजें."
            ),
            "location_saved": (
                "📍 आपका स्थान दर्ज कर लिया गया है.\n\n"
                "अब प्रभावित पत्ते की एक साफ़ तस्वीर भेजें."
            ),
            "language_set": "✅ भाषा हिन्दी कर दी गई है. अब पत्ते की तस्वीर भेजें.",
        },
        "labels": {
            "header": "🌱 *अन्नदाता सेतु | फसल स्वास्थ्य सलाह*",
            "diagnosis": "🔍 *निदान (Diagnosis):*",
            "confidence": "📊 *विश्वसनीयता (Confidence):*",
            "context": "📋 *विश्लेषण (Context):*",
            "action": "*सलाह (Action):*",
            "dosage": "💊 *मात्रा (Dosage):*",
            "cost": "💰 *अनुमानित खर्च:*",
            "urgency": "⏳ *समय:* {hours} घंटों के भीतर",
            "no_spray": "🎉 *छिड़काव की ज़रूरत नहीं — दवा का अनावश्यक खर्च बचाएँ.*",
            "sources": "📚 *संदर्भ:*",
        },
        "escalation_text": (
            "🌱 *अन्नदाता सेतु | फसल स्वास्थ्य सलाह*\n\n"
            "🔍 *निदान (Diagnosis):* अनिश्चित — जाँच जारी है\n\n"
            "🔬 *सलाह (Action):*\n"
            "आपकी तस्वीर से हम पक्का निदान नहीं कर सके.\n\n"
            "⚠️ *कृपया अभी कोई छिड़काव न करें.*\n"
            "हमारे कृषि विशेषज्ञ आपकी तस्वीर देखकर जल्द सलाह देंगे.\n\n"
            "📷 मदद के लिए: दिन के उजाले में, प्रभावित पत्ते की पास से साफ़ तस्वीर दोबारा भेजें."
        ),
        "voice": {
            "subject_known": "{disease} दिखाई दे रहा है",
            "subject_unknown": "रोग के लक्षण दिखाई दे रहे हैं",
            "dose_known": "{dosage} की दर से मिलाकर छिड़काव करें. ",
            "dose_unknown": "दवा के पैकेट पर दी गई मात्रा के अनुसार छिड़काव करें. ",
            "dosage_pattern": "{per_qty} {per_unit} पानी में {qty} {unit}",
            "dosage_pattern_single": "{per_qty} {per_unit} पानी में {qty} {unit}",
            "treatment": (
                "नमस्ते. आपकी फसल पर {subject}. "
                "मौसम में नमी के कारण यह तेज़ी से फैल सकता है. "
                "{advice}{dose}"
                "इसका अनुमानित खर्च ₹{cost} आएगा और यह छिड़काव अगले {hours} घंटों में पूरा करें."
            ),
            "dont_spray": (
                "नमस्ते. आपकी फसल पर {subject}. "
                "यह रोग नहीं, बल्कि पोषक तत्वों की कमी है. "
                "{advice}"
                "इसलिए किसी भी रासायनिक छिड़काव की ज़रूरत नहीं है. "
                "इससे आपके लगभग ₹{saved} बचेंगे."
            ),
            "escalation": (
                "नमस्ते. हम आपकी तस्वीर ठीक से जाँच नहीं सके. "
                "इसलिए अभी कोई छिड़काव न करें. "
                "हमारे कृषि विशेषज्ञ आपकी तस्वीर देखकर जल्द सलाह देंगे. "
                "हो सके तो दिन के उजाले में पत्ते की साफ़ तस्वीर दोबारा भेजें."
            ),
        },
        "alert": {
            "text": (
                "🚨 *सावधान! पूर्व चेतावनी (Outbreak Alert)* 🚨\n\n"
                "आपके क्षेत्र ({district}) में *{disease}* रोग का प्रकोप पाया गया है. "
                "कुल {count} खेतों में यह रोग फैल चुका है.\n\n"
                "🛡️ *बचाव के उपाय:* अपनी फसल की जाँच करें. रोग आपके खेत तक पहुँचने से पहले "
                "एहतियाती छिड़काव करें या पत्ते की तस्वीर यहाँ भेजें."
            ),
            "voice": (
                "सावधान! आपके {district} क्षेत्र में {disease} रोग का प्रकोप शुरू हो गया है. "
                "{count} खेतों में यह रोग दिखाई दिया है. "
                "रोग आपकी फसल तक पहुँचने से पहले सावधानी बरतें या अपने खेत की तस्वीर हमें भेजें."
            ),
        },
    },
    # ----------------------------------------------------------------- Bengali
    "bn": {
        "ui": {
            "ack": "Got it, checking your field 🌱\nআপনার জমি পরীক্ষা করা হচ্ছে...",
            "need_photo": (
                "🌱 *অন্নদাতা সেতু*\n\n"
                "ফসল পরীক্ষার জন্য অনুগ্রহ করে আক্রান্ত পাতার একটি পরিষ্কার ছবি পাঠান."
            ),
            "location_saved": (
                "📍 আপনার অবস্থান নথিভুক্ত হয়েছে.\n\n"
                "এখন আক্রান্ত পাতার একটি পরিষ্কার ছবি পাঠান."
            ),
            "language_set": "✅ ভাষা বাংলা করা হয়েছে. এবার পাতার ছবি পাঠান.",
        },
        "labels": {
            "header": "🌱 *অন্নদাতা সেতু | ফসল স্বাস্থ্য পরামর্শ*",
            "diagnosis": "🔍 *নির্ণয় (Diagnosis):*",
            "confidence": "📊 *নির্ভরযোগ্যতা (Confidence):*",
            "context": "📋 *বিশ্লেষণ (Context):*",
            "action": "*পরামর্শ (Action):*",
            "dosage": "💊 *মাত্রা (Dosage):*",
            "cost": "💰 *আনুমানিক খরচ:*",
            "urgency": "⏳ *সময়:* {hours} ঘণ্টার মধ্যে",
            "no_spray": "🎉 *স্প্রে করার দরকার নেই — অপ্রয়োজনীয় ওষুধের খরচ বাঁচান.*",
            "sources": "📚 *সূত্র:*",
        },
        "escalation_text": (
            "🌱 *অন্নদাতা সেতু | ফসল স্বাস্থ্য পরামর্শ*\n\n"
            "🔍 *নির্ণয় (Diagnosis):* অনিশ্চিত — পরীক্ষা চলছে\n\n"
            "🔬 *পরামর্শ (Action):*\n"
            "আপনার ছবি থেকে আমরা নিশ্চিতভাবে রোগ নির্ণয় করতে পারিনি.\n\n"
            "⚠️ *অনুগ্রহ করে এখন কোনো স্প্রে করবেন না.*\n"
            "আমাদের কৃষি বিশেষজ্ঞ আপনার ছবি দেখে শীঘ্রই পরামর্শ দেবেন.\n\n"
            "📷 সাহায্যের জন্য: দিনের আলোয়, আক্রান্ত পাতার কাছ থেকে পরিষ্কার ছবি আবার পাঠান."
        ),
        "voice": {
            "subject_known": "{disease} দেখা যাচ্ছে",
            "subject_unknown": "রোগের লক্ষণ দেখা যাচ্ছে",
            "dose_known": "{dosage} হারে মিশিয়ে স্প্রে করুন. ",
            "dose_unknown": "ওষুধের প্যাকেটে দেওয়া মাত্রা অনুযায়ী স্প্রে করুন. ",
            "dosage_pattern": "{per_qty} {per_unit} জলে {qty} {unit}",
            "dosage_pattern_single": "{per_qty} {per_unit} জলে {qty} {unit}",
            "treatment": (
                "নমস্কার. আপনার ফসলে {subject}. "
                "আবহাওয়ার আর্দ্রতার কারণে এটি দ্রুত ছড়িয়ে পড়তে পারে. "
                "{advice}{dose}"
                "এর আনুমানিক খরচ ₹{cost} এবং এই স্প্রে আগামী {hours} ঘণ্টার মধ্যে সম্পন্ন করুন."
            ),
            "dont_spray": (
                "নমস্কার. আপনার ফসলে {subject}. "
                "এটি রোগের সংক্রমণ নয়, পুষ্টির ঘাটতি. "
                "{advice}"
                "তাই কোনো রাসায়নিক স্প্রে করার প্রয়োজন নেই. "
                "এতে আপনার প্রায় ₹{saved} সাশ্রয় হবে."
            ),
            "escalation": (
                "নমস্কার. আমরা আপনার ছবিটি ভালোভাবে পরীক্ষা করতে পারিনি. "
                "তাই এখন কোনো স্প্রে করবেন না. "
                "আমাদের কৃষি বিশেষজ্ঞ আপনার ছবি দেখে শীঘ্রই পরামর্শ দেবেন. "
                "সম্ভব হলে দিনের আলোয় পাতার পরিষ্কার ছবি আবার পাঠান."
            ),
        },
        "alert": {
            "text": (
                "🚨 *সতর্কতা! পূর্বাভাস (Outbreak Alert)* 🚨\n\n"
                "আপনার এলাকায় ({district}) *{disease}* রোগের প্রাদুর্ভাব দেখা গেছে. "
                "মোট {count} টি জমিতে এই রোগ ছড়িয়েছে.\n\n"
                "🛡️ *প্রতিরোধমূলক ব্যবস্থা:* আপনার ফসল পরীক্ষা করুন. রোগ আপনার জমিতে "
                "পৌঁছানোর আগে সতর্কতামূলক স্প্রে করুন বা পাতার ছবি এখানে পাঠান."
            ),
            "voice": (
                "সতর্ক হোন! আপনার {district} এলাকায় {disease} রোগের প্রাদুর্ভাব শুরু হয়েছে. "
                "{count} টি জমিতে এই রোগ দেখা গেছে. "
                "রোগ আপনার ফসলে পৌঁছানোর আগে সতর্কতা নিন বা আপনার জমির ছবি আমাদের পাঠান."
            ),
        },
    },
    # ---------------------------------------------------------------- English
    "en": {
        "ui": {
            "ack": "Got it, checking your field 🌱",
            "need_photo": (
                "🌱 *Annadata Setu*\n\n"
                "Please send one clear photo of the affected leaf so we can check your crop."
            ),
            "location_saved": (
                "📍 Your location has been saved.\n\n"
                "Now send a clear photo of the affected leaf."
            ),
            "language_set": "✅ Language set to English. Now send a photo of the leaf.",
        },
        "labels": {
            "header": "🌱 *Annadata Setu | Crop Health Advisory*",
            "diagnosis": "🔍 *Diagnosis:*",
            "confidence": "📊 *Confidence:*",
            "context": "📋 *Context:*",
            "action": "*Action:*",
            "dosage": "💊 *Dosage:*",
            "cost": "💰 *Estimated cost:*",
            "urgency": "⏳ *Timeline:* within {hours} hours",
            "no_spray": "🎉 *No spray needed — save the cost of unnecessary chemicals.*",
            "sources": "📚 *Sources:*",
        },
        "escalation_text": (
            "🌱 *Annadata Setu | Crop Health Advisory*\n\n"
            "🔍 *Diagnosis:* Undetermined — under review\n\n"
            "🔬 *Action:*\n"
            "We could not reach a confident diagnosis from your photo.\n\n"
            "⚠️ *Please do not spray anything for now.*\n"
            "Our agronomist will review your photo and advise you shortly.\n\n"
            "📷 To help: send a close, clear photo of the affected leaf again, in daylight."
        ),
        "voice": {
            "subject_known": "{disease}",
            "subject_unknown": "symptoms of disease",
            "dose_known": "Spray at {dosage}. ",
            "dose_unknown": "Spray at the rate printed on the product label. ",
            "dosage_pattern": "{qty} {unit} per {per_qty} {per_unit} of water",
            "dosage_pattern_single": "{qty} {unit} per {per_unit} of water",
            "treatment": (
                "Hello. Your crop shows {subject}. "
                "Humidity in the forecast can spread it quickly. "
                "{advice}{dose}"
                "This will cost about {cost} rupees, and complete the spray within the next {hours} hours."
            ),
            "dont_spray": (
                "Hello. Your crop shows {subject}. "
                "This is not an infection but a nutrient deficiency. "
                "{advice}"
                "So no chemical spray is needed. "
                "That saves you about {saved} rupees."
            ),
            "escalation": (
                "Hello. We could not examine your photo properly. "
                "So please do not spray anything for now. "
                "Our agronomist will review your photo and advise you shortly. "
                "If you can, send a clear daylight photo of the affected leaf again."
            ),
        },
        "alert": {
            "text": (
                "🚨 *Outbreak Alert* 🚨\n\n"
                "An outbreak of *{disease}* has been detected in your area ({district}). "
                "It has spread across {count} fields.\n\n"
                "🛡️ *Protective steps:* Inspect your crop. Spray preventively before the "
                "disease reaches your field, or send a photo of a leaf here."
            ),
            "voice": (
                "Warning. An outbreak of {disease} has begun in your area, {district}. "
                "It has been seen in {count} fields. "
                "Take precautions before it reaches your crop, or send us a photo of your field."
            ),
        },
    },
}


def phrases(code: str = DEFAULT_LANGUAGE) -> Dict[str, Dict[str, str]]:
    """The phrase set for a language, falling back to the default."""
    return PHRASES.get(code, PHRASES[DEFAULT_LANGUAGE])


def ui(key: str, code: str = DEFAULT_LANGUAGE) -> str:
    return phrases(code)["ui"][key]


def label(key: str, code: str = DEFAULT_LANGUAGE) -> str:
    return phrases(code)["labels"][key]


def voice(key: str, code: str = DEFAULT_LANGUAGE) -> str:
    return phrases(code)["voice"][key]


def language_menu() -> str:
    """The chooser, listing every language in itself.

    Not localised, and deliberately so: a farmer who cannot read the current
    language is exactly the farmer who needs this message.
    """
    lines = ["🌐 *भाषा / Language*", ""]
    for lang in LANGUAGES.values():
        index = menu_position(lang.code)
        lines.append(f"{index}. {lang.endonym} — reply *{index}* or *{lang.english_name}*")
    return "\n".join(lines)
