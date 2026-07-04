# Task Types
TASK_CHAT_ANSWER = "chat_answer"
TASK_EXPLAIN = "explain"
TASK_SUMMARY = "summary"
TASK_QUIZ = "quiz"
TASK_ANSWER_TABLE = "answer_table"
TASK_KEY_POINTS = "key_points"
TASK_COMPARISON_TABLE = "comparison_table"
TASK_UNKNOWN = "unknown"

SUPPORTED_TASK_TYPES = {
    TASK_CHAT_ANSWER,
    TASK_EXPLAIN,
    TASK_SUMMARY,
    TASK_QUIZ,
    TASK_ANSWER_TABLE,
    TASK_KEY_POINTS,
    TASK_COMPARISON_TABLE,
    TASK_UNKNOWN
}

# Execution Modes
MODE_SINGLE = "single"
MODE_PARALLEL = "parallel"
MODE_SEQUENTIAL = "sequential"

SUPPORTED_EXECUTION_MODES = {
    MODE_SINGLE,
    MODE_PARALLEL,
    MODE_SEQUENTIAL
}

# Golden Rule Default No Answer response
NO_ANSWER_FALLBACK = "لم أجد إجابة واضحة في الملف المرفوع."

# Clarification defaults
CLARIFICATION_QUESTION_AR = "كيف يمكنني مساعدتك في محتوى هذا الملف؟"
CLARIFICATION_QUESTION_EN = "How can I help you with this document's content?"

# Keyword map for intent classification
KEYWORDS = {
    "ar": {
        TASK_SUMMARY: ["لخص", "ملخص", "تلخيص", "اختصر", "اختصار", "موجز"],
        TASK_QUIZ: ["اختبار", "كويز", "امتحان", "اسئلة", "أسئلة", "كوز"],
        TASK_ANSWER_TABLE: ["جدول اجابات", "جدول إجابات", "جدول الاجابات", "جدول الإجابات", "اجوبة", "أجوبة"],
        TASK_EXPLAIN: ["اشرح", "شرح", "وضح", "توضيح", "فسر", "تفسير"],
        TASK_KEY_POINTS: ["النقاط الرئيسية", "نقاط رئيسية", "أهم النقاط", "اهم النقاط", "افكار رئيسية"],
        TASK_COMPARISON_TABLE: ["جدول مقارنة", "مقارنة", "قارن", "جدول مقارنه"]
    },
    "en": {
        TASK_SUMMARY: ["summarize", "summary", "brief", "digest", "shorten"],
        TASK_QUIZ: ["quiz", "test", "exam", "question", "quizzes"],
        TASK_ANSWER_TABLE: ["answer table", "answers table", "solution table", "answer sheet"],
        TASK_EXPLAIN: ["explain", "explanation", "clarify", "describe"],
        TASK_KEY_POINTS: ["key points", "bullet points", "main ideas", "takeaways"],
        TASK_COMPARISON_TABLE: ["comparison table", "compare", "contrast"]
    }
}
