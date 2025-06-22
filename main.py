import os
import uuid
import yaml
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

import google.generativeai as genai
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# Global variables
supabase_client: Optional[Client] = None
questions_dataset: List[Dict[str, str]] = []
gemini_model = None

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Pydantic models
class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    
    @validator('question')
    def validate_question(cls, v):
        if not v.strip():
            raise ValueError('Question cannot be empty or whitespace only')
        return v.strip()

class AnswerResponse(BaseModel):
    answer: str
    source: str = Field(default="ai")  # "ai", "dataset", or "fallback"

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    environment: str

# Load YAML dataset
def load_questions_dataset() -> List[Dict[str, str]]:
    """Load questions from YAML file"""
    try:
        with open('questions_dataset.yaml', 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
            return data if isinstance(data, list) else []
    except FileNotFoundError:
        print("Warning: questions_dataset.yaml not found. Using empty dataset.")
        return []
    except yaml.YAMLError as e:
        print(f"Error loading YAML dataset: {e}")
        return []

# Search in local dataset
def search_in_dataset(question: str) -> Optional[str]:
    """Search for similar question in local dataset"""
    question_lower = question.lower()
    
    for item in questions_dataset:
        if isinstance(item, dict) and 'question' in item and 'answer' in item:
            # Simple similarity check - can be enhanced with fuzzy matching
            if question_lower in item['question'].lower() or item['question'].lower() in question_lower:
                return item['answer']
    
    return None

# Initialize Gemini AI
def initialize_gemini():
    """Initialize Google Gemini AI"""
    global gemini_model
    try:
        if GOOGLE_API_KEY:
            genai.configure(api_key=GOOGLE_API_KEY)
            gemini_model = genai.GenerativeModel('gemini-pro')
            print("✅ Gemini AI initialized successfully")
        else:
            print("⚠️ GOOGLE_API_KEY not found. Gemini AI disabled.")
    except Exception as e:
        print(f"❌ Failed to initialize Gemini AI: {e}")
        gemini_model = None

# Initialize Supabase
def initialize_supabase():
    """Initialize Supabase client"""
    global supabase_client
    try:
        if SUPABASE_URL and SUPABASE_KEY:
            supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            print("✅ Supabase initialized successfully")
        else:
            print("⚠️ Supabase credentials not found. Logging disabled.")
    except Exception as e:
        print(f"❌ Failed to initialize Supabase: {e}")
        supabase_client = None

# Supabase logging functions
async def log_question_to_supabase(question_id: str, question: str) -> bool:
    """Log question to Supabase"""
    if not supabase_client:
        return False
    
    try:
        result = supabase_client.table('chat_logs').insert({
            'id': question_id,
            'question': question,
            'timestamp': datetime.utcnow().isoformat(),
            'answer': None
        }).execute()
        return True
    except Exception as e:
        print(f"Error logging question to Supabase: {e}")
        return False

async def update_answer_in_supabase(question_id: str, answer: str, source: str) -> bool:
    """Update answer in Supabase log"""
    if not supabase_client:
        return False
    
    try:
        result = supabase_client.table('chat_logs').update({
            'answer': answer,
            'source': source,
            'answered_at': datetime.utcnow().isoformat()
        }).eq('id', question_id).execute()
        return True
    except Exception as e:
        print(f"Error updating answer in Supabase: {e}")
        return False

# Gemini AI query
async def query_gemini_ai(question: str, timeout: int = 30) -> Optional[str]:
    """Query Gemini AI with timeout"""
    if not gemini_model:
        return None
    
    try:
        # Create a prompt for Myanmar legal questions
        prompt = f"""သင်သည် မြန်မာနိုင်ငံ၏ ဥပဒေကြံ့ခိုင်မှုနှင့် ဥပဒေရေးရာ အကြံပေးပုဂ္គိုလ်ဖြစ်ပါသည်။ 
        မြန်မာနိုင်ငံ၏ ဥပဒေများ၊ အတုပ်များ၊ နှင့် ဥပဒေရေးရာ လုပ်ထုံးလုပ်နည်းများအပေါ် အခြေခံ၍ အောက်ပါမေးခွန်းကို ဖြေကြားပါ။

        မေးခွန်း: {question}

        ကျေးဇူးပြု၍ တိကျသော၊ အသုံးဝင်သော၊ နှင့် မြန်မာဘာသာဖြင့် ဖြေကြားပါ။ သင့်ဖြေကြားချက်သည် မြန်မာနိုင်ငံ၏ လက်ရှိဥပဒေများနှင့် ကိုက်ညီရမည်။"""

        # Use asyncio.wait_for for timeout
        response = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: gemini_model.generate_content(prompt)
            ),
            timeout=timeout
        )
        
        if response and response.text:
            return response.text.strip()
        return None
        
    except asyncio.TimeoutError:
        print("Gemini AI request timed out")
        return None
    except Exception as e:
        print(f"Error querying Gemini AI: {e}")
        return None

# Startup event
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print("🚀 Starting MM Law Chatbot API...")
    
    # Load dataset
    global questions_dataset
    questions_dataset = load_questions_dataset()
    print(f"📚 Loaded {len(questions_dataset)} questions from dataset")
    
    # Initialize services
    initialize_gemini()
    initialize_supabase()
    
    print("✅ MM Law Chatbot API started successfully")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down MM Law Chatbot API...")

# FastAPI app
app = FastAPI(
    title="MM Law Chatbot API",
    description="A Burmese-language legal Q&A chatbot powered by Google Gemini AI",
    version="1.0.0",
    lifespan=lifespan
)

# Add SlowAPI middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS configuration
if ENVIRONMENT == "development":
    origins = ["*"]
else:
    origins = [origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Routes
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="ok",
        timestamp=datetime.utcnow().isoformat(),
        environment=ENVIRONMENT
    )

@app.post("/ask", response_model=AnswerResponse)
@limiter.limit("5/minute")
async def ask_question(request: Request, question_req: QuestionRequest):
    """Main Q&A endpoint with rate limiting"""
    question = question_req.question
    question_id = str(uuid.uuid4())
    
    # Log question to Supabase
    await log_question_to_supabase(question_id, question)
    
    try:
        # First, search in local dataset
        dataset_answer = search_in_dataset(question)
        
        if dataset_answer:
            # Found in dataset
            await update_answer_in_supabase(question_id, dataset_answer, "dataset")
            return AnswerResponse(answer=dataset_answer, source="dataset")
        
        # Query Gemini AI
        ai_answer = await query_gemini_ai(question)
        
        if ai_answer:
            # Got answer from AI
            await update_answer_in_supabase(question_id, ai_answer, "ai")
            return AnswerResponse(answer=ai_answer, source="ai")
        
        # Fallback response
        fallback_answer = "ဝမ်းနည်းပါတယ်။ လောလောဆယ် သင့်မေးခွန်းအတွက် တိကျသော အဖြေ မပေးနိုင်ပါ။ ကျေးဇူးပြု၍ သင့်မေးခွန်းကို ပိုမို တိကျစွာ မေးကြည့်ပါ သို့မဟုတ် ဥပဒေကြံ့ခိုင်မှုနှင့် တိုင်ပင်ပါ။"
        
        await update_answer_in_supabase(question_id, fallback_answer, "fallback")
        return AnswerResponse(answer=fallback_answer, source="fallback")
        
    except Exception as e:
        # Log error and return error response
        error_message = "စနစ်အမှားဖြစ်ပွားနေပါသည်။ ကျေးဇူးပြု၍ ခဏစောင့်ပြီး ပြန်လည်ကြိုးစားပါ။"
        await update_answer_in_supabase(question_id, f"Error: {str(e)}", "error")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_message
        )

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler"""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "စနစ်အတွင်းပိုင်း အမှားဖြစ်ပွားနေပါသည်။",
            "status_code": 500
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
