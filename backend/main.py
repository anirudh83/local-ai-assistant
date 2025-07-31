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
chatbot = pipeline("text-generation", model="gpt2", max_length=100, pad_token_id=50256)
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
        # Create a prompt for better responses
        prompt = f"Human: {message.message}\nAI Assistant:"
        
        # Generate response using the AI model with better parameters
        result = chatbot(
            prompt, 
            max_length=len(prompt.split()) + 40,
            num_return_sequences=1, 
            temperature=0.8,
            do_sample=True,
            repetition_penalty=1.2,
            no_repeat_ngram_size=3
        )
        
        # Get the AI's response
        full_text = result[0]['generated_text']
        
        # Extract just the AI's part
        if "AI Assistant:" in full_text:
            ai_response = full_text.split("AI Assistant:")[-1].strip()
        else:
            ai_response = full_text.replace(prompt, "").strip()
        
        # Clean up the response - stop at first newline or "Human:"
        ai_response = ai_response.split("\n")[0].strip()
        ai_response = ai_response.split("Human:")[0].strip()
        
        # If no good response, provide fallback
        if not ai_response or len(ai_response) < 3:
            ai_response = "I'm still learning! Could you rephrase that?"
        
        return {
            "response": ai_response,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        # Fallback to simple response if AI fails
        return {
            "response": f"AI Error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

# Run with: python main.py
if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Local AI Assistant Backend")
    print("📍 Server: http://127.0.0.1:8000")
    print("📍 API Docs: http://127.0.0.1:8000/docs")
    
    uvicorn.run(app, host="127.0.0.1", port=8000)