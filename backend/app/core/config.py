import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# التأكد من تحميل ملف .env تلقائياً عند تشغيل الباك اند
load_dotenv()

class Settings(BaseSettings):
    # نقرأ القيمة من الـ environment عشان نضمن الأمان وميبقاش hardcoded
    GROQ_API_KEY_VALIDATION: str = os.getenv("GROQ_API_KEY_VALIDATION", "")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
