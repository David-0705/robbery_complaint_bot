#!/usr/bin/env python3
"""
Robbery Complaint Chatbot using Ollama
Collects complaint information through conversational interface and saves to CSV
"""

import csv
import json
import requests
import re
from datetime import datetime
from typing import Dict, List, Optional

class RobberyComplaintBot:
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "llama2"):
        self.ollama_url = ollama_url
        self.model = model
        self.csv_filename = f"robbery_complaints_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.current_complaint = {}
        
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
        self.initialize_csv()
    
    def initialize_csv(self):
        """Create CSV file with headers"""
        headers = [
            'complaint_id', 'timestamp', 'name', 'mobile', 'email', 'age', 'gender',
            'father_name', 'present_address', 'district', 'nearest_police_station_home',
            'incident_location', 'stolen_items', 'robber_description',
            'nearest_police_station_incident', 'incident_description'
        ]
        
        with open(self.csv_filename, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(headers)
        
        print(f"CSV file initialized: {self.csv_filename}")
    
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
                return "I'm having trouble processing your request. Please try again."
                
        except Exception as e:
            return f"Connection error: {str(e)}"
    
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
                # Ask the next question
                prompt = f"""You are a helpful police complaint assistant. The user just provided: "{extracted_info}" for {next_field}.

Now you need to ask them: {self.required_fields[next_next_field]}

Start with a brief acknowledgment like "Thank you" and then ask the next question naturally and professionally. Keep it brief and clear.
"""
                ollama_response = self.call_ollama(prompt)
                return ollama_response
            else:
                # All information collected
                return "Thank you! I have collected all the necessary information for your robbery complaint. Let me save this to our records."
        else:
            # User didn't provide the information we need, ask again or clarify
            prompt = f"""You are a helpful police complaint assistant. The user said: "{user_input}"

You need to ask them: {self.required_fields[next_field]}

The user may not have understood or may need clarification. Ask the question clearly and professionally. Be helpful and patient.
"""
            ollama_response = self.call_ollama(prompt)
            return ollama_response
    
    def save_complaint(self) -> str:
        """Save the complaint to CSV file"""
        complaint_id = f"RC{datetime.now().strftime('%Y%m%d%H%M%S')}"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Prepare row data
        row_data = [
            complaint_id,
            timestamp,
            self.current_complaint.get('name', ''),
            self.current_complaint.get('mobile', ''),
            self.current_complaint.get('email', ''),
            self.current_complaint.get('age', ''),
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
        ]
        
        # Save to CSV
        with open(self.csv_filename, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(row_data)
        
        return f"Your complaint has been saved with ID: {complaint_id}"
    
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
        print("Type 'quit' at any time to exit.\n")
        
        # Initial greeting
        initial_prompt = """You are a helpful police complaint assistant. Greet the user warmly and ask for their name to begin filing a robbery/theft complaint. Keep it professional but friendly."""
        
        response = self.call_ollama(initial_prompt)
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
                    print("Bot: Let's start with your new complaint. What's your name?")
                else:
                    print("Bot: Thank you for using our complaint system. Your complaint has been recorded.")
                    break

def main():
    print("Starting Robbery Complaint Chatbot...")
    print("Make sure Ollama is running on http://localhost:11434")
    print("You can change the model in the code (default: llama2)")
    print()
    
    # You can change the model here (e.g., "mistral", "codellama", "phi", etc.)
    bot = RobberyComplaintBot(model="llama3.2:3b")
    
    try:
        bot.start_conversation()
    except KeyboardInterrupt:
        print("\n\nBot: Session interrupted. Goodbye!")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()