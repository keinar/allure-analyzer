import os
import json
from flask import Flask, jsonify, render_template, request, send_from_directory
from google import genai
from google.genai import types
from dotenv import load_dotenv
from typing import Dict, Any, List
from datetime import datetime, timedelta

load_dotenv() 

app = Flask(__name__, static_folder='static', template_folder='.')

# Client Initialization
client = None
try:
    client = genai.Client()
    print("✅ Gemini API Client initialized successfully.")
except Exception as e:
    print(f"❌ Error initializing Gemini Client: {e}")

HISTORY_BASE_DIR = 'reports_history'
# This dictionary will store the history of messages for each session
chat_histories: Dict[str, List[types.Content]] = {}

# --- The AI's "Toolbox" (Our Python Functions) ---

def get_list_of_all_reports() -> List[str]:
    """
    Returns a sorted list of all available report timestamps, from newest to oldest.
    """
    print("TOOLBOX: Called get_list_of_all_reports")
    if not os.path.isdir(HISTORY_BASE_DIR):
        return []
    return sorted(
        [d for d in os.listdir(HISTORY_BASE_DIR) if os.path.isdir(os.path.join(HISTORY_BASE_DIR, d))],
        reverse=True
    )

def read_data_from_report(timestamp: str) -> Dict[str, Any]:
    """
    Reads and returns the full JSON data for a single report given its timestamp.
    """
    print(f"TOOLBOX: Called read_data_from_report with timestamp: {timestamp}")
    report_path = os.path.join(HISTORY_BASE_DIR, timestamp, 'failure_analysis_report.json')
    if not os.path.exists(report_path):
        return {"error": f"Report with timestamp '{timestamp}' not found."}
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return json.loads(content) if content else {"error": "File is empty."}
    except Exception as e:
        return {"error": f"Error reading report '{timestamp}': {str(e)}"}

def get_reports_in_date_range(days_ago: int) -> List[str]:
    """
    Returns a list of report timestamps from the last N days.
    """
    print(f"TOOLBOX: Called get_reports_in_date_range for last {days_ago} days")
    start_date = datetime.now() - timedelta(days=days_ago)
    all_reports = get_list_of_all_reports()
    return [
        r for r in all_reports 
        if datetime.strptime(r.split('_')[0], '%Y-%m-%d') >= start_date
    ]

# --- Flask Routes ---

@app.route('/')
def index():
    return render_template('report.html')

@app.route('/reports')
def list_reports():
    return jsonify(get_list_of_all_reports())

@app.route('/reports/<path:timestamp>')
def get_report_data(timestamp):
    if '..' in timestamp or timestamp.startswith('/'):
        return "Invalid path", 400
    file_path = os.path.join(HISTORY_BASE_DIR, timestamp, 'failure_analysis_report.json')
    if os.path.exists(file_path):
        return send_from_directory(os.path.dirname(file_path), os.path.basename(file_path))
    else:
        return "Report not found", 404

# --- Final, Robust, Stateful Chat Logic with Priming ---

@app.route('/chat', methods=['POST'])
def chat():
    if not client:
        return jsonify({"error": "Gemini Client is not configured."}), 500

    data = request.json
    user_question = data.get('question', '')
    session_id = data.get('session_id')
    if not all([user_question, session_id]):
        return jsonify({"error": "Missing user question or session_id"}), 400

    # Retrieve the history for this session, or create and "prime" a new one
    if session_id not in chat_histories:
        print(f"Creating and priming new chat session for ID: {session_id}")
        system_instruction = """
            You are an expert QA analyst agent. Your task is to answer user questions about test failure reports by using the provided tools.

            **Your thinking process MUST be:**
            1.  Analyze the user's question to understand what information is needed.
            2.  If you don't know what reports are available, your first step is ALWAYS to call `get_list_of_all_reports()` to see what files exist.
            3.  Once you have the list of reports, use the `read_data_from_report(timestamp)` tool to get the content of the specific report(s) you need.
            4.  After gathering all necessary data, synthesize it into a final, helpful answer for the user.

            **Example Conversation:**
            * User asks: "What's the difference between the two most recent reports?"
            * Your internal thought process: The user wants to compare the two most recent reports. First, I need to know what reports are available. I must call the `get_list_of_all_reports` tool.
            * (You then proceed to call the `get_list_of_all_reports` tool).
            """
        # We "prime" the chat with the system instructions so the AI knows its role from the start.
        chat_histories[session_id] = [
            types.Content(role='user', parts=[types.Part(text=system_instruction)]),
            types.Content(role='model', parts=[types.Part(text="Understood. I am ready to analyze test failure reports. How can I help?")])
        ]
    
    history = chat_histories[session_id]
    
    # Add the new user question to the history
    history.append(types.Content(role='user', parts=[types.Part(text=user_question)]))

    tools = [get_list_of_all_reports, read_data_from_report, get_reports_in_date_range]
    
    try:
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=history,
            config=types.GenerateContentConfig(tools=tools),
        )
        
        # Add the AI's response to the history for the next turn
        history.append(response.candidates[0].content)

        return jsonify({"response": response.text})

    except Exception as e:
        print(f"An error occurred during content generation: {e}")
        # Try to remove the last user message from history if the call failed
        if history and history[-1].role == 'user':
            history.pop()
        return jsonify({"error": f"An unexpected error occurred on the server: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=True)