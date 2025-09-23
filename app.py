from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import pandas as pd
import random
import re
import tempfile
import os
import requests
from google.cloud import texttospeech
from google.oauth2 import service_account
import json
import base64
from datetime import datetime
from threading import Thread
import logging

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnglishLearningBackend:
    def __init__(self):
        self.vocabulary = []
        self.current_word = None
        self.current_mode = None
        self.first_language = None
        self.second_language = None
        self.audio_enabled = True
        self.score = 0
        self.questions_asked = 0
        self.max_questions = 50
        self.passes_left = 3
        self.max_passes = 3
        self.game_active = False
        self.solution_visible = False
        
        # Google Cloud Text-to-Speech configuration
        self.tts_client = None
        self.init_google_tts()

        # Character usage tracking
        self.usage_file = 'google_tts_usage.json'
        self.max_monthly_chars = 1000000  # Google free tier limit

        # Language mapping for Google TTS voices
        self.google_voices = {
            'english': {'language_code': 'en-US', 'name': 'en-US-Neural2-F'},
            'italian': {'language_code': 'it-IT', 'name': 'it-IT-Neural2-A'},
            'french': {'language_code': 'fr-FR', 'name': 'fr-FR-Neural2-A'},
            'spanish': {'language_code': 'es-ES', 'name': 'es-ES-Neural2-A'},
            'german': {'language_code': 'de-DE', 'name': 'de-DE-Neural2-A'}
        }
        
        # Initialize usage tracking
        self.init_usage_tracking()


    def init_google_tts(self):
        """Initialize Google Cloud Text-to-Speech client"""
        try:
            # Try to get JSON content from environment variable
            credentials_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            
            if credentials_json:
                try:
                    # Try to parse as JSON content first
                    import json
                    
                    credentials_info = json.loads(credentials_json)
                    credentials = service_account.Credentials.from_service_account_info(credentials_info)
                    self.tts_client = texttospeech.TextToSpeechClient(credentials=credentials)
                    logger.info("Google TTS client initialized from JSON content in env var")
                    
                except json.JSONDecodeError:
                    # If JSON parsing fails, treat it as a file path
                    if os.path.exists(credentials_json):
                        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_json
                        self.tts_client = texttospeech.TextToSpeechClient()
                        logger.info("Google TTS client initialized from file path")
                    else:
                        logger.error(f"Invalid JSON and file not found: {credentials_json}")
                        self.tts_client = None
            else:
                logger.warning("GOOGLE_APPLICATION_CREDENTIALS not set")
                self.tts_client = None
                
        except Exception as e:
            logger.error(f"Failed to initialize Google TTS: {e}")
            self.tts_client = None

    def init_usage_tracking(self):
        """Initialize or load usage tracking data"""
        try:
            if os.path.exists(self.usage_file):
                with open(self.usage_file, 'r') as f:
                    self.usage_data = json.load(f)
            else:
                self.usage_data = {
                    'current_month': datetime.now().strftime('%Y-%m'),
                    'characters_used': 0,
                    'requests_made': 0
                }
                self.save_usage_data()
        except Exception as e:
            logger.error(f"Error loading usage data: {e}")
            self.usage_data = {
                'current_month': datetime.now().strftime('%Y-%m'),
                'characters_used': 0,
                'requests_made': 0
            }

    def save_usage_data(self):
        """Save usage tracking data to file"""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(self.usage_data, f)
        except Exception as e:
            logger.error(f"Error saving usage data: {e}")

    def check_monthly_reset(self):
        """Reset counter if it's a new month"""
        current_month = datetime.now().strftime('%Y-%m')
        if self.usage_data['current_month'] != current_month:
            self.usage_data = {
                'current_month': current_month,
                'characters_used': 0,
                'requests_made': 0
            }
            self.save_usage_data()
            logger.info("Monthly usage counter reset")

    def can_use_audio(self, text_length):
        """Check if we can use audio API within limits"""
        self.check_monthly_reset()
        
        remaining_chars = self.max_monthly_chars - self.usage_data['characters_used']
        if remaining_chars < text_length:
            return False, f"Monthly limit exceeded. Used: {self.usage_data['characters_used']}/{self.max_monthly_chars} characters"
        
        return True, f"Characters available: {remaining_chars}/{self.max_monthly_chars}"

    def update_usage(self, characters_used):
        """Update usage counter"""
        self.usage_data['characters_used'] += characters_used
        self.usage_data['requests_made'] += 1
        self.save_usage_data()
        
        logger.info(f"Updated usage: {self.usage_data['characters_used']}/{self.max_monthly_chars} characters used")

    def get_usage_info(self):
        """Get current usage information"""
        self.check_monthly_reset()
        return {
            'characters_used': self.usage_data['characters_used'],
            'characters_limit': self.max_monthly_chars,
            'characters_remaining': self.max_monthly_chars - self.usage_data['characters_used'],
            'requests_made': self.usage_data['requests_made'],
            'current_month': self.usage_data['current_month']
        }

    
    def generate_audio_google_tts(self, text, language):
        """Generate audio using Google Cloud Text-to-Speech API"""
        try:
            if not self.tts_client:
                return None, "Google TTS client not initialized"
                
            # Check if we can make the request
            can_use, message = self.can_use_audio(len(text))
            if not can_use:
                return None, message

            # Get voice configuration for the language
            voice_config = self.google_voices.get(language)
            if not voice_config:
                voice_config = self.google_voices['english']  # Fallback to English

            # Set the text input to be synthesized
            synthesis_input = texttospeech.SynthesisInput(text=text)

            # Build the voice request
            voice = texttospeech.VoiceSelectionParams(
                language_code=voice_config['language_code'],
                name=voice_config['name']
            )

            # Select the type of audio file you want returned
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )

            # Perform the text-to-speech request
            response = self.tts_client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )

            if response.audio_content:
                # Update usage counter
                self.update_usage(len(text))
                
                # Convert audio to base64
                audio_base64 = base64.b64encode(response.audio_content).decode('utf-8')
                return audio_base64, "Audio generated successfully"
            else:
                return None, "No audio content received from Google TTS"
                
        except Exception as e:
            logger.error(f"Google TTS error: {e}")
            return None, f"Audio generation failed: {str(e)}"

    # [Mantieni tutti gli altri metodi della classe originale...]
    def parse_variants(self, text):
        if not text or not isinstance(text, str):
            return []
        
        text = text.strip()
        
        patterns = [
            r'([^/,\\()]+)/([^/,\\()]+)',
            r'([^/,\\()]+),\s*([^/,\\()]+)',
            r'([^/,\\()]+)\\([^/,\\()]+)',
            r'([^/,\\()]+)\(([^/,\\()]+)\)',
        ]
        
        variants = []
        original_text = text
        
        while True:
            found_variant = False
            for pattern in patterns:
                matches = re.findall(pattern, text)
                if matches:
                    for match in matches:
                        for part in match:
                            clean_part = part.strip()
                            if clean_part and clean_part not in variants:
                                variants.append(clean_part)
                        found_variant = True
                    text = re.sub(pattern, lambda m: m.group(1), text)
            
            if not found_variant:
                break
        
        if not variants:
            variants.append(original_text.strip())
        else:
            remaining = text.strip()
            if remaining and remaining not in variants:
                variants.append(remaining)
        
        clean_variants = []
        for variant in variants:
            clean = re.sub(r'[/,\\()]', '', variant).strip()
            if clean and clean not in clean_variants:
                clean_variants.append(clean)
        
        return clean_variants if clean_variants else [original_text.strip()]

    def convert_google_sheets_url(self, url):
        patterns = [
            r'https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)/edit.*',
            r'https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)/edit#gid=(\d+)',
            r'https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)/export\?format=csv.*',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, url)
            if match:
                sheet_id = match.group(1)
                return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        
        return url

    def load_google_sheet(self, url):
        try:
            csv_url = self.convert_google_sheets_url(url)
            response = requests.get(csv_url, timeout=10)
            response.raise_for_status()
            
            from io import StringIO
            df = pd.read_csv(StringIO(response.text))
            
            if len(df.columns) < 2:
                return {"success": False, "message": "Sheet must have at least 2 columns!"}
            
            return self.process_vocabulary_data(df)
            
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Connection error: {str(e)}"}
        except Exception as e:
            return {"success": False, "message": f"Loading error: {str(e)}"}

    def process_vocabulary_data(self, df):
        vocabulary_data = df.iloc[:, :2].dropna()
        
        self.vocabulary = []
        for _, row in vocabulary_data.iterrows():
            first_raw = str(row.iloc[0]).strip()
            second_raw = str(row.iloc[1]).strip()
            
            if first_raw and second_raw and first_raw.lower() != 'nan' and second_raw.lower() != 'nan':
                first_variants = self.parse_variants(first_raw)
                second_variants = self.parse_variants(second_raw)
                
                self.vocabulary.append({
                    'first_display': first_raw,
                    'second_display': second_raw,
                    'first_variants': first_variants,
                    'second_variants': second_variants,
                    'first_main': first_variants[0] if first_variants else first_raw,
                    'second_main': second_variants[0] if second_variants else second_raw
                })
        
        count = len(self.vocabulary)
        if count > 0:
            return {
                "success": True, 
                "message": f"Found {count} items and saved successfully!",
                "count": count
            }
        else:
            return {"success": False, "message": "No valid data found"}

    def load_excel(self, file_content, filename):
        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(file_content)
            else:
                df = pd.read_excel(file_content)
            
            if len(df.columns) < 2:
                return {"success": False, "message": "File must have at least 2 columns!"}
            
            return self.process_vocabulary_data(df)
            
        except Exception as e:
            return {"success": False, "message": f"Loading error: {str(e)}"}

    def set_languages(self, first_lang, second_lang):
        self.first_language = first_lang.lower()
        self.second_language = second_lang.lower()
        self.audio_enabled = (
            first_lang.lower() != 'other' and 
            second_lang.lower() != 'other' and
            self.tts_client is not None
        )
        
        return {
            "success": True,
            "audio_enabled": self.audio_enabled,
            "message": "Languages set successfully",
            "usage_info": self.get_usage_info() if self.audio_enabled else None
        }

    def start_game(self, mode, max_questions, max_passes):
        if not self.vocabulary:
            return {"success": False, "message": "No vocabulary loaded!"}
        
        self.current_mode = mode
        self.score = 0
        self.questions_asked = 0
        self.max_questions = int(max_questions)
        self.max_passes = int(max_passes)
        self.passes_left = self.max_passes
        self.game_active = True
        self.solution_visible = False
        
        return self.next_question()

    def next_question(self):
        if not self.game_active or self.questions_asked >= self.max_questions:
            return self.end_game()
            
        self.current_word = random.choice(self.vocabulary)
        self.questions_asked += 1
        self.solution_visible = False
        
        if self.current_mode == "first_second":
            question_text = f"Translate to second language:\n\n'{self.current_word['first_display']}'"
            question_type = "first_second"
        else:
            question_text = f"Translate to first language:\n\n'{self.current_word['second_display']}'"
            question_type = "second_first"
            
        return {
            "success": True,
            "game_active": True,
            "question": question_text,
            "question_type": question_type,
            "score": self.score,
            "questions_asked": self.questions_asked,
            "max_questions": self.max_questions,
            "passes_left": self.passes_left,
            "audio_enabled": self.audio_enabled,
            "solution_visible": False,
            "usage_info": self.get_usage_info() if self.audio_enabled else None
        }

    def show_solution(self):
        if not self.game_active or not self.current_word:
            return {"success": False, "message": "No active question"}
        
        self.solution_visible = True
        
        if self.current_mode == "first_second":
            solution = self.current_word['second_display']
        else:
            solution = self.current_word['first_display']
            
        return {
            "success": True,
            "solution": solution,
            "solution_visible": True
        }

    def hide_solution(self):
        self.solution_visible = False
        return {"success": True, "solution_visible": False}

    def check_answer(self, user_answer):
        if not self.game_active or not self.current_word:
            return {"success": False, "message": "No active question"}
        
        user_answer = user_answer.strip().lower()
        
        if self.current_mode == "first_second":
            correct_variants = [var.lower() for var in self.current_word['second_variants']]
            display_answer = self.current_word['second_display']
        else:
            correct_variants = [var.lower() for var in self.current_word['first_variants']]
            display_answer = self.current_word['first_display']
        
        if user_answer in correct_variants:
            self.score += 1
            result = {
                "correct": True,
                "message": "CORRECT!",
                "score": self.score
            }
        else:
            self.score -= 1
            result = {
                "correct": False,
                "message": f"WRONG!\nCorrect answer: {display_answer}",
                "correct_answer": display_answer,
                "score": self.score,
                "solution_visible": True
            }
            self.solution_visible = True
        
        return result

    def pass_question(self):
        if not self.game_active:
            return {"success": False, "message": "No active game"}
            
        if self.passes_left > 0:
            self.passes_left -= 1
            
            # Show solution when passing
            if self.current_mode == "first_second":
                solution = self.current_word['second_display']
            else:
                solution = self.current_word['first_display']
            
            self.solution_visible = True
            
            return {
                "success": True, 
                "message": "Question skipped",
                "passes_left": self.passes_left,
                "solution": solution,
                "solution_visible": True
            }
        else:
            return {"success": False, "message": "No more passes available!"}

    def get_audio(self):
        """Get audio for current question or solution"""
        if not self.game_active or not self.current_word or not self.audio_enabled:
            return {"success": False, "message": "Audio not available"}
        
        try:
            # Determine what word is currently visible and use its correct language
            if self.solution_visible:
                # Solution is visible - speak the solution word in solution's language
                if self.current_mode == "first_second":
                    # We're translating first->second, so solution is second language
                    word_to_speak = self.current_word['second_main']
                    lang_code = self.second_language
                    logger.info(f"Speaking solution: '{word_to_speak}' in {self.second_language}")
                else:
                    # We're translating second->first, so solution is first language
                    word_to_speak = self.current_word['first_main']  
                    lang_code = self.first_language
                    logger.info(f"Speaking solution: '{word_to_speak}' in {self.first_language}")
            else:
                # Question is visible - speak the question word in question's language
                if self.current_mode == "first_second":
                    # We're translating first->second, so question is first language
                    word_to_speak = self.current_word['first_main']
                    lang_code = self.first_language
                    logger.info(f"Speaking question: '{word_to_speak}' in {self.first_language}")
                else:
                    # We're translating second->first, so question is second language
                    word_to_speak = self.current_word['second_main']
                    lang_code = self.second_language
                    logger.info(f"Speaking question: '{word_to_speak}' in {self.second_language}")
            
            # Generate audio using Google TTS
            audio_base64, message = self.generate_audio_google_tts(word_to_speak, lang_code)
            
            if audio_base64:
                return {
                    "success": True,
                    "audio": audio_base64,
                    "message": message,
                    "usage_info": self.get_usage_info()
                }
            else:
                return {"success": False, "message": message}
                
        except Exception as e:
            logger.error(f"Audio generation error: {e}")
            return {"success": False, "message": f"Audio generation failed: {str(e)}"}
            
    def end_game(self):
        if not self.game_active:
            return {"success": False, "message": "No active game"}
            
        percentage = (self.score / self.questions_asked * 100) if self.questions_asked > 0 else 0
        
        self.game_active = False
        
        return {
            "success": True,
            "game_active": False,
            "final_score": self.score,
            "questions_asked": self.questions_asked,
            "percentage": round(percentage, 1),
            "message": f"GAME ENDED! Score: {self.score}/{self.questions_asked} ({percentage:.1f}%)",
            "usage_info": self.get_usage_info() if self.audio_enabled else None
        }

# Global backend instance
backend = EnglishLearningBackend()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/examples/<filename>')
def download_example(filename):
    try:
        return send_from_directory('static/examples', filename, as_attachment=True)
    except:
        return jsonify({"error": "File not found"}), 404

@app.route('/api/set_languages', methods=['POST'])
def api_set_languages():
    data = request.get_json()
    first_lang = data.get('first_language', '')
    second_lang = data.get('second_language', '')
    
    result = backend.set_languages(first_lang, second_lang)
    return jsonify(result)

@app.route('/api/load_google_sheet', methods=['POST'])
def api_load_google_sheet():
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({"success": False, "message": "URL missing"})
    
    result = backend.load_google_sheet(url)
    return jsonify(result)

@app.route('/api/load_excel', methods=['POST'])
def api_load_excel():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file uploaded"})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "No file selected"})
    
    result = backend.load_excel(file, file.filename)
    return jsonify(result)

@app.route('/api/start_game', methods=['POST'])
def api_start_game():
    data = request.get_json()
    mode = data.get('mode')
    max_questions = data.get('max_questions', 50)
    max_passes = data.get('max_passes', 3)
    
    result = backend.start_game(mode, max_questions, max_passes)
    return jsonify(result)

@app.route('/api/next_question', methods=['GET'])
def api_next_question():
    result = backend.next_question()
    return jsonify(result)

@app.route('/api/show_solution', methods=['POST'])
def api_show_solution():
    result = backend.show_solution()
    return jsonify(result)

@app.route('/api/hide_solution', methods=['POST'])
def api_hide_solution():
    result = backend.hide_solution()
    return jsonify(result)

@app.route('/api/check_answer', methods=['POST'])
def api_check_answer():
    data = request.get_json()
    user_answer = data.get('answer', '')
    
    result = backend.check_answer(user_answer)
    return jsonify(result)

@app.route('/api/pass_question', methods=['POST'])
def api_pass_question():
    result = backend.pass_question()
    return jsonify(result)

@app.route('/api/play_audio', methods=['POST'])
def api_get_audio():
    result = backend.get_audio()
    return jsonify(result)

@app.route('/api/usage_info', methods=['GET'])
def api_usage_info():
    return jsonify(backend.get_usage_info())

@app.route('/api/end_game', methods=['POST'])
def api_end_game():
    result = backend.end_game()
    return jsonify(result)

@app.route('/api/status', methods=['GET'])
def api_status():
    return jsonify({
        "game_active": backend.game_active,
        "vocabulary_count": len(backend.vocabulary),
        "score": backend.score,
        "questions_asked": backend.questions_asked,
        "audio_enabled": backend.audio_enabled,
        "usage_info": backend.get_usage_info() if backend.audio_enabled else None
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)