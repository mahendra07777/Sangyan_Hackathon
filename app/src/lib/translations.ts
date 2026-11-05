export type SupportedLanguage = "English" | "Hindi" | "Hinglish";

type TranslationDictionary = {
  [key: string]: string;
};

const en: TranslationDictionary = {
  // Home
  "home.eyebrow": "Financial Intelligence For Bharat",
  "home.hero.title": "Turn complex financial information into clear understanding.",
  "home.hero.subtitle": "Upload a financial document, disclosure, screenshot, or report. Bharat extracts the facts, explains the concepts, and shows where the information came from.",
  "home.upload.processing": "Processing document...",
  "home.upload.drop": "Drop a document here",
  "home.upload.formats": "PDF · IMAGE · SCREENSHOT",
  "home.upload.button": "Upload Document",
  "home.live_preview": "Live Preview",
  "home.q1_results": "Q1 FY27 RESULTS",
  "home.revenue": "Revenue",
  "home.yoy_change": "+13.9% YoY",
  "home.preview.explanation": "Revenue increased 13.9% year over year.",
  "home.preview.why_matters": "Revenue describes the scale of business activity.",
  "home.preview.chat_reply": "Revenue simply means the total amount of money earned by the company this quarter.",
  "home.bharat_explains": "Bharat Explains",
  "home.why_it_matters": "Why it matters",
  "home.source_page": "Source · Page 4",
  "home.ask_bharat": "Ask Bharat",
  "home.explain_hindi": "\"Explain this in Hindi\"",
  "home.lang.sample": "\"What does revenue mean in simple terms?\"",
  "home.voice.sample": "\"What is the simple meaning of revenue?\"",
  
  "home.path.01": "UPLOAD",
  "home.path.01.sub": "Document",
  "home.path.02": "UNDERSTAND",
  "home.path.02.sub": "Facts",
  "home.path.03": "EXPLAIN",
  "home.path.03.sub": "Simple language",
  "home.path.04": "ASK",
  "home.path.04.sub": "Questions",
  "home.path.05": "LEARN",
  "home.path.05.sub": "Concepts",
  "home.path.06": "VERIFY",
  "home.path.06.sub": "Evidence",

  "home.diff.understand": "Understand",
  "home.diff.understand.sub": "Complex financial language becomes simple.",
  "home.diff.learn": "Learn",
  "home.diff.learn.sub": "Understand the concept behind the number.",
  "home.diff.verify": "Verify",
  "home.diff.verify.sub": "See exactly where the information came from.",

  "home.lang.title": "Language",
  "home.lang.heading": "Ask in the language you're comfortable with.",
  "home.voice.title": "Ask Bharat",
  "home.voice.heading": "Speak or type.",
  "home.voice.sub": "Understand financial information without needing financial jargon.",
  
  "home.cta.upload": "Upload Document",

  // Workspace
  "ws.back": "← Home",
  "ws.document": "Document",
  "ws.overview": "Overview",
  "ws.key_numbers": "Key Numbers",
  "ws.impact_lens": "Impact Lens",
  "ws.impact_lens.sub": "From a number to an understanding.",
  "ws.concept": "Financial Concept",
  "ws.why_matters": "Why it matters",
  "ws.questions": "Questions to explore",
  "ws.questions.health": "How does this affect overall health?",
  "ws.questions.causes": "What usually causes this to change?",
  "ws.verify": "Verify Source",
  "ws.ai_educator": "AI Educator",
  "ws.placeholder": "Ask about this document...",
  "ws.processing": "Processing...",
  "ws.processing_incomplete": "Processing incomplete.",
  
  "ws.evidence.title": "Source Evidence",
  "ws.evidence.close": "Close",
  "ws.evidence.claim": "Claim",
  "ws.evidence.exact": "Exact Document Text",
  "ws.evidence.reference": "Document Reference",
  "ws.evidence.source": "Source",
  "ws.evidence.ai_explanation": "AI Explanation",
  "ws.evidence.snippet_available": "Snippet available.",
  
  // Q&A
  "qa.greeting": "What would you like to understand?",
  "qa.q1": "Explain the key numbers",
  "qa.q2": "What changed this quarter?",
  "qa.q3": "Where did this number come from?",
  
  "ws.document_story": "Document Story",
  "ws.what_changed": "What Changed?",
  "ws.what_connects": "What Connects?",
  "ws.areas_to_understand": "Areas Worth Understanding",
  "ws.your_investigation": "Your Investigation",
  "ws.explore": "Explore",
  
  // Safety
  "safety.message": "Educational context only. This is not investment advice.",
  
  // Errors
  "error.network": "Network or server issue.",
  "error.failed": "Failed to process document"
};

const hi: TranslationDictionary = {
  "home.eyebrow": "भारत के लिए वित्तीय समझ",
  "home.hero.title": "जटिल वित्तीय जानकारी को आसानी से समझें।",
  "home.hero.subtitle": "कोई भी वित्तीय दस्तावेज़, रिपोर्ट या स्क्रीनशॉट अपलोड करें। भारत तथ्य निकालता है, अवधारणाओं को समझाता है, और जानकारी का स्रोत दिखाता है।",
  "home.upload.processing": "दस्तावेज़ का विश्लेषण किया जा रहा है...",
  "home.upload.drop": "दस्तावेज़ यहाँ छोड़ें",
  "home.upload.formats": "PDF · इमेज · स्क्रीनशॉट",
  "home.upload.button": "दस्तावेज़ अपलोड करें",
  "home.live_preview": "लाइव झलक (Live Preview)",
  "home.q1_results": "Q1 FY27 नतीजे",
  "home.revenue": "रेवेन्यू (Revenue)",
  "home.yoy_change": "+13.9% YoY (साल-दर-साल)",
  "home.preview.explanation": "कंपनी का राजस्व (Revenue) पिछले वर्ष की तुलना में 13.9% बढ़ा है।",
  "home.preview.why_matters": "रेवेन्यू यह दर्शाता है कि कंपनी का व्यापार कितना बड़ा और सक्रिय है।",
  "home.preview.chat_reply": "रेवेन्यू का सीधा मतलब है कि कंपनी ने इस तिमाही में कुल कितना पैसा कमाया है।",
  "home.bharat_explains": "भारत समझाता है",
  "home.why_it_matters": "यह क्यों महत्वपूर्ण है",
  "home.source_page": "स्रोत · पृष्ठ 4",
  "home.ask_bharat": "भारत से पूछें",
  "home.explain_hindi": "\"इसे हिंदी में समझाएं\"",
  "home.lang.sample": "\"रेवेन्यू का सीधा मतलब क्या है?\"",
  "home.voice.sample": "\"रेवेन्यू का सरल अर्थ क्या है?\"",

  "home.path.01": "अपलोड",
  "home.path.01.sub": "दस्तावेज़",
  "home.path.02": "समझें",
  "home.path.02.sub": "तथ्य",
  "home.path.03": "समझाएं",
  "home.path.03.sub": "सरल भाषा",
  "home.path.04": "पूछें",
  "home.path.04.sub": "प्रश्न",
  "home.path.05": "सीखें",
  "home.path.05.sub": "अवधारणाएं",
  "home.path.06": "प्रमाणित करें",
  "home.path.06.sub": "प्रमाण",

  "home.diff.understand": "समझें",
  "home.diff.understand.sub": "जटिल वित्तीय भाषा सरल बन जाती है।",
  "home.diff.learn": "सीखें",
  "home.diff.learn.sub": "नंबर के पीछे की अवधारणा को समझें।",
  "home.diff.verify": "प्रमाणित करें",
  "home.diff.verify.sub": "देखें कि जानकारी बिल्कुल कहाँ से आई है।",

  "home.lang.title": "भाषा",
  "home.lang.heading": "अपनी आरामदायक भाषा में पूछें।",
  "home.voice.title": "भारत से पूछें",
  "home.voice.heading": "बोलें या टाइप करें।",
  "home.voice.sub": "बिना कठिन वित्तीय शब्दों के सरल वित्तीय जानकारी समझें।",
  
  "home.cta.upload": "दस्तावेज़ अपलोड करें",

  "ws.back": "← होम",
  "ws.document": "दस्तावेज़",
  "ws.overview": "अवलोकन",
  "ws.key_numbers": "मुख्य संख्याएं",
  "ws.impact_lens": "इम्पैक्ट लेंस (Impact Lens)",
  "ws.impact_lens.sub": "एक नंबर से समझ तक।",
  "ws.concept": "वित्तीय अवधारणा",
  "ws.why_matters": "यह क्यों महत्वपूर्ण है",
  "ws.questions": "आगे जानने के प्रश्न",
  "ws.questions.health": "यह व्यापार के समग्र स्वास्थ्य को कैसे प्रभावित करता है?",
  "ws.questions.causes": "इसके बदलने का मुख्य कारण क्या होता है?",
  "ws.verify": "स्रोत प्रमाणित करें",
  "ws.ai_educator": "AI शिक्षक",
  "ws.placeholder": "इस दस्तावेज़ के बारे में पूछें...",
  "ws.processing": "प्रोसेस हो रहा है...",
  "ws.processing_incomplete": "दस्तावेज़ की प्रोसेसिंग अधूरी है।",

  "ws.evidence.title": "स्रोत प्रमाण",
  "ws.evidence.close": "बंद करें",
  "ws.evidence.claim": "दावा",
  "ws.evidence.exact": "सटीक दस्तावेज़ पाठ",
  "ws.evidence.reference": "दस्तावेज़ संदर्भ",
  "ws.evidence.source": "स्रोत",
  "ws.evidence.ai_explanation": "AI व्याख्या",
  "ws.evidence.snippet_available": "दस्तावेज़ का अंश उपलब्ध है।",

  "qa.greeting": "आप क्या समझना चाहते हैं?",
  "qa.q1": "मुख्य numbers को आसान भाषा में समझाइए",
  "qa.q2": "इस quarter में क्या बदला?",
  "qa.q3": "यह number कहाँ से आया?",

  "ws.document_story": "दस्तावेज़ का सार",
  "ws.what_changed": "क्या बदला?",
  "ws.what_connects": "क्या संबंध है?",
  "ws.areas_to_understand": "समझने योग्य क्षेत्र",
  "ws.your_investigation": "आपकी खोज",
  "ws.explore": "और जानें",

  "safety.message": "यह केवल शैक्षिक जानकारी है। यह निवेश सलाह नहीं है।",
  
  "error.network": "नेटवर्क या सर्वर की समस्या।",
  "error.failed": "दस्तावेज़ प्रोसेस करने में विफल"
};

const hinglish: TranslationDictionary = {
  "home.eyebrow": "Financial Intelligence Bharat Ke Liye",
  "home.hero.title": "Complex finance ko easily samajhiye.",
  "home.hero.subtitle": "Koi bhi financial document, report ya screenshot upload karein. Bharat facts nikalta hai, concepts samjhata hai, aur source dikhata hai.",
  "home.upload.processing": "Document analyze kiya ja raha hai...",
  "home.upload.drop": "Document yahan drop karein",
  "home.upload.formats": "PDF · IMAGE · SCREENSHOT",
  "home.upload.button": "Upload Document",
  "home.live_preview": "Live Preview",
  "home.q1_results": "Q1 FY27 RESULTS",
  "home.revenue": "Revenue (Kamai)",
  "home.yoy_change": "+13.9% YoY",
  "home.preview.explanation": "Company ka revenue pichle saal ke mukable 13.9% badh gaya.",
  "home.preview.why_matters": "Revenue se pata chalta hai ki company ka business kitna bada hai.",
  "home.preview.chat_reply": "Revenue ka simple matlab hai ki company ne is quarter mein kitna paisa kamaya hai.",
  "home.bharat_explains": "Bharat Explains",
  "home.why_it_matters": "Ye kyun matter karta hai",
  "home.source_page": "Source · Page 4",
  "home.ask_bharat": "Ask Bharat",
  "home.explain_hindi": "\"Iska simple meaning kya hai?\"",
  "home.lang.sample": "\"Revenue ka simple matlab kya hai?\"",
  "home.voice.sample": "\"Revenue ka simple meaning kya hai?\"",

  "home.path.01": "UPLOAD",
  "home.path.01.sub": "Document",
  "home.path.02": "UNDERSTAND",
  "home.path.02.sub": "Facts",
  "home.path.03": "EXPLAIN",
  "home.path.03.sub": "Simple language",
  "home.path.04": "ASK",
  "home.path.04.sub": "Questions",
  "home.path.05": "LEARN",
  "home.path.05.sub": "Concepts",
  "home.path.06": "VERIFY",
  "home.path.06.sub": "Evidence",

  "home.diff.understand": "Understand",
  "home.diff.understand.sub": "Complex financial language ab simple.",
  "home.diff.learn": "Learn",
  "home.diff.learn.sub": "Number ke peeche ka concept samjhein.",
  "home.diff.verify": "Verify",
  "home.diff.verify.sub": "Dekhein ki information kahan se aayi hai.",

  "home.lang.title": "Language",
  "home.lang.heading": "Apni comfortable language mein poochhein.",
  "home.voice.title": "Ask Bharat",
  "home.voice.heading": "Bolein ya type karein.",
  "home.voice.sub": "Financial jargon ke bina financial information samjhein.",
  
  "home.cta.upload": "Upload Document",

  // Workspace
  "ws.back": "← Home",
  "ws.document": "Document",
  "ws.overview": "Overview",
  "ws.key_numbers": "Key Numbers",
  "ws.impact_lens": "Impact Lens",
  "ws.impact_lens.sub": "Number se leke samajh tak.",
  "ws.concept": "Financial Concept",
  "ws.why_matters": "Ye kyun matter karta hai",
  "ws.questions": "Aage kya explore karein",
  "ws.questions.health": "Ye overall business health ko kaise affect karta hai?",
  "ws.questions.causes": "Iske change hone ka main reason kya hota hai?",
  "ws.verify": "Verify Source",
  "ws.ai_educator": "AI Educator",
  "ws.placeholder": "Is document ke baare mein poochhein...",
  "ws.processing": "Processing...",
  "ws.processing_incomplete": "Processing incomplete hai.",

  "ws.evidence.title": "Source Evidence",
  "ws.evidence.close": "Close",
  "ws.evidence.claim": "Claim",
  "ws.evidence.exact": "Exact Document Text",
  "ws.evidence.reference": "Document Reference",
  "ws.evidence.source": "Source",
  "ws.evidence.ai_explanation": "AI Explanation",
  "ws.evidence.snippet_available": "Snippet available hai.",

  "qa.greeting": "Aap kya samajhna chahenge?",
  "qa.q1": "Key numbers ko simple language mein samjhao",
  "qa.q2": "Is quarter mein kya change hua?",
  "qa.q3": "Ye number kahan se aaya?",

  "ws.document_story": "Document Story",
  "ws.what_changed": "Kya Change Hua?",
  "ws.what_connects": "Kya Connection Hai?",
  "ws.areas_to_understand": "Samajhne Wale Areas",
  "ws.your_investigation": "Aapki Investigation",
  "ws.explore": "Explore Karein",

  "safety.message": "Ye sirf educational information hai. Ye investment advice nahi hai.",
  
  "error.network": "Network ya server issue.",
  "error.failed": "Document process karne mein fail hua"
};

const dictionaries: Record<SupportedLanguage, TranslationDictionary> = {
  English: en,
  Hindi: hi,
  Hinglish: hinglish,
};

export function getTranslation(key: string, language: SupportedLanguage): string {
  const dict = dictionaries[language] || dictionaries.English;
  return dict[key] || dictionaries.English[key] || key;
}
