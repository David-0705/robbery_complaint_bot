#!/usr/bin/env python3
"""
Enhanced Flask Backend with Debug Information
Connects your existing RobberyComplaintBot to a web frontend with better error handling
"""
import os
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import requests
from datetime import datetime
import threading
import time
import uuid
import traceback

# Import your existing bot
from robbery_complaint_bot import RobberyComplaintBot

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Store active chat sessions
active_sessions = {}

class ChatSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.bot = RobberyComplaintBot()  # Your bot instance
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.conversation_started = False
    
    def update_activity(self):
        self.last_activity = datetime.now()

def cleanup_old_sessions():
    """Clean up sessions older than 1 hour"""
    current_time = datetime.now()
    sessions_to_remove = []
    
    for session_id, session in active_sessions.items():
        time_diff = (current_time - session.last_activity).total_seconds()
        if time_diff > 3600:  # 1 hour
            sessions_to_remove.append(session_id)
    
    for session_id in sessions_to_remove:
        del active_sessions[session_id]

def get_or_create_session(session_id: str) -> ChatSession:
    """Get existing session or create new one"""
    cleanup_old_sessions()
    
    if session_id not in active_sessions:
        active_sessions[session_id] = ChatSession(session_id)
    
    session = active_sessions[session_id]
    session.update_activity()
    return session

def test_ollama_connection():
    """Test Ollama connection and return detailed info"""
    try:
        # Test basic connection
        response = requests.get("http://localhost:11434", timeout=5)
        if response.status_code != 200:
            return False, f"Ollama responded with status {response.status_code}"
        
        # Test model availability
        models_response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if models_response.status_code == 200:
            models = models_response.json()
            available_models = [model['name'] for model in models.get('models', [])]
            
            # Test generation
            test_bot = RobberyComplaintBot()
            test_response = test_bot.call_ollama("Hello")
            
            if test_response in ["OLLAMA_ERROR", "CONNECTION_ERROR"]:
                return False, f"Ollama generation failed. Available models: {available_models}"
            
            return True, f"Ollama working. Available models: {available_models}, Test response: {test_response[:50]}..."
        else:
            return False, "Could not fetch model list"
            
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Ollama at http://localhost:11434"
    except Exception as e:
        return False, f"Ollama test error: {str(e)}"

@app.route('/')
def index():
    """Serve the frontend HTML with debug info"""
    try:
        if os.path.exists('templates/index.html'):
            with open('templates/index.html', 'r', encoding='utf-8') as f:
                return render_template_string(f.read())
        else:
            # Get debug info
            ollama_working, ollama_msg = test_ollama_connection()
            
            try:
                bot = RobberyComplaintBot()
                db_status = f"✅ Database connected, {bot.get_complaint_count()} complaints"
            except Exception as e:
                db_status = f"❌ Database error: {e}"
            
            return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Robbery Complaint System - Debug</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            text-align: center;
            margin-bottom: 30px;
        }
        .status {
            background: #e8f5e8;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            border-left: 4px solid #27ae60;
        }
        .error {
            background: #ffe8e8;
            border-left-color: #e74c3c;
        }
        .debug {
            background: #e8f4fd;
            border-left-color: #3498db;
            font-family: monospace;
            white-space: pre-wrap;
        }
        .endpoints {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            margin: 20px 0;
        }
        .endpoint {
            margin: 10px 0;
            font-family: monospace;
            background: white;
            padding: 8px;
            border-radius: 3px;
        }
        a {
            color: #3498db;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚔 Robbery Complaint System - Debug Mode</h1>
        
        <div class="status {{ 'error' if not ollama_working else '' }}">
            <h3>🤖 Ollama Status:</h3>
            <p>{{ '❌' if not ollama_working else '✅' }} {{ ollama_msg }}</p>
        </div>
        
        <div class="status">
            <h3>💾 Database Status:</h3>
            <p>{{ db_status }}</p>
        </div>

        <div class="debug">
            <h3>🔍 Debug Information:</h3>
Server URL: http://localhost:5000
Bot File: robbery_complaint_bot.py
Using: Your original RobberyComplaintBot

{% if not ollama_working %}
⚠️ ISSUE DETECTED: Ollama is not working properly!

This is why you're seeing "OLLAMA_ERROR" and simple responses.

SOLUTIONS:
1. Check if Ollama is running: Open terminal and run 'ollama list'
2. If not installed: Visit https://ollama.ai and install Ollama
3. If installed but not running: Run 'ollama serve' in terminal
4. Check your bot's model name - it should match an installed model
5. Try running your bot in terminal first to confirm it works

CURRENT BOT SETTINGS:
- Ollama URL: http://localhost:11434
- Model: Check your robbery_complaint_bot.py for the model name
{% endif %}
        </div>

        <div class="endpoints">
            <h3>📡 Available API Endpoints:</h3>
            <div class="endpoint"><strong>GET</strong> / - This debug page</div>
            <div class="endpoint"><strong>GET</strong> /api/status - System status check</div>
            <div class="endpoint"><strong>GET</strong> /api/debug - Detailed debug info</div>
            <div class="endpoint"><strong>POST</strong> /api/chat/start - Initialize new chat session</div>
            <div class="endpoint"><strong>POST</strong> /api/chat/message - Send message to chatbot</div>
            <div class="endpoint"><strong>POST</strong> /api/chat/reset - Reset current session</div>
            <div class="endpoint"><strong>GET</strong> /api/complaints/count - Get total complaints count</div>
        </div>

        <div class="status">
            <h3>🛠️ Quick Fixes:</h3>
            <ol>
                <li><strong>Test your bot directly:</strong> Run 'python robbery_complaint_bot.py' first</li>
                <li><strong>Check Ollama:</strong> Run 'ollama list' to see installed models</li>
                <li><strong>Start Ollama:</strong> Run 'ollama serve' if it's not running</li>
                <li><strong>Model mismatch:</strong> Make sure your bot uses an installed model</li>
                <li><strong>Create frontend:</strong> Add templates/index.html for the full UI</li>
            </ol>
        </div>
    </div>
</body>
</html>
            """, ollama_working=ollama_working, ollama_msg=ollama_msg, db_status=db_status)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f"Error loading template: {str(e)}"
        })

@app.route('/api/debug', methods=['GET'])
def get_debug_info():
    """Get detailed debug information"""
    debug_info = {}
    
    try:
        # Test your bot
        bot = RobberyComplaintBot()
        debug_info['bot_initialized'] = True
        debug_info['bot_config'] = {
            'ollama_url': bot.ollama_url,
            'model': bot.model,
            'required_fields_count': len(bot.required_fields),
            'use_simple_responses': bot.use_simple_responses
        }
        
        # Test database
        db_conn = bot.create_database_connection()
        debug_info['database_connected'] = db_conn is not None
        if db_conn:
            db_conn.close()
            debug_info['complaint_count'] = bot.get_complaint_count()
        
        # Test Ollama in detail
        ollama_working, ollama_msg = test_ollama_connection()
        debug_info['ollama_status'] = {
            'working': ollama_working,
            'message': ollama_msg
        }
        
        # Test a simple generation
        test_response = bot.call_ollama("Test message")
        debug_info['ollama_test'] = {
            'response': test_response,
            'is_error': test_response in ["OLLAMA_ERROR", "CONNECTION_ERROR"]
        }
        
    except Exception as e:
        debug_info['error'] = str(e)
        debug_info['traceback'] = traceback.format_exc()
    
    return jsonify({
        'status': 'success',
        'debug_info': debug_info,
        'active_sessions': len(active_sessions)
    })

@app.route('/api/status', methods=['GET'])
def get_status():
    """Check system status"""
    try:
        # Test database connection using your bot
        bot = RobberyComplaintBot()
        db_connected = bot.create_database_connection() is not None
        
        # Test Ollama connection
        ollama_working, ollama_msg = test_ollama_connection()
        
        # Get complaint count using your bot
        complaint_count = bot.get_complaint_count()
        
        return jsonify({
            'status': 'success',
            'database_connected': db_connected,
            'ollama_connected': ollama_working,
            'ollama_message': ollama_msg,
            'complaint_count': complaint_count,
            'active_sessions': len(active_sessions),
            'bot_type': 'Your Original RobberyComplaintBot',
            'bot_simple_mode': bot.use_simple_responses
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc(),
            'database_connected': False,
            'ollama_connected': False,
            'complaint_count': 0,
            'active_sessions': len(active_sessions)
        })

@app.route('/api/chat/start', methods=['POST'])
def start_chat():
    """Initialize a new chat session"""
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        session = get_or_create_session(session_id)
        
        if not session.conversation_started:
            # Use your bot's actual initial greeting logic
            # Test if Ollama is working for this session
            ollama_test = session.bot.call_ollama("Hello")
            
            if ollama_test in ["OLLAMA_ERROR", "CONNECTION_ERROR"]:
                session.bot.use_simple_responses = True
                initial_message = "Hello! I'll help you file a robbery complaint. What is your full name?"
            else:
                # Use AI-generated greeting like in terminal
                initial_prompt = """You are an official police complaint registration assistant. A citizen has come to file a robbery/theft complaint. This is a legitimate government service.

Greet them professionally and ask for their full name to begin the official complaint process. Explain this is standard police procedure for crime reporting. Keep it brief and official.
"""
                ai_response = session.bot.call_ollama(initial_prompt)
                if ai_response in ["OLLAMA_ERROR", "CONNECTION_ERROR"]:
                    session.bot.use_simple_responses = True
                    initial_message = "Hello! I'll help you file a robbery complaint. What is your full name?"
                else:
                    initial_message = ai_response
            
            session.conversation_started = True
        else:
            initial_message = "Welcome back! Please continue with your complaint."
        
        return jsonify({
            'status': 'success',
            'session_id': session.session_id,
            'message': initial_message,
            'current_step': len(session.bot.collected_fields),
            'total_steps': len(session.bot.required_fields),
            'completed': session.bot.is_complete(),
            'simple_mode': session.bot.use_simple_responses
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f"Failed to start chat: {str(e)}",
            'traceback': traceback.format_exc()
        })

@app.route('/api/chat/message', methods=['POST'])
def process_message():
    """Process a chat message using your bot"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            })
            
        session_id = data.get('session_id')
        user_message = data.get('message', '').strip()
        
        if not session_id or not user_message:
            return jsonify({
                'status': 'error',
                'message': 'Session ID and message are required'
            })
        
        session = get_or_create_session(session_id)
        
        # Process the message through YOUR bot
        bot_response = session.bot.generate_response(user_message)
        
        # Check if complaint is complete
        is_complete = session.bot.is_complete()
        complaint_id = None
        
        if is_complete and not any('saved' in bot_response.lower() for _ in [1]):
            # Save the complaint using your bot's method
            save_result = session.bot.save_complaint()
            bot_response = save_result
            
            # Extract complaint ID from save result
            if "RC" in save_result:
                complaint_id = save_result.split("ID: ")[1] if "ID: " in save_result else None
        
        return jsonify({
            'status': 'success',
            'message': bot_response,
            'current_step': len(session.bot.collected_fields),
            'total_steps': len(session.bot.required_fields),
            'completed': is_complete,
            'complaint_id': complaint_id,
            'collected_data': dict(session.bot.current_complaint) if is_complete else None,
            'simple_mode': session.bot.use_simple_responses
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f"Failed to process message: {str(e)}",
            'traceback': traceback.format_exc()
        })

@app.route('/api/chat/reset', methods=['POST'])
def reset_chat():
    """Reset the current chat session"""
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({
                'status': 'error',
                'message': 'Session ID is required'
            })
        
        if session_id in active_sessions:
            session = active_sessions[session_id]
            session.bot.reset_complaint()  # Use your bot's reset method
            session.conversation_started = False
        
        return jsonify({
            'status': 'success',
            'message': 'Chat session reset successfully'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f"Failed to reset chat: {str(e)}"
        })

@app.route('/api/complaints/count', methods=['GET'])
def get_complaint_count():
    """Get total number of complaints using your bot"""
    try:
        bot = RobberyComplaintBot()
        count = bot.get_complaint_count()
        
        return jsonify({
            'status': 'success',
            'count': count
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f"Failed to get complaint count: {str(e)}",
            'count': 0
        })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'status': 'error',
        'message': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'status': 'error',
        'message': 'Internal server error',
        'traceback': traceback.format_exc()
    }), 500

if __name__ == '__main__':
    print("=" * 60)
    print("ROBBERY COMPLAINT SYSTEM - DEBUG FLASK SERVER")
    print("=" * 60)
    print("Starting Flask server with enhanced debugging...")
    print("Using YOUR original RobberyComplaintBot")
    
    # Test initial connections using your bot
    print("\nTesting system components...")
    
    try:
        bot = RobberyComplaintBot()
        print(f"✅ Your bot initialized successfully")
        print(f"✅ Database initialized with {bot.get_complaint_count()} existing complaints")
        print(f"📋 Bot config: Ollama URL: {bot.ollama_url}, Model: {bot.model}")
    except Exception as e:
        print(f"❌ Error initializing your bot: {e}")
        print("❌ Make sure 'robbery_complaint_bot.py' is in the same directory")
    
    # Test Ollama in detail
    ollama_working, ollama_msg = test_ollama_connection()
    print(f"🤖 Ollama status: {'✅' if ollama_working else '❌'} {ollama_msg}")
    
    if not ollama_working:
        print("\n⚠️  IMPORTANT: Ollama issues detected!")
        print("This will cause OLLAMA_ERROR and simple responses.")
        print("Solutions:")
        print("1. Run 'ollama list' to check installed models")
        print("2. Run 'ollama serve' to start Ollama")
        print("3. Test your bot in terminal first: 'python robbery_complaint_bot.py'")
    
    print(f"\n🌐 Server will be available at: http://localhost:5000")
    print(f"🔍 Debug endpoint: http://localhost:5000/api/debug")
    print(f"📱 API endpoints:")
    print(f"   - POST /api/chat/start - Initialize chat")
    print(f"   - POST /api/chat/message - Send message") 
    print(f"   - GET /api/debug - Get debug information")
    print(f"\nPress Ctrl+C to stop the server")
    print("=" * 60)
    
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)