import logging
import random
from typing import Optional
from app.ai_system.validation.schemas import ResponseStrategy

logger = logging.getLogger(__name__)

GREETINGS_AR_RESPONSES = [
    "مرحباً بك! يمكنني مساعدتك في تلخيص هذا الملف، شرح أجزائه، أو إنشاء اختبارات عليه. تفضل بطرح سؤالك.",
    "أهلاً بك! أنا هنا لمساعدتك في مذاكرة وفهم محتوى هذا المستند. كيف يمكنني مساعدتك اليوم؟",
    "مرحباً! أستطيع مساعدتك في مراجعة هذا الملف، استخراج النقاط الأساسية، أو الإجابة على أسئلتك حوله."
]

GREETINGS_EN_RESPONSES = [
    "Hello! I can help you summarize this document, explain sections, or generate quizzes. How can I help you today?",
    "Welcome! I am here to help you study and understand this document. How can I help you assist your learning?",
    "Hi there! I can help you review this file, extract key takeaways, or answer questions about its content. How can I help you today?"
]

ABUSE_AR_RESPONSES = [
    "أنا هنا لمساعدتك في فهم محتوى الملف المرفوع. نرجو الحفاظ على أسلوب محترم في التواصل لنتمكن من الاستمرار.",
    "يرجى استخدام لغة محترمة أثناء التواصل. تفضل بطرح أي سؤال يتعلق بمحتوى المستند وسأقوم بمساعدتك.",
    "أنا جاهز لمساعدتك في مراجعة المستند، ولكن يُرجى الحفاظ على الاحترام المتبادل في الحديث."
]

GENTLE_ABUSE_WARNING_AR = " (برجاء الحفاظ على أسلوب تواصل محترم)"
GENTLE_ABUSE_WARNING_EN = " (Please maintain a respectful communication style)"

ABUSE_EN_RESPONSES = [
    "I am here to help you understand the document. Please maintain a respectful tone so we can continue.",
    "Please use respectful language. Feel free to ask any questions related to the document's content.",
    "I am happy to assist you with the document, but please ensure we communicate respectfully."
]

INJECTION_AR_RESPONSES = [
    "عذراً، أنا مبرمج للعمل فقط كمساعد دراسي مرتبط بمحتوى هذا المستند ولا يمكنني كشف التعليمات الداخلية أو تجاوز الحدود الأمنية.",
    "غير مسموح لي بتخطي سياق هذا الملف أو كشف إعدادات النظام. يرجى سؤالي عن المحتوى التعليمي للمستند فقط."
]

INJECTION_EN_RESPONSES = [
    "I'm sorry, I am programmed to work only as a study companion bound to this document. I cannot bypass my grounding boundaries or reveal internal instructions.",
    "Bypassing the document boundaries or revealing system prompts is not permitted. Please ask about the educational content of this file."
]

AMBIGUOUS_AR_RESPONSES = [
    "يرجى تحديد جزء معين، أو رقم الصفحة، أو المفهوم الذي تود مني شرحه لتسهيل مساعدتك بدقة.",
    "السؤال غير واضح تماماً. هل يمكنك توضيح ما تقصده بالتحديد في المستند، أو ذكر القسم المعني؟"
]

AMBIGUOUS_EN_RESPONSES = [
    "Please specify the page number, section, or specific concept you want me to explain so I can assist you accurately.",
    "Your request is a bit ambiguous. Could you clarify what exactly you are referring to in the document?"
]

OUT_OF_SCOPE_AR_RESPONSES = [
    "لا يظهر في الملف الحالي محتوى كافٍ للإجابة عن هذا السؤال بشكل موثوق. يمكنك سؤالي عن موضوع آخر داخل المستند أو رفع ملف مرتبط بالموضوع.",
    "لم أجد في محتوى المستند ما يدعم إجابة واضحة عن السؤال. جرّب تحديد صفحة أو قسم معين، أو استخدم ملفًا يتناول هذا الموضوع."
]

OUT_OF_SCOPE_EN_RESPONSES = [
    "The current document does not provide enough supporting evidence to answer this question. Please ask about another topic inside the document.",
    "I couldn't find details supporting this query in the uploaded document. Try specifying a section or upload a document covering this topic."
]

NO_DOC_AR_RESPONSES = [
    "الرجاء رفع مستند PDF أو اختيار ملف أولاً لتتمكن من التحدث معه."
]

NO_DOC_EN_RESPONSES = [
    "Please upload a PDF document or select a file first to start chatting."
]

PROCESSING_AR_RESPONSES = [
    "المستند ما زال قيد المعالجة حالياً. يرجى الانتظار قليلاً أو المحاولة مرة أخرى لاحقاً."
]

PROCESSING_EN_RESPONSES = [
    "The document is still processing. Please wait a moment or try again later."
]

def compose_dynamic_response(strategy: ResponseStrategy, lang: str = "ar") -> str:
    """
    Composes deterministic validation responses using dynamic templates (Zero LLM calls).
    """
    # Deterministic templates selection using random (but seedable if needed)
    idx = random.randint(0, 100)
    
    if strategy == ResponseStrategy.generate_greeting_response:
        if lang == "ar":
            return GREETINGS_AR_RESPONSES[idx % len(GREETINGS_AR_RESPONSES)]
        return GREETINGS_EN_RESPONSES[idx % len(GREETINGS_EN_RESPONSES)]
        
    elif strategy == ResponseStrategy.generate_respectful_boundary:
        if lang == "ar":
            return ABUSE_AR_RESPONSES[idx % len(ABUSE_AR_RESPONSES)]
        return ABUSE_EN_RESPONSES[idx % len(ABUSE_EN_RESPONSES)]
        
    elif strategy == ResponseStrategy.block_prompt_injection:
        if lang == "ar":
            return INJECTION_AR_RESPONSES[idx % len(INJECTION_AR_RESPONSES)]
        return INJECTION_EN_RESPONSES[idx % len(INJECTION_EN_RESPONSES)]
        
    elif strategy == ResponseStrategy.generate_clarification:
        if lang == "ar":
            return AMBIGUOUS_AR_RESPONSES[idx % len(AMBIGUOUS_AR_RESPONSES)]
        return AMBIGUOUS_EN_RESPONSES[idx % len(AMBIGUOUS_EN_RESPONSES)]
        
    elif strategy == ResponseStrategy.generate_out_of_scope_response:
        if lang == "ar":
            return OUT_OF_SCOPE_AR_RESPONSES[idx % len(OUT_OF_SCOPE_AR_RESPONSES)]
        return OUT_OF_SCOPE_EN_RESPONSES[idx % len(OUT_OF_SCOPE_EN_RESPONSES)]
        
    elif strategy == ResponseStrategy.request_document_upload:
        return NO_DOC_AR_RESPONSES[0] if lang == "ar" else NO_DOC_EN_RESPONSES[0]
        
    elif strategy == ResponseStrategy.request_document_ready:
        return PROCESSING_AR_RESPONSES[0] if lang == "ar" else PROCESSING_EN_RESPONSES[0]
        
    # Default fallback
    if lang == "ar":
        return "لم أجد إجابة واضحة في الملف المرفوع."
    return "I could not find a clear answer in the uploaded file."
