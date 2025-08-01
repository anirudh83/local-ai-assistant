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
        "model": "llama3.2:1b",
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
    """Call Llama 3.2 with optimized settings for speed"""
    
    # Shorter, more focused prompt for speed
    full_prompt = f"""You are a personal daily coach. 

User: "{user_message}"

Context: {context[:200]}...

Respond briefly and helpfully (under 80 words):"""

    try:
        response = requests.post(OLLAMA_URL, json={
            "model": "llama3.2:1b",  # Much faster model
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": 0.5,  # Lower for speed
                "max_tokens": 100,   # Much shorter
                "top_p": 0.9,       # More focused
                "repeat_penalty": 1.1
            }
        }, timeout=15)  # Even shorter timeout
        
        if response.status_code == 200:
            return response.json()["response"].strip()
        else:
            return "I'm thinking... can you try again?"
            
    except Exception as e:
        return "Quick response mode: I'm here to help! What do you need?"

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
    """Simplified routine extraction that actually works"""
    
    # Simple pattern matching for now - more reliable than complex AI parsing
    combined_text = (user_message + " " + ai_response).lower()
    
    routines_found = []
    
    # Look for time patterns and activities
    import re
    
    # Pattern: "wake up at 7am" or "7:00 wake up"
    wake_patterns = re.findall(r'(?:wake.*?(?:at\s*)?(\d{1,2}):?(\d{0,2})\s*(?:am|pm)?)|(?:(\d{1,2}):?(\d{0,2})\s*(?:am|pm)?.*?wake)', combined_text)
    
    for match in wake_patterns:
        hour = int(match[0] or match[2] or 7)
        minute = int(match[1] or match[3] or 0)
        if hour <= 12 and 'pm' not in combined_text:  # Assume AM for morning routines
            time_str = f"{hour:02d}:{minute:02d}"
            routines_found.append({
                "name": "Wake Up",
                "time": time_str,
                "message": "Good morning! Time to start your amazing day! ☀️"
            })
    
    # Pattern: "walk" with time
    walk_patterns = re.findall(r'walk.*?(?:at\s*)?(\d{1,2}):?(\d{0,2})', combined_text)
    for match in walk_patterns:
        hour = int(match[0])
        minute = int(match[1] or 0)
        time_str = f"{hour:02d}:{minute:02d}"
        routines_found.append({
            "name": "Morning Walk", 
            "time": time_str,
            "message": "Time for your energizing walk! 🚶‍♂️"
        })
    
    # Pattern: "breakfast" with time
    breakfast_patterns = re.findall(r'breakfast.*?(?:at\s*)?(\d{1,2}):?(\d{0,2})', combined_text)
    for match in breakfast_patterns:
        hour = int(match[0])
        minute = int(match[1] or 0)
        time_str = f"{hour:02d}:{minute:02d}"
        routines_found.append({
            "name": "Breakfast",
            "time": time_str, 
            "message": "Time for a healthy breakfast! 🍳"
        })
    
    # Save any found routines
    if routines_found:
        try:
            conn = sqlite3.connect('assistant.db')
            cursor = conn.cursor()
            
            saved_count = 0
            for routine in routines_found:
                # Check if routine already exists to avoid duplicates
                cursor.execute("SELECT id FROM routines WHERE name = ? AND time = ?", (routine['name'], routine['time']))
                if not cursor.fetchone():  # Only add if doesn't exist
                    cursor.execute(
                        "INSERT INTO routines (name, time, message, created_at) VALUES (?, ?, ?, ?)",
                        (routine['name'], routine['time'], routine['message'], datetime.now())
                    )
                    saved_count += 1
            
            conn.commit()
            conn.close()
            
            if saved_count > 0:
                print(f"✅ Extracted and saved {saved_count} new routines")
                
        except Exception as e:
            print(f"Error saving routines: {e}")

def extract_and_save_activities(ai_response, user_message):
    """Simplified activity extraction"""
    
    combined_text = (user_message + " " + ai_response).lower()
    
    activities_found = []
    
    # Look for meal mentions
    if any(word in combined_text for word in ['had', 'ate', 'breakfast', 'lunch', 'dinner', 'meal']):
        # Extract what they ate
        meal_text = user_message  # Use original user message
        activities_found.append({
            "category": "meal",
            "description": meal_text
        })
    
    # Look for exercise mentions  
    if any(word in combined_text for word in ['walk', 'run', 'gym', 'exercise', 'workout']):
        activities_found.append({
            "category": "exercise", 
            "description": "exercise activity mentioned"
        })
    
    # Save activities
    if activities_found:
        try:
            conn = sqlite3.connect('assistant.db')
            cursor = conn.cursor()
            
            for activity in activities_found:
                cursor.execute(
                    "INSERT INTO activities (date, category, description, timestamp) VALUES (?, ?, ?, ?)",
                    (datetime.now().date(), activity['category'], activity['description'], datetime.now())
                )
            
            conn.commit()
            conn.close()
            print(f"✅ Saved {len(activities_found)} activities")
            
        except Exception as e:
            print(f"Error saving activities: {e}")

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
    """Main chat endpoint - optimized for speed"""
    
    try:
        # Simpler context for speed
        context = "No context yet" if not message else "User has routines"
        
        # Simple system role - no complex analysis for basic greetings
        user_msg = message.message.lower().strip()
        
        if len(user_msg) < 10 and any(word in user_msg for word in ["hi", "hello", "hey"]):
            # Fast response for simple greetings
            ai_response = "Hi! I'm your daily coach. How can I help you today? Want to plan your day or set up some routines?"
        else:
            # Use AI for more complex requests
            system_role = "You are a helpful daily coach. Be brief and encouraging."
            ai_response = call_intelligent_coach(system_role, message.message, context)
        
        # Skip complex extraction for simple messages
        if len(user_msg) > 15:  # Only extract from longer messages
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
            "response": "Hi! I'm your daily coach. How can I help you today?",
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

@app.post("/clean-duplicates")
async def clean_duplicates():
    """Remove duplicate routines"""
    try:
        conn = sqlite3.connect('assistant.db')
        cursor = conn.cursor()
        
        # Remove duplicates - keep only the latest one for each name+time combination
        cursor.execute("""
            DELETE FROM routines 
            WHERE id NOT IN (
                SELECT MAX(id) 
                FROM routines 
                GROUP BY name, time
            )
        """)
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return {"message": f"Cleaned up {deleted_count} duplicate routines"}
        
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Intelligent Daily Coach")
    print("🧠 AI handles all parsing, analysis, and decisions")
    uvicorn.run(app, host="127.0.0.1", port=8000)