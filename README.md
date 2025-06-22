# MM Law Chatbot API 🏛️⚖️

A production-ready FastAPI backend for a Burmese-language legal Q&A chatbot powered by Google Gemini AI with fallback YAML dataset and comprehensive logging.

## 🚀 Features

- **Multi-source Q&A System**: Google Gemini AI + Local YAML dataset fallback
- **Burmese Language Support**: Native Myanmar language processing
- **Rate Limiting**: 5 requests per minute per IP to prevent abuse
- **Comprehensive Logging**: All interactions logged to Supabase for analytics
- **Production-Ready**: CORS, error handling, health checks, auto-deployment
- **Scalable Architecture**: Docker containerized with horizontal scaling support

## 🛠️ Tech Stack

- **Backend**: FastAPI 0.104.1 + Uvicorn
- **AI**: Google Gemini Pro API
- **Database**: Supabase (PostgreSQL)
- **Rate Limiting**: SlowAPI
- **Deployment**: Render.com with auto-scaling
- **Containerization**: Docker

## 📋 Prerequisites

- Python 3.11+
- Google Gemini API Key
- Supabase Project (URL + Anon Key)
- Render.com account (for deployment)

## ⚡ Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd mm-law-chatbot-api
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Configuration

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
GOOGLE_API_KEY=your_google_gemini_api_key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
```

### 3. Supabase Database Setup

Run the SQL commands in `supabase_setup.sql` in your Supabase SQL editor to create the required tables and indexes.

### 4. Local Development

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API will be available at: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## 🔧 API Endpoints

### Health Check
```http
GET /health
```
**Response:**
```json
{
  "status": "ok",
  "timestamp": "2025-06-22T10:30:00.000Z",
  "environment": "development"
}
```

### Ask Question
```http
POST /ask
Content-Type: application/json

{
  "question": "ဥပဒေအရ ခိုးယူမှုအပြစ်ဒဏ်"
}
```

**Response:**
```json
{
  "answer": "မြန်မာနိုင်ငံ ဥပဒေအရ ခိုးယူမှုအတွက်...",
  "source": "ai"
}
```

**Rate Limits:** 5 requests per minute per IP

## 🚀 Deployment to Render

### Automatic Deployment

1. **Fork this repository**
2. **Connect to Render:**
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click "New" → "Web Service"
   - Connect your GitHub repository
   
3. **Configure Environment Variables:**
   ```
   GOOGLE_API_KEY=your_actual_api_key
   SUPABASE_URL=your_actual_supabase_url  
   SUPABASE_KEY=your_actual_supabase_key
   ENVIRONMENT=production
   ALLOWED_ORIGINS=https://yourdomain.com
   ```

4. **Deploy:**
   - Render will automatically use `render.yaml` configuration
   - Build and deployment happen automatically on every push to main branch

### Manual Docker Deploy

```bash
# Build Docker image
docker build -t mm-law-chatbot .

# Run container
docker run -p 8000:8000 \
  -e GOOGLE_API_KEY=your_key \
  -e SUPABASE_URL=your_url \
  -e SUPABASE_KEY=your_key \
  -e ENVIRONMENT=production \
  mm-law-chatbot
```

## 📊 Monitoring & Analytics

The API logs all interactions to Supabase with the following data:
- Question text and timestamp
- AI-generated or fallback answers
- Response source (ai/dataset/fallback/error)
- Response time metrics
- User IP addresses (for rate limiting)

Query the `chat_logs` table or use the `chat_analytics` view for insights.

## 🔒 Security Features

- **Rate Limiting**: IP-based request throttling
- **CORS Protection**: Environment-specific origin restrictions  
- **Input Validation**: Pydantic models with length/content checks
- **Error Sanitization**: No sensitive data exposure in error responses
- **Non-root Container**: Docker security best practices

## 🧪 Testing

```bash
# Install dev dependencies
pip install pytest httpx pytest-asyncio

# Run tests (create test_main.py)
pytest

# Test health endpoint
curl http://localhost:8000/health

# Test ask endpoint
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "ဥပဒေအရ ခိုးယူမှုအပြစ်ဒဏ်"}'
```

## 📈 Performance & Scaling

- **Auto-scaling**: Render scales instances based on CPU/memory usage
- **Connection Pooling**: Supabase handles database connection optimization
- **Async Operations**: FastAPI async/await for concurrent request handling
- **Caching**: Local YAML dataset cached in memory for fast lookups
- **Timeout Handling**: 30-second Gemini AI timeout with graceful fallback

## 🔧 Customization

### Adding New Legal Questions

Edit `questions_dataset.yaml`:

```yaml
- question: "နယ်မြေပိုင်ဆိုင်မှုအငြင်းပွား"
  answer: "နယ်မြေပိုင်ဆိုင်မှုအငြင်းအဆိုများကို..."
```

### Modifying Rate Limits

In `main.py`, change the limiter decorator:

```python
@limiter.limit("10/minute")  # Allow 10 requests per minute
async def ask_question(request: Request, question_req: QuestionRequest):
```

### Adding New Response Sources

Extend the `source` field in Pydantic models and database schema.

## 🐛 Troubleshooting

**Common Issues:**

1. **Gemini AI Not Responding:**
   - Check `GOOGLE_API_KEY` validity
   - Verify API quota limits
   - Review network connectivity

2. **Supabase Connection Failed:**
   - Validate `SUPABASE_URL` and `SUPABASE_KEY`
   - Ensure RLS policies allow service access
   - Check database table exists

3. **YAML Dataset Not Loading:**
   - Verify `questions_dataset.yaml` file exists
   - Check YAML syntax validity
   - Review file encoding (should be UTF-8)

4. **Rate Limiting Issues:**
   - Clear SlowAPI Redis cache if using external Redis
   - Check IP detection behind reverse proxy

## 📄 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the project
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📞 Support

For issues and questions:
- Create GitHub Issue
- Check logs: `docker logs <container-id>`
- Monitor Supabase dashboard for database issues

---

**Built for Myanmar Legal Tech** 🇲🇲 | **Production-Ready** ✅ | **AI-Powered** 🤖
