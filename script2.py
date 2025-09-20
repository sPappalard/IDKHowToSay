from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import pandas as pd
import random
import re
import tempfile
import os
from gtts import gTTS
from playsound import playsound
import requests
from threading import Thread
import logging


app = Flask(__name__)
CORS(app)  # Abilita CORS per tutte le rotte

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnglishLearningBackend:
    def __init__(self):
        self.vocabulary = []
        self.current_word = None
        self.current_mode = None
        self.score = 0
        self.questions_asked = 0
        self.max_questions = 50
        self.passes_left = 3
        self.max_passes = 3
        self.game_active = False

    def parse_variants(self, text):
        """Estrae tutte le varianti possibili da un testo con separatori multipli."""
        if not text or not isinstance(text, str):
            return []
        
        # Prima pulisce il testo
        text = text.strip()
        
        # Pattern per catturare diversi tipi di separatori
        patterns = [
            r'([^/,\\()]+)/([^/,\\()]+)',  # word1/word2
            r'([^/,\\()]+),\s*([^/,\\()]+)',  # word1, word2
            r'([^/,\\()]+)\\([^/,\\()]+)',  # word1\word2
            r'([^/,\\()]+)\(([^/,\\()]+)\)',  # word1(word2)
        ]
        
        variants = []
        original_text = text
        
        # Applica tutti i pattern fino a che non trova più varianti
        while True:
            found_variant = False
            for pattern in patterns:
                matches = re.findall(pattern, text)
                if matches:
                    for match in matches:
                        # Aggiunge tutte le parti trovate
                        for part in match:
                            clean_part = part.strip()
                            if clean_part and clean_part not in variants:
                                variants.append(clean_part)
                        found_variant = True
                    # Sostituisce le parti trovate per continuare la ricerca
                    text = re.sub(pattern, lambda m: m.group(1), text)
            
            if not found_variant:
                break
        
        # Se non ha trovato varianti, usa il testo originale
        if not variants:
            variants.append(original_text.strip())
        else:
            # Aggiunge anche eventuali parti rimaste
            remaining = text.strip()
            if remaining and remaining not in variants:
                variants.append(remaining)
        
        # Pulisce e filtra le varianti
        clean_variants = []
        for variant in variants:
            # Rimuove caratteri speciali residui
            clean = re.sub(r'[/,\\()]', '', variant).strip()
            if clean and clean not in clean_variants:
                clean_variants.append(clean)
        
        return clean_variants if clean_variants else [original_text.strip()]

    def convert_google_sheets_url(self, url):
        """Converte un URL di Google Sheets in formato CSV export."""
        # Pattern per diversi tipi di URL Google Sheets
        patterns = [
            # URL completo con /edit
            r'https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)/edit.*',
            # URL con /edit#gid=
            r'https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)/edit#gid=(\d+)',
            # URL già in formato export
            r'https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)/export\?format=csv.*',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, url)
            if match:
                sheet_id = match.group(1)
                # Crea URL per export CSV
                return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        
        # Se non corrisponde ai pattern, prova comunque
        return url

    def load_google_sheet(self, url):
        """Carica dati da Google Sheets tramite URL."""
        try:
            # Converte l'URL in formato CSV export
            csv_url = self.convert_google_sheets_url(url)
            
            # Scarica i dati
            response = requests.get(csv_url, timeout=10)
            response.raise_for_status()
            
            # Legge il CSV con pandas
            from io import StringIO
            df = pd.read_csv(StringIO(response.text))
            
            if len(df.columns) < 2:
                return {"success": False, "message": "Il foglio deve avere almeno 2 colonne!"}
            
            # Processa i dati
            return self.process_vocabulary_data(df)
            
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Errore di connessione: {str(e)}"}
        except Exception as e:
            return {"success": False, "message": f"Errore nel caricamento: {str(e)}"}

    def process_vocabulary_data(self, df):
        """Processa i dati del vocabolario da un DataFrame pandas."""
        # Prende le prime due colonne e rimuove righe vuote
        vocabulary_data = df.iloc[:, :2].dropna()
        
        self.vocabulary = []
        for _, row in vocabulary_data.iterrows():
            english_raw = str(row.iloc[0]).strip()
            italian_raw = str(row.iloc[1]).strip()
            
            if english_raw and italian_raw and english_raw.lower() != 'nan' and italian_raw.lower() != 'nan':
                # Estrae le varianti per entrambe le lingue
                english_variants = self.parse_variants(english_raw)
                italian_variants = self.parse_variants(italian_raw)
                
                # Salva le varianti insieme al testo originale per la visualizzazione
                self.vocabulary.append({
                    'english_display': english_raw,
                    'italian_display': italian_raw,
                    'english_variants': english_variants,
                    'italian_variants': italian_variants,
                    'english_main': english_variants[0] if english_variants else english_raw,
                    'italian_main': italian_variants[0] if italian_variants else italian_raw
                })
        
        count = len(self.vocabulary)
        if count > 0:
            return {
                "success": True, 
                "message": f"Trovati {count} elementi e salvati correttamente!",
                "count": count
            }
        else:
            return {"success": False, "message": "Nessun dato valido trovato"}

    def load_excel(self, file_content, filename):
        """Carica dati da file Excel/CSV."""
        try:
            # Legge il file
            if filename.endswith('.csv'):
                df = pd.read_csv(file_content)
            else:
                df = pd.read_excel(file_content)
            
            if len(df.columns) < 2:
                return {"success": False, "message": "Il file deve avere almeno 2 colonne!"}
            
            # Processa i dati
            return self.process_vocabulary_data(df)
            
        except Exception as e:
            return {"success": False, "message": f"Errore nel caricamento: {str(e)}"}

    def start_game(self, mode, max_questions, max_passes):
        if not self.vocabulary:
            return {"success": False, "message": "Nessun vocabolario caricato!"}
        
        self.current_mode = mode
        self.score = 0
        self.questions_asked = 0
        self.max_questions = int(max_questions)
        self.max_passes = int(max_passes)
        self.passes_left = self.max_passes
        self.game_active = True
        
        return self.next_question()

    def next_question(self):
        if not self.game_active or self.questions_asked >= self.max_questions:
            return self.end_game()
            
        self.current_word = random.choice(self.vocabulary)
        self.questions_asked += 1
        
        if self.current_mode == "eng_ita":
            question_text = f"Traduci in italiano:\n\n'{self.current_word['english_display']}'"
            question_type = "eng_ita"
        else:
            question_text = f"Traduci in inglese:\n\n'{self.current_word['italian_display']}'"
            question_type = "ita_eng"
            
        return {
            "success": True,
            "game_active": True,
            "question": question_text,
            "question_type": question_type,
            "score": self.score,
            "questions_asked": self.questions_asked,
            "max_questions": self.max_questions,
            "passes_left": self.passes_left
        }

    def check_answer(self, user_answer):
        if not self.game_active or not self.current_word:
            return {"success": False, "message": "Nessuna domanda attiva"}
        
        user_answer = user_answer.strip().lower()
        
        if self.current_mode == "eng_ita":
            correct_variants = [var.lower() for var in self.current_word['italian_variants']]
            display_answer = self.current_word['italian_display']
        else:
            correct_variants = [var.lower() for var in self.current_word['english_variants']]
            display_answer = self.current_word['english_display']
        
        if user_answer in correct_variants:
            self.score += 1
            result = {
                "correct": True,
                "message": "✅ CORRETTO!",
                "score": self.score
            }
        else:
            self.score -= 1
            result = {
                "correct": False,
                "message": f"❌ SBAGLIATO!\nRisposta corretta: {display_answer}",
                "correct_answer": display_answer,
                "score": self.score
            }
        
        return result

    def pass_question(self):
        if not self.game_active:
            return {"success": False, "message": "Nessuna partita attiva"}
            
        if self.passes_left > 0:
            self.passes_left -= 1
            return {
                "success": True, 
                "message": "⏭️ Domanda saltata",
                "passes_left": self.passes_left
            }
        else:
            return {"success": False, "message": "Non hai più passi disponibili!"}

    def play_audio(self):
        if not self.game_active or not self.current_word:
            return {"success": False, "message": "Nessuna parola da pronunciare"}
        
        def speak():
            try:
                # Pronuncia sempre la parola inglese principale
                word_to_speak = self.current_word['english_main']
                
                # Crea il file audio con gTTS
                tts = gTTS(text=word_to_speak, lang='en')
                
                # Usa un file temporaneo
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                    tmp_filename = tmp_file.name
                    tts.save(tmp_filename)
                
                # Riproduce l'audio
                playsound(tmp_filename)
                
                # Pulisce il file temporaneo
                try:
                    os.unlink(tmp_filename)
                except:
                    pass
                    
            except Exception as e:
                logger.error(f"Errore audio: {e}")
        
        # Esegue in thread separato per non bloccare
        Thread(target=speak, daemon=True).start()
        return {"success": True, "message": "Riproduzione audio avviata"}
            
    def end_game(self):
        if not self.game_active:
            return {"success": False, "message": "Nessuna partita attiva"}
            
        percentage = (self.score / self.questions_asked * 100) if self.questions_asked > 0 else 0
        
        self.game_active = False
        
        return {
            "success": True,
            "game_active": False,
            "final_score": self.score,
            "questions_asked": self.questions_asked,
            "percentage": round(percentage, 1),
            "message": f"GIOCO TERMINATO! Punteggio: {self.score}/{self.questions_asked} ({percentage:.1f}%)"
        }

# Istanza globale del backend
backend = EnglishLearningBackend()

# Route API
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/load_google_sheet', methods=['POST'])
def api_load_google_sheet():
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({"success": False, "message": "URL mancante"})
    
    result = backend.load_google_sheet(url)
    return jsonify(result)

@app.route('/api/load_excel', methods=['POST'])
def api_load_excel():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "Nessun file caricato"})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "Nessun file selezionato"})
    
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
def api_play_audio():
    result = backend.play_audio()
    return jsonify(result)

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
        "questions_asked": backend.questions_asked
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)