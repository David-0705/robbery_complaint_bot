#!/usr/bin/env python3
"""
Robbery Complaint Chatbot using Ollama with MySQL Database
Collects complaint information through conversational interface and saves to MySQL
"""

import mysql.connector
from mysql.connector import Error
import json
import requests
import re
from datetime import datetime
from typing import Dict, List, Optional

class RobberyComplaintBot:
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = None):
        self.ollama_url = ollama_url
        
        # Auto-detect best available model if none specified
        if model is None:
            model = self._get_best_available_model()
        
        self.model = model
        self.current_complaint = {}
        
        # MySQL connection parameters - Updated with your password
        self.db_config = {
            'host': 'localhost',
            'database': 'robbery_complaints_db',
            'user': 'root',
            'password': '123',  # Your MySQL password
            'port': 3306
        }
        
        # Fields to collect
        self.required_fields = {
            # Personal Details
            'name': 'What is your full name?',
            'mobile': 'What is your mobile number?',
            'email': 'What is your email address?',
            'age': 'What is your age?',
            'gender': 'What is your gender?',
            'father_name': 'What is your father\'s name?',
            'present_address': 'What is your present address?',
            'district': 'Which district do you live in?',
            'nearest_police_station_home': 'What is the nearest police station to your house?',
            
            # Incident Details
            'incident_location': 'Where did the robbery/theft happen?',
            'stolen_items': 'What was stolen from you?',
            'robber_description': 'Can you describe how the robbers looked like?',
            'nearest_police_station_incident': 'What is the nearest police station to where the incident occurred?',
            'incident_description': 'Please provide a brief description of the entire incident'
        }
        
        self.collected_fields = set()
        self.use_simple_responses = False  # Fallback when AI is problematic
        self.initialize_database()
    
    def _get_best_available_model(self) -> str:
        """Auto-detect the best available Ollama model"""
        try:
            models_response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if models_response.status_code == 200:
                models = models_response.json()
                available_models = [model['name'] for model in models.get('models', [])]
                
                # Preferred models in order of preference
                preferred_models = ["llama3.2:3b", "llama3.2:1b", "mistral", "llama2", "phi"]
                
                # Find the first available preferred model
                for preferred in preferred_models:
                    for available in available_models:
                        if preferred in available:
                            print(f"[INFO] Auto-selected model: {available}")
                            return available
                
                # If no preferred model found, use first available
                if available_models:
                    print(f"[INFO] Using first available model: {available_models[0]}")
                    return available_models[0]
        
        except Exception as e:
            print(f"[INFO] Could not auto-detect model: {e}")
        
        # Fallback to llama3.2:3b as default (most likely to be available)
        print("[INFO] Using fallback model: llama3.2:3b")
        return "llama3.2:3b"
    
    def create_database_connection(self):
        """Create database connection"""
        try:
            connection = mysql.connector.connect(**self.db_config)
            if connection.is_connected():
                return connection
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
            return None
    
    def initialize_database(self):
        """Create database and table if they don't exist"""
        try:
            # First, connect without specifying database to create it
            temp_config = self.db_config.copy()
            temp_config.pop('database')
            
            connection = mysql.connector.connect(**temp_config)
            cursor = connection.cursor()
            
            # Create database if it doesn't exist
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.db_config['database']}")
            cursor.close()
            connection.close()
            
            # Now connect to the specific database
            connection = self.create_database_connection()
            if connection:
                cursor = connection.cursor()
                
                # Create table if it doesn't exist
                create_table_query = """
                CREATE TABLE IF NOT EXISTS complaints (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    complaint_id VARCHAR(50) UNIQUE NOT NULL,
                    timestamp DATETIME NOT NULL,
                    name VARCHAR(255),
                    mobile VARCHAR(15),
                    email VARCHAR(255),
                    age INT,
                    gender VARCHAR(20),
                    father_name VARCHAR(255),
                    present_address TEXT,
                    district VARCHAR(100),
                    nearest_police_station_home VARCHAR(255),
                    incident_location TEXT,
                    stolen_items TEXT,
                    robber_description TEXT,
                    nearest_police_station_incident VARCHAR(255),
                    incident_description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
                
                cursor.execute(create_table_query)
                connection.commit()
                cursor.close()
                connection.close()
                
                print(f"Database '{self.db_config['database']}' and table 'complaints' initialized successfully!")
                
        except Error as e:
            print(f"Error initializing database: {e}")
    
    def call_ollama(self, prompt: str) -> str:
        """Make API call to Ollama"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()["response"].strip()
            else:
                print(f"[DEBUG] Ollama API error: Status {response.status_code}")
                print(f"[DEBUG] Response: {response.text}")
                return "OLLAMA_ERROR"
                
        except requests.exceptions.ConnectionError:
            print(f"[DEBUG] Cannot connect to Ollama at {self.ollama_url}")
            return "CONNECTION_ERROR"
        except Exception as e:
            print(f"[DEBUG] Ollama error: {str(e)}")
            return "OLLAMA_ERROR"
    
    def generate_simple_response(self, next_field: str, extracted_info: str = None) -> str:
        """Generate simple responses without AI when AI is being problematic"""
        
        responses = {
            'name': "Thank you. What is your mobile number?",
            'mobile': "Got it. What is your email address?", 
            'email': "Thank you. What is your age?",
            'age': "Noted. What is your gender?",
            'gender': "Thank you. What is your father's name?",
            'father_name': "Got it. What is your present address?",
            'present_address': "Thank you. Which district do you live in?",
            'district': "Noted. What is the nearest police station to your house?",
            'nearest_police_station_home': "Thank you. Where did the robbery/theft happen?",
            'incident_location': "Got it. What was stolen from you?",
            'stolen_items': "Thank you. Can you describe how the robbers looked like?",
            'robber_description': "Noted. What is the nearest police station to where the incident occurred?",
            'nearest_police_station_incident': "Thank you. Please provide a brief description of the entire incident.",
            'incident_description': "Thank you for providing all the information."
        }
        
        return responses.get(next_field, f"Please provide your {next_field}.")
    
    def extract_information(self, user_input: str, field: str) -> Optional[str]:
        """Extract specific information from user input"""
        
        # Clean input first
        user_input = user_input.strip()
        
        # Skip very short or meaningless responses
        if len(user_input) < 2 or user_input.lower() in ['ok', 'okok', 'yes', 'no', 'yeah', 'yep']:
            return None
        
        # Simple extraction patterns
        if field == 'mobile':
            mobile_pattern = r'\b\d{10}\b'
            match = re.search(mobile_pattern, user_input)
            if match:
                return match.group()
        
        elif field == 'email':
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            match = re.search(email_pattern, user_input)
            if match:
                return match.group()
        
        elif field == 'age':
            age_pattern = r'\b(\d{1,3})\b'
            numbers = re.findall(age_pattern, user_input)
            for num in numbers:
                if 1 <= int(num) <= 120:  # Reasonable age range
                    return num
        
        elif field == 'name':
            # Look for name patterns - should be at least 2 words or contain letters
            if len(user_input) > 2 and any(c.isalpha() for c in user_input):
                return user_input.title()  # Capitalize properly
        
        elif field in ['gender']:
            # Check for gender keywords
            user_lower = user_input.lower()
            if any(word in user_lower for word in ['male', 'female', 'man', 'woman', 'boy', 'girl', 'm', 'f']):
                return user_input.capitalize()
        
        # For other fields, return the cleaned input if it's substantial
        if len(user_input) > 2:
            return user_input.strip()
        
        return None
    
    def generate_response(self, user_input: str) -> str:
        """Generate contextual response using Ollama"""
        
        # Find the next field we need to collect (in order)
        next_field = None
        field_list = list(self.required_fields.keys())
        
        for field in field_list:
            if field not in self.collected_fields:
                next_field = field
                break
        
        if not next_field:
            # All information collected
            return "Thank you! I have collected all the necessary information for your robbery complaint. Let me save this to our records."
        
        # Try to extract information for the current field we're asking about
        extracted_info = self.extract_information(user_input, next_field)
        
        # Check if the user provided the information we're looking for
        if extracted_info and len(extracted_info.strip()) > 0:
            # Store the information
            self.current_complaint[next_field] = extracted_info
            self.collected_fields.add(next_field)
            
            # Find the next field to ask about
            next_next_field = None
            for field in field_list:
                if field not in self.collected_fields:
                    next_next_field = field
                    break
            
            if next_next_field:
                # Try AI first, fallback to simple response
                if not self.use_simple_responses:
                    prompt = f"""You are an official police complaint registration assistant helping citizens file legitimate robbery/theft reports. This is a legal government process.

The citizen just provided their {next_field}: "{extracted_info}"

You need to collect their {next_next_field} next by asking: {self.required_fields[next_next_field]}

Respond professionally: acknowledge what they provided, then ask the next required question for the official police report. This is standard police procedure for crime reporting.
"""
                    ollama_response = self.call_ollama(prompt)
                    
                    # Check if AI is giving problematic responses or Ollama failed
                    if "cannot" in ollama_response.lower() or "can't" in ollama_response.lower() or ollama_response in ["OLLAMA_ERROR", "CONNECTION_ERROR"]:
                        print("[INFO] Switching to simple responses...")
                        self.use_simple_responses = True
                        return self.generate_simple_response(next_next_field)
                    return ollama_response
                else:
                    return self.generate_simple_response(next_next_field)
            else:
                # All information collected
                return "Thank you! I have collected all the necessary information for your robbery complaint. Let me save this to our records."
        else:
            # User didn't provide the information we need, ask again or clarify
            prompt = f"""You are an official police complaint registration assistant helping citizens file legitimate robbery/theft reports. This is a legal government process.

The citizen said: "{user_input}"

You need to collect their {next_field} by asking: {self.required_fields[next_field]}

This information is required for the official police report. Ask the question clearly and professionally. Explain this is standard procedure for filing a complaint.
"""
            ollama_response = self.call_ollama(prompt)
            return ollama_response
    
    def save_complaint(self) -> str:
        """Save the complaint to MySQL database"""
        try:
            connection = self.create_database_connection()
            if not connection:
                return "Error: Could not connect to database"
            
            cursor = connection.cursor()
            complaint_id = f"RC{datetime.now().strftime('%Y%m%d%H%M%S')}"
            timestamp = datetime.now()
            
            # Prepare insert query
            insert_query = """
            INSERT INTO complaints (
                complaint_id, timestamp, name, mobile, email, age, gender,
                father_name, present_address, district, nearest_police_station_home,
                incident_location, stolen_items, robber_description,
                nearest_police_station_incident, incident_description
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            # Prepare values
            age_value = None
            if self.current_complaint.get('age'):
                try:
                    age_value = int(self.current_complaint.get('age'))
                except ValueError:
                    age_value = None
            
            values = (
                complaint_id,
                timestamp,
                self.current_complaint.get('name', ''),
                self.current_complaint.get('mobile', ''),
                self.current_complaint.get('email', ''),
                age_value,
                self.current_complaint.get('gender', ''),
                self.current_complaint.get('father_name', ''),
                self.current_complaint.get('present_address', ''),
                self.current_complaint.get('district', ''),
                self.current_complaint.get('nearest_police_station_home', ''),
                self.current_complaint.get('incident_location', ''),
                self.current_complaint.get('stolen_items', ''),
                self.current_complaint.get('robber_description', ''),
                self.current_complaint.get('nearest_police_station_incident', ''),
                self.current_complaint.get('incident_description', '')
            )
            
            cursor.execute(insert_query, values)
            connection.commit()
            cursor.close()
            connection.close()
            
            return f"Your complaint has been saved to the database with ID: {complaint_id}"
            
        except Error as e:
            return f"Error saving complaint to database: {e}"
    
    def get_complaint_count(self) -> int:
        """Get total number of complaints in database"""
        try:
            connection = self.create_database_connection()
            if connection:
                cursor = connection.cursor()
                cursor.execute("SELECT COUNT(*) FROM complaints")
                count = cursor.fetchone()[0]
                cursor.close()
                connection.close()
                return count
        except Error as e:
            print(f"Error getting complaint count: {e}")
        return 0
    
    def is_complete(self) -> bool:
        """Check if all required information is collected"""
        return len(self.collected_fields) == len(self.required_fields)
    
    def reset_complaint(self):
        """Reset for new complaint"""
        self.current_complaint = {}
        self.collected_fields = set()
    
    def start_conversation(self):
        """Main conversation loop"""
        print("=" * 60)
        print("ROBBERY/THEFT COMPLAINT REGISTRATION SYSTEM")
        print("=" * 60)
        print("Hello! I'm here to help you file a robbery/theft complaint.")
        print("I'll ask you some questions to gather the necessary information.")
        print(f"Total complaints in database: {self.get_complaint_count()}")
        print("Type 'quit' at any time to exit.\n")
        
        # Test Ollama connection first
        print("Testing Ollama connection...")
        test_response = self.call_ollama("Hello")
        
        if test_response in ["OLLAMA_ERROR", "CONNECTION_ERROR"]:
            print("❌ Ollama is not working. Switching to simple mode (no AI responses).")
            self.use_simple_responses = True
            print("Bot: Hello! I'll help you file a robbery complaint. What is your full name?")
        else:
            print("✅ Ollama is working!")
            # Initial greeting with clear context
            initial_prompt = """You are an official police complaint registration assistant. A citizen has come to file a robbery/theft complaint. This is a legitimate government service.

Greet them professionally and ask for their full name to begin the official complaint process. Explain this is standard police procedure for crime reporting. Keep it brief and official.
"""
            
            response = self.call_ollama(initial_prompt)
            if response in ["OLLAMA_ERROR", "CONNECTION_ERROR"]:
                print("Bot: Hello! I'll help you file a robbery complaint. What is your full name?")
                self.use_simple_responses = True
            else:
                print(f"Bot: {response}")
        
        while True:
            user_input = input("\nYou: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("Bot: Thank you for using our complaint system. Goodbye!")
                break
            
            if not user_input:
                print("Bot: Please provide some information.")
                continue
            
            # Generate response
            bot_response = self.generate_response(user_input)
            print(f"Bot: {bot_response}")
            
            # Check if complaint is complete
            if self.is_complete():
                save_message = self.save_complaint()
                print(f"Bot: {save_message}")
                
                print("\nWould you like to file another complaint? (yes/no)")
                continue_input = input("You: ").strip().lower()
                
                if continue_input in ['yes', 'y']:
                    self.reset_complaint()
                    if self.use_simple_responses:
                        print("Bot: Let's start with your new complaint. What is your full name?")
                    else:
                        print("Bot: Let's start with your new complaint. What's your name?")
                else:
                    print("Bot: Thank you for using our complaint system. Your complaint has been recorded.")
                    break

def test_mysql_connection():
    """Test different password combinations"""
    common_passwords = ['', 'root', 'mysql', 'password', '123456']
    
    for pwd in common_passwords:
        try:
            print(f"Trying password: {'(empty)' if pwd == '' else pwd}")
            config = {
                'host': 'localhost',
                'user': 'root',
                'password': pwd,
                'port': 3306
            }
            connection = mysql.connector.connect(**config)
            if connection.is_connected():
                print(f"✅ SUCCESS! Your root password is: {'(empty)' if pwd == '' else pwd}")
                connection.close()
                return pwd
        except Error as e:
            print(f"❌ Failed with password {'(empty)' if pwd == '' else pwd}")
    
    print("None of the common passwords worked. You may need to reset your MySQL root password.")
    return None

def main():
    print("Starting Robbery Complaint Chatbot with MySQL Database...")
    print("Checking requirements...")
    
    # Check if Ollama is running
    try:
        test_response = requests.get("http://localhost:11434", timeout=5)
        print("✅ Ollama server is running")
    except:
        print("❌ Ollama server is not running or not accessible")
        print("   You can still use the bot in simple mode (without AI responses)")
    
    # Check available models
    try:
        models_response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if models_response.status_code == 200:
            models = models_response.json()
            available_models = [model['name'] for model in models.get('models', [])]
            print(f"✅ Available models: {available_models}")
            
            # Choose the best available model
            preferred_models = ["llama3.2:3b", "llama3.2:1b", "mistral", "llama2", "phi"]
            chosen_model = "llama3.2:3b"  # default to most likely available
            
            for model in preferred_models:
                if any(model in available for available in available_models):
                    chosen_model = model
                    break
            
            print(f"✅ Using model: {chosen_model}")
        else:
            print("⚠️ Could not check available models")
            chosen_model = "llama3.2:3b"
    except:
        print("⚠️ Could not check available models, using default: llama3.2:3b")
        chosen_model = "llama3.2:3b"
    
    print()
    
    # Create bot - model will be auto-detected if not specified
    bot = RobberyComplaintBot()
    
    try:
        bot.start_conversation()
    except KeyboardInterrupt:
        print("\n\nBot: Session interrupted. Goodbye!")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()