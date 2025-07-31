"""
Intelligent Daily Coach - Llama 3.2 Powered Backend
The AI handles all parsing, analysis, and decision making
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
import sqlite3
import json
import requests

app = FastAPI(title="Intelligent Daily Coach", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = "http://localhost:11434/api/generate"

print("🧠 Connecting to Intelligent Coach (Llama 3.2)...")
try:
    test_response = requests.post(OLLAMA_URL, json={
        "model": "llama3.2:3b",
        "prompt": "Hello",
        "stream": False
    }, timeout=10)
    if test_response.status_code == 200:
        print("✅ Intelligent Coach online!")
    else:
        print("❌ Coach offline. Run: ollama serve")
except Exception as e:
    print(f"❌ Cannot connect to coach: {e}")

def call_intelligent_coach(system_prompt, user_message, context=""):
    """Call Llama 3.2 with full context and intelligence"""
    
    full_prompt = f"""You are an intelligent personal daily coach. You understand natural language, analyze patterns, and take actions autonomously.

SYSTEM ROLE:
{system_prompt}

CURRENT CONTEXT:
{context}

USER MESSAGE: "{user_message}"

INSTRUCTIONS:
- Understand the user's intent deeply
- If they want to set routines, parse times and activities
- If they're sharing activities, extract relevant data
- Analyze patterns and provide insights
- Be warm, supportive, and proactive
- Keep responses under 150 words but be specific

RESPONSE:"""

    try:
        response = requests.post(OLLAMA_URL, json={
            "model": "llama3.2:3b",
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "max_tokens": 200
            }
        }, timeout=45)
        
        if response.status_code == 200:
            return response.json()["response"].strip()
        else:
            return "I'm having trouble processing that. Can you try again?"
            
    except Exception as e:
        return f"My brain is offline: {str(e)}"

def get_user_context():
    """Get comprehensive user context for AI decision making"""
    try:
        conn = sqlite3.connect('assistant.db')
        cursor = conn.cursor()
        
        # Get all routines
        cursor.execute("SELECT name, time, message, created_at FROM routines WHERE active = TRUE ORDER BY time")
        routines = cursor.fetchall()
        
        # Get recent activities (last 7 days)
        cursor.execute("""
            SELECT date, category, description, timestamp 
            FROM activities 
            WHERE date >= date('now', '-7 days') 
            ORDER BY timestamp DESC 
            LIMIT 20
        """)
        activities = cursor.fetchall()
        
        # Get conversation history (last 5)
        cursor.execute("""
            SELECT user_message, ai_response, timestamp 
            FROM conversations 
            ORDER BY timestamp DESC 
            LIMIT 5
        """)
        conversations = cursor.fetchall()
        
        conn.close()
        
        # Build comprehensive context
        context_parts = []
        
        current_time = datetime.now()
        context_parts.append(f"Current time: {current_time.strftime('%A, %B %d, %Y at %I:%M %p')}")
        
        if routines:
            routine_list = []
            for r in routines:
                routine_list.append(f"• {r[1]} - {r[0]}: {r[2]}")
            context_parts.append("CURRENT ROUTINES:\n" + "\n".join(routine_list))
        
        if activities:
            recent_activities = []
            for a in activities[:10]:  # Last 10 activities
                recent_activities.append(f"• {a[0]} - {a[2]} ({a[1]})")
            context_parts.append("RECENT ACTIVITIES:\n" + "\n".join(recent_activities))
        
        if conversations:
            context_parts.append("RECENT CONVERSATION CONTEXT:")
            for c in conversations[:3]:  # Last 3 exchanges
                context_parts.append(f"User: {c[0][:50]}...")
                context_parts.append(f"Coach: {c[1][:50]}...")
        
        return "\n\n".join(context_parts)
        
    except Exception as e:
        return f"Context error: {str(e)}"

def extract_and_save_routines(ai_response, user_message):
    """Let AI extract and save routines from conversation"""
    
    extraction_prompt = f"""Analyze this conversation and extract any routines or schedules the user wants to set up.

USER SAID: "{user_message}"
AI RESPONDED: "{ai_response}"

If any routines were mentioned, respond with a JSON array of routines in this EXACT format:
[
  {{"name": "Wake Up", "time": "07:00", "message": "Good morning! Time to start your day!"}},
  {{"name": "Morning Walk", "time": "07:30", "message": "Time for your energizing walk!"}}
]

If NO routines were mentioned, respond with: []

ONLY respond with the JSON array, nothing else:"""

    try:
        extraction_response = requests.post(OLLAMA_URL, json={
            "model": "llama3.2:3b",
            "prompt": extraction_prompt,
            "stream": False,
            "options": {"temperature": 0.3}
        }, timeout=30)
        
        if extraction_response.status_code == 200:
            extracted_text = extraction_response.json()["response"].strip()
            
            # Try to parse JSON from the response
            try:
                # Clean up the response - sometimes AI adds extra text
                json_start = extracted_text.find('[')
                json_end = extracted_text.rfind(']') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_text = extracted_text[json_start:json_end]
                    routines = json.loads(json_text)
                    
                    if routines:  # If we got valid routines
                        conn = sqlite3.connect('assistant.db')
                        cursor = conn.cursor()
                        
                        saved_count = 0
                        for routine in routines:
                            if all(key in routine for key in ['name', 'time', 'message']):
                                cursor.execute(
                                    "INSERT OR REPLACE INTO routines (name, time, message, created_at) VALUES (?, ?, ?, ?)",
                                    (routine['name'], routine['time'], routine['message'], datetime.now())
                                )
                                saved_count += 1
                        
                        conn.commit()
                        conn.close()
                        
                        if saved_count > 0:
                            print(f"✅ AI extracted and saved {saved_count} routines automatically")
                        
            except json.JSONDecodeError:
                pass  # No valid routines found, that's okay
                
    except Exception as e:
        print(f"Routine extraction error: {e}")

def extract_and_save_activities(ai_response, user_message):
    """Let AI extract and save activities from conversation"""
    
    extraction_prompt = f"""Analyze this conversation and extract any activities the user did or wants to log.

USER SAID: "{user_message}"
AI RESPONDED: "{ai_response}"

If any activities were mentioned (meals, exercise, mood, etc.), respond with a JSON array:
[
  {{"category": "meal", "description": "had oatmeal with berries for breakfast"}},
  {{"category": "exercise", "description": "20-minute morning walk in the park"}}
]

Valid categories: meal, exercise, mood, sleep, work, health

If NO activities were mentioned, respond with: []

ONLY respond with the JSON array:"""

    try:
        extraction_response = requests.post(OLLAMA_URL, json={
            "model": "llama3.2:3b",
            "prompt": extraction_prompt,
            "stream": False,
            "options": {"temperature": 0.3}
        }, timeout=30)
        
        if extraction_response.status_code == 200:
            extracted_text = extraction_response.json()["response"].strip()
            
            try:
                json_start = extracted_text.find('[')
                json_end = extracted_text.rfind(']') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_text = extracted_text[json_start:json_end]
                    activities = json.loads(json_text)
                    
                    if activities:
                        conn = sqlite3.connect('assistant.db')
                        cursor = conn.cursor()
                        
                        saved_count = 0
                        for activity in activities:
                            if all(key in activity for key in ['category', 'description']):
                                cursor.execute(
                                    "INSERT INTO activities (date, category, description, timestamp) VALUES (?, ?, ?, ?)",
                                    (datetime.now().date(), activity['category'], activity['description'], datetime.now())
                                )
                                saved_count += 1
                        
                        conn.commit()
                        conn.close()
                        
                        if saved_count > 0:
                            print(f"✅ AI extracted and saved {saved_count} activities automatically")
                        
            except json.JSONDecodeError:
                pass
                
    except Exception as e:
        print(f"Activity extraction error: {e}")

# Database setup
def init_db():
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS routines (
            id INTEGER PRIMARY KEY,
            name TEXT,
            time TEXT,
            message TEXT,
            active BOOLEAN DEFAULT TRUE,
            created_at DATETIME
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY,
            date DATE,
            category TEXT,
            description TEXT,
            timestamp DATETIME
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY,
            user_message TEXT,
            ai_response TEXT,
            timestamp DATETIME
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

class ChatMessage(BaseModel):
    message: str

@app.get("/")
async def root():
    return {"message": "Intelligent Daily Coach is running!"}

@app.get("/health")
async def health():
    return {"status": "healthy", "message": "Your intelligent coach is ready!"}

@app.post("/chat")
async def chat(message: ChatMessage):
    """Main chat endpoint - AI handles everything"""
    
    try:
        # Get full context for intelligent response
        context = get_user_context()
        
        # Let AI determine the system role based on the message
        user_msg = message.message.lower().strip()
        
        if any(word in user_msg for word in ["morning", "hello", "hi", "start"]):
            system_role = """You are starting a coaching session. Greet the user warmly, assess their energy/mood, and help them plan their day. Ask about how they're feeling and what they want to focus on."""
        
        elif any(word in user_msg for word in ["routine", "schedule", "plan", "set up", "remind"]):
            system_role = """You are helping the user create or modify their daily routines. Parse their requests carefully and set up specific times and activities. Be encouraging about building sustainable habits."""
        
        elif any(word in user_msg for word in ["had", "ate", "did", "went", "finished"]):
            system_role = """The user is sharing something they did. Acknowledge it positively, log the activity, and potentially give encouraging feedback or suggestions."""
        
        elif any(word in user_msg for word in ["how", "progress", "week", "summary", "analysis"]):
            system_role = """Analyze the user's patterns and progress. Look at their recent activities and routines to provide insights, celebrate wins, and suggest improvements."""
        
        else:
            system_role = """You are a supportive daily coach. Listen to the user's needs and respond with helpful guidance. Be proactive in suggesting routines or activities that could help them."""
        
        # Get intelligent response from AI
        ai_response = call_intelligent_coach(system_role, message.message, context)
        
        # Let AI automatically extract and save any routines or activities
        extract_and_save_routines(ai_response, message.message)
        extract_and_save_activities(ai_response, message.message)
        
        # Save conversation
        try:
            conn = sqlite3.connect('assistant.db')
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversations (user_message, ai_response, timestamp) VALUES (?, ?, ?)",
                (message.message, ai_response, datetime.now())
            )
            conn.commit()
            conn.close()
        except:
            pass
        
        return {
            "response": ai_response,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "response": f"I'm having trouble processing that right now. Error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

@app.get("/routines")
async def get_routines():
    """Simple endpoint to show current routines"""
    try:
        conn = sqlite3.connect('assistant.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name, time, message FROM routines WHERE active = TRUE ORDER BY time")
        routines = cursor.fetchall()
        conn.close()
        
        return {
            "routines": [
                {"name": r[0], "time": r[1], "message": r[2]}
                for r in routines
            ]
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug")
async def debug():
    """Debug endpoint to see what AI has learned"""
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM routines ORDER BY created_at DESC")
    routines = cursor.fetchall()
    
    cursor.execute("SELECT * FROM activities ORDER BY timestamp DESC LIMIT 10")
    activities = cursor.fetchall()
    
    conn.close()
    
    return {
        "total_routines": len(routines),
        "routines": routines,
        "recent_activities": activities,
        "context_sample": get_user_context()[:500] + "..."
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Intelligent Daily Coach")
    print("🧠 AI handles all parsing, analysis, and decisions")
    uvicorn.run(app, host="127.0.0.1", port=8000)