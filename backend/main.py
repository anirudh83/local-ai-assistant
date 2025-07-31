"""
Local AI Assistant - Simple Backend Test
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from transformers import pipeline

# Create FastAPI app
app = FastAPI(title="Local AI Assistant", version="0.1.0")

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load AI model (this will download on first run)
print("🤖 Loading AI model...")
chatbot = pipeline("text-generation", model="microsoft/DialoGPT-small", max_length=100)
print("✅ AI model loaded!")

# Simple data model
class ChatMessage(BaseModel):
    message: str

# Test endpoint
@app.get("/")
async def root():
    return {
        "message": "Local AI Assistant Backend is running!",
        "timestamp": datetime.now().isoformat(),
        "status": "healthy"
    }

@app.get("/health")
async def health():
    return {"status": "ok", "message": "Backend is healthy"}

@app.post("/chat")
async def chat(message: ChatMessage):
    # Use the AI model to generate response
    try:
        # Generate response using the AI model
        result = chatbot(message.message, max_length=50, num_return_sequences=1)
        
        # Get the AI's response (remove the input part)
        full_text = result[0]['generated_text']
        ai_response = full_text.replace(message.message, "").strip()
        
        # If no new text was generated, provide a fallback
        if not ai_response:
            ai_response = "I understand. Can you tell me more?"
        
        return {
            "response": ai_response,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        # Fallback to simple response if AI fails
        return {
            "response": f"AI Error: {str(e)}. Fallback: You said '{message.message}'",
            "timestamp": datetime.now().isoformat()
        }

# Run with: python main.py
if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Local AI Assistant Backend")
    print("📍 Server: http://127.0.0.1:8000")
    print("📍 API Docs: http://127.0.0.1:8000/docs")
    
    uvicorn.run(app, host="127.0.0.1", port=8000)