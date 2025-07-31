from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta, date
import sqlite3
import re
import json
import requests
import random

# Register adapters and converters to handle datetime in sqlite3 without warnings
import sqlite3
import datetime as dt

sqlite3.register_adapter(dt.datetime, lambda val: val.isoformat())
sqlite3.register_converter("timestamp", lambda val: dt.datetime.fromisoformat(val.decode("utf-8")))

sqlite3.register_adapter(dt.date, lambda val: val.isoformat())
sqlite3.register_converter("date", lambda val: dt.date.fromisoformat(val.decode("utf-8")))


app = FastAPI(title="Personal AI Assistant", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production to trusted origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ollama API endpoint for Llama 3.2 (adjust if needed)
OLLAMA_URL = "http://localhost:11434/api/generate"

print("🤖 Connecting to Llama 3.2...")
try:
    # Test connection to Ollama
    test_response = requests.post(
        OLLAMA_URL,
        json={"model": "llama3.2:3b", "prompt": "Hello", "stream": False},
        timeout=10,
    )
    if test_response.status_code == 200:
        print("✅ Llama 3.2 connected successfully!")
    else:
        print("❌ Ollama not responding. Make sure 'ollama serve' is running.")
except Exception as e:
    print(f"❌ Cannot connect to Ollama: {e}")
    print("Run: ollama serve")

def call_llama(prompt: str) -> str:
    """Call Llama 3.2 via Ollama endpoint"""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": "llama3.2:3b",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "max_tokens": 150},
            },
            timeout=30,
        )
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        else:
            return "I'm having trouble thinking right now. Can you try again?"
    except Exception as e:
        return f"My brain is offline. Error: {str(e)}"

def init_db():
    """Initialize database and tables if not exist"""
    conn = sqlite3.connect(
        'assistant.db', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
    )
    cursor = conn.cursor()

    # Create tables with proper datetime/date types
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS routines (
            id INTEGER PRIMARY KEY,
            name TEXT,
            time TEXT,
            message TEXT,
            active BOOLEAN DEFAULT TRUE,
            created_at timestamp
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY,
            date date,
            category TEXT,
            description TEXT,
            timestamp timestamp
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY,
            user_message TEXT,
            ai_response TEXT,
            timestamp timestamp
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            name TEXT,
            time TEXT,
            date date,
            is_done BOOLEAN DEFAULT FALSE,
            created_at timestamp
        )
    ''')

    conn.commit()
    conn.close()

init_db()

class ChatMessage(BaseModel):
    message: str

@app.get("/")
async def root():
    return {"message": "Personal AI Assistant is running!"}

@app.get("/health")
async def health():
    return {"status": "healthy", "message": "Your AI assistant is ready!"}

@app.post("/chat")
async def chat(message: ChatMessage):
    user_msg = message.message.lower().strip()
    try:
        if any(word in user_msg for word in ["good morning", "morning", "hello", "hi"]) and len(user_msg) < 20:
            response = generate_morning_greeting()
        elif any(word in user_msg for word in ["wake", "alarm", "morning"]):
            response = handle_wake_up_routine(user_msg)
        elif any(word in user_msg for word in ["plan", "schedule", "day"]):
            response = create_day_plan()
        elif any(word in user_msg for word in ["had", "ate", "breakfast", "lunch", "dinner", "meal"]):
            response = log_activity(user_msg, "meal")
        elif any(word in user_msg for word in ["exercise", "gym", "walk", "run", "workout"]):
            response = log_activity(user_msg, "exercise")
        elif any(word in user_msg for word in ["week", "summary", "progress"]):
            response = generate_weekly_summary()
        elif any(word in user_msg for word in ["routine", "remind"]):
            response = show_routines()
        elif contains_time_event(user_msg):
            response = log_task(user_msg)
        else:
            response = generate_smart_response(user_msg)

        save_conversation(message.message, response)

        return {"response": response, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {
            "response": f"Oops! My brain had a hiccup: {str(e)}. Can you try rephrasing?",
            "timestamp": datetime.now().isoformat(),
        }

def generate_morning_greeting() -> str:
    """Generate personalized morning greeting using Llama 3.2"""
    context = get_user_context()
    current_time = datetime.now()
    day_name = current_time.strftime("%A")
    prompt = f"""You are a personal morning coach. The user just said hello/good morning.
Context about the user:
{context}
It's {day_name} morning. Generate an encouraging, personalized morning greeting that:
1. Acknowledges the day
2. References their recent patterns if any
3. Asks how they're feeling
4. Suggests what they might want to focus on today
Keep it warm, personal, and under 100 words.
Greeting:"""
    return call_llama(prompt)

def handle_wake_up_routine(message: str) -> str:
    """Extract wake-up time and save as a routine"""
    time_pattern = r'(\d{1,2})(?::(\d{1,2}))?\s?(am|pm)?'
    time_match = re.search(time_pattern, message)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        ampm = time_match.group(3)
        if ampm == 'pm' and hour != 12:
            hour += 12
        elif ampm == 'am' and hour == 12:
            hour = 0
        time_str = f"{hour:02d}:{minute:02d}"

        conn = sqlite3.connect('assistant.db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO routines (name, time, message, created_at) VALUES (?, ?, ?, ?)",
            ("Wake Up", time_str, "Good morning! Time to start your amazing day! ☀️", datetime.now()),
        )
        conn.commit()
        conn.close()

        return f"✅ Perfect! I've set your wake-up routine for {time_str}. I'll help you start each day with energy!"
    else:
        return "I'd love to help you wake up! What time should I wake you? (e.g., '7am' or '7:30am')"

def create_day_plan() -> str:
    """Generate the user's day plan combining routines and today's tasks"""
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    # Get active routines
    cursor.execute("SELECT name, time FROM routines WHERE active = TRUE")
    routines = cursor.fetchall()

    today = datetime.now().date()
    cursor.execute("SELECT name, time FROM tasks WHERE date = ? ORDER BY time", (today,))
    tasks = cursor.fetchall()

    conn.close()

    # Combine and sort by time
    all_items = []
    for name, time_str in routines:
        if time_str:
            all_items.append((name, time_str))
    for name, time_str in tasks:
        if time_str:
            all_items.append((name, time_str))
    # convert time 'HH:MM' to minutes for sorting
    def time_key(t):
        parts = t[1].split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]) * 60 + int(parts[1])
        return 0
    all_items.sort(key=time_key)

    if all_items:
        plan = "Here's your personalized day plan:\n\n"
        for name, time_str in all_items:
            plan += f"🕐 {time_str} - {name}\n"
        plan += "\n💡 Suggestions to optimize your day:\n"
        plan += "• Drink water first thing in the morning\n"
        plan += "• Take breaks every 2 hours\n"
        plan += "• Get some sunlight midday\n"
        plan += "• Wind down 30 mins before bed"
        return plan
    else:
        return "No events or routines found for today. Start adding tasks or routines!"

def log_activity(message: str, category: str) -> str:
    """Extract activity description and log a meal or exercise"""
    # Remove trigger words
    activity = re.sub(r'\b(i had|i ate|had)\b', '', message, flags=re.IGNORECASE).strip()
    if not activity:
        activity = category  # fallback

    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO activities (date, category, description, timestamp) VALUES (?, ?, ?, ?)",
        (datetime.now().date(), category, activity, datetime.now()),
    )
    conn.commit()
    conn.close()

    encouragement = {
        "meal": ["Great choice!", "Fueling your body well!", "Healthy eating builds healthy habits!"],
        "exercise": ["You're crushing it!", "Every step counts!", "Your body will thank you!"],
    }

    praise = random.choice(encouragement.get(category, ["Well done!"]))
    return f"✅ {praise} I've logged: {activity}. Keep up the great work!"

def generate_weekly_summary() -> str:
    """Summarize activities of the last 7 days"""
    week_ago = datetime.now() - timedelta(days=7)
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT category, COUNT(*) FROM activities WHERE timestamp >= ? GROUP BY category",
        (week_ago,),
    )
    stats = cursor.fetchall()
    conn.close()

    if stats:
        summary = "📊 Your week in review:\n\n"
        for category, count in stats:
            summary += f"• {category.title()}: {count} entries\n"
        summary += "\n🌟 You're building great habits! Consistency is key to reaching your goals."
        return summary
    else:
        return "You haven't logged much this week yet. Start tracking your meals and activities - I'll help you spot patterns!"

def show_routines() -> str:
    """Return a formatted string listing current active routines"""
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, time, message FROM routines WHERE active = TRUE ORDER BY time")
    routines = cursor.fetchall()
    conn.close()

    if routines:
        response = "📅 Your current routines:\n\n"
        for name, time_str, message in routines:
            response += f"🕐 {time_str} - {name}: {message}\n"
        return response
    else:
        return "You don't have any routines set yet. Try saying 'wake me up at 7am' to get started!"

def generate_smart_response(message: str) -> str:
    """Use Llama 3.2 for intelligent responses"""
    context = get_user_context()
    prompt = f"""You are a supportive personal life coach and morning assistant. You help people start their day well and build healthy routines.
Context about the user:
{context}
User message: "{message}"
Respond as a caring, encouraging coach. Keep responses under 100 words. Be specific and actionable.
Response:"""
    return call_llama(prompt)

def get_user_context() -> str:
    """Get recent user patterns for context"""
    try:
        conn = sqlite3.connect('assistant.db')
        cursor = conn.cursor()
        cursor.execute("SELECT category, description FROM activities WHERE date >= date('now', '-7 days') ORDER BY timestamp DESC LIMIT 5")
        activities = cursor.fetchall()
        cursor.execute("SELECT name, time FROM routines WHERE active = TRUE")
        routines = cursor.fetchall()
        conn.close()

        context_parts = []
        if routines:
            context_parts.append("User's routines: " + ", ".join([f"{r[0]} at {r[1]}" for r in routines]))
        if activities:
            context_parts.append("Recent activities: " + ", ".join([f"{a[1]} ({a[0]})" for a in activities]))
        return "\n".join(context_parts) if context_parts else "No previous context available."

    except Exception:
        return "No context available."

def save_conversation(user_msg: str, ai_response: str) -> None:
    """Save chat conversation to database, ignore failing silently"""
    try:
        conn = sqlite3.connect('assistant.db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversations (user_message, ai_response, timestamp) VALUES (?, ?, ?)",
            (user_msg, ai_response, datetime.now()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

def contains_time_event(message: str) -> bool:
    """Heuristic to detect if the user message matches a time-based event/task e.g. 'meeting at 2pm'"""
    # Simple regex to detect time mentions like "at 2pm"," at 14:00", etc.
    time_pattern = r'\b(at|by|around)?\s*\d{1,2}(:\d{2})?\s?(am|pm)?\b'
    return bool(re.search(time_pattern, message, re.IGNORECASE))

def parse_time_from_text(text: str):
    """Extract time string (HH:MM) from user text if any, else None"""
    time_pattern = r'(\d{1,2})(?::(\d{2}))?\s?(am|pm)?'
    match = re.search(time_pattern, text, re.IGNORECASE)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        ampm = match.group(3)
        if ampm:
            ampm = ampm.lower()
            if ampm == 'pm' and hour != 12:
                hour += 12
            elif ampm == 'am' and hour == 12:
                hour = 0
        return f"{hour:02d}:{minute:02d}"
    return None

def log_task(message: str) -> str:
    """Parse and save a time-based task to the tasks table"""
    # Attempt to extract time
    time_str = parse_time_from_text(message)
    if not time_str:
        return "I couldn't understand the time for that task. Please specify (e.g., 'Meeting with Iliaz at 2pm')."
    # Extract task description by removing time phrase
    # Remove the time part from message for task name
    task_name = re.sub(r'\b(at|by|around)?\s*\d{1,2}(:\d{2})?\s?(am|pm)?\b', '', message, flags=re.IGNORECASE).strip(" ,.-")
    if not task_name:
        task_name = "Task"

    today = datetime.now().date()
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (name, time, date, is_done, created_at) VALUES (?, ?, ?, ?, ?)",
        (task_name.capitalize(), time_str, today, False, datetime.now()),
    )
    conn.commit()
    conn.close()
    return f"✅ Got it! I've added task '{task_name.capitalize()}' at {time_str} to your day plan."

@app.get("/debug")
async def debug():
    """Debug endpoint to view current database contents"""
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM routines")
    routines = cursor.fetchall()
    cursor.execute("SELECT * FROM activities ORDER BY timestamp DESC LIMIT 10")
    activities = cursor.fetchall()
    cursor.execute("SELECT * FROM tasks ORDER BY date DESC, time ASC LIMIT 10")
    tasks = cursor.fetchall()
    conn.close()

    return {
        "routines": routines,
        "activities": activities,
        "tasks": tasks,
    }

if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting your personal AI assistant")
    print("💬 Chat at: http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
