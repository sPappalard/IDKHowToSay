import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import random
import re
import os
import tempfile
from threading import Thread
from gtts import gTTS
from playsound import playsound
import requests

class EnglishLearningApp:
    def __init__(self, root):
        self.root = root
        self.root.title("English Learning Game")
        self.root.geometry("800x600")
        self.root.configure(bg="#2c3e50")
        
        # Variabili di gioco
        self.vocabulary = []
        self.current_word = None
        self.current_mode = None
        self.score = 0
        self.questions_asked = 0
        self.max_questions = 50
        self.passes_left = 3
        self.max_passes = 3
        
        self.setup_ui()
        
    def setup_ui(self):
        # Header
        header_frame = tk.Frame(self.root, bg="#34495e", height=80)
        header_frame.pack(fill="x", padx=10, pady=5)
        
        title_label = tk.Label(header_frame, text="🎓 English Learning Game", 
                              font=("Arial", 24, "bold"), fg="white", bg="#34495e")
        title_label.pack(pady=15)
        
        # Menu Frame
        self.menu_frame = tk.Frame(self.root, bg="#2c3e50")
        self.menu_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Load Options Frame
        load_frame = tk.Frame(self.menu_frame, bg="#2c3e50")
        load_frame.pack(pady=10)
        
        # Load Excel Button
        load_excel_btn = tk.Button(load_frame, text="📁 Carica File Excel", 
                                 font=("Arial", 12, "bold"), bg="#3498db", fg="white",
                                 command=self.load_excel, pady=8, padx=15)
        load_excel_btn.pack(side="left", padx=5)
        
        # Load Google Sheets Button
        load_sheets_btn = tk.Button(load_frame, text="🌐 Carica Google Sheets", 
                                  font=("Arial", 12, "bold"), bg="#27ae60", fg="white",
                                  command=self.load_google_sheet, pady=8, padx=15)
        load_sheets_btn.pack(side="left", padx=5)
        
        # Google Sheets URL Frame
        self.url_frame = tk.Frame(self.menu_frame, bg="#2c3e50")
        self.url_frame.pack(pady=10, fill="x", padx=20)
        
        tk.Label(self.url_frame, text="🔗 Link Google Sheets:", 
                font=("Arial", 11), fg="white", bg="#2c3e50").pack(anchor="w")
        
        self.url_entry = tk.Entry(self.url_frame, font=("Arial", 10), width=80)
        self.url_entry.pack(fill="x", pady=5)
        self.url_entry.bind("<Return>", lambda e: self.load_google_sheet())
        
        # Instructions
        instructions = tk.Label(self.menu_frame, 
                               text="💡 Per Google Sheets: condividi il foglio pubblicamente e incolla qui il link",
                               font=("Arial", 9), fg="#95a5a6", bg="#2c3e50")
        instructions.pack(pady=5)
        
        # Status Label
        self.status_label = tk.Label(self.menu_frame, text="Nessun dato caricato", 
                                   font=("Arial", 12), fg="#ecf0f1", bg="#2c3e50")
        self.status_label.pack(pady=10)
        
        # Settings Frame
        settings_frame = tk.LabelFrame(self.menu_frame, text="⚙️ Impostazioni", 
                                     font=("Arial", 12, "bold"), fg="white", bg="#2c3e50")
        settings_frame.pack(pady=20, padx=20, fill="x")
        
        # Max Questions Setting
        tk.Label(settings_frame, text="Numero massimo domande:", 
                fg="white", bg="#2c3e50").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        self.max_questions_var = tk.StringVar(value="50")
        questions_spinbox = tk.Spinbox(settings_frame, from_=10, to=500, 
                                     textvariable=self.max_questions_var, width=10)
        questions_spinbox.grid(row=0, column=1, padx=10, pady=5)
        
        # Max Passes Setting
        tk.Label(settings_frame, text="Numero massimo passi:", 
                fg="white", bg="#2c3e50").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        
        self.max_passes_var = tk.StringVar(value="3")
        passes_spinbox = tk.Spinbox(settings_frame, from_=0, to=20, 
                                  textvariable=self.max_passes_var, width=10)
        passes_spinbox.grid(row=1, column=1, padx=10, pady=5)
        
        # Game Mode Buttons
        modes_frame = tk.Frame(self.menu_frame, bg="#2c3e50")
        modes_frame.pack(pady=30)
        
        eng_ita_btn = tk.Button(modes_frame, text="🇬🇧➡️🇮🇹 ENG → ITA", 
                              font=("Arial", 14, "bold"), bg="#e74c3c", fg="white",
                              command=lambda: self.start_game("eng_ita"), 
                              pady=15, padx=25, state="disabled")
        eng_ita_btn.pack(side="left", padx=20)
        
        ita_eng_btn = tk.Button(modes_frame, text="🇮🇹➡️🇬🇧 ITA → ENG", 
                              font=("Arial", 14, "bold"), bg="#27ae60", fg="white",
                              command=lambda: self.start_game("ita_eng"), 
                              pady=15, padx=25, state="disabled")
        ita_eng_btn.pack(side="left", padx=20)
        
        self.mode_buttons = [eng_ita_btn, ita_eng_btn]
        
        # Game Frame (inizialmente nascosto)
        self.setup_game_frame()
        
    def setup_game_frame(self):
        self.game_frame = tk.Frame(self.root, bg="#2c3e50")
        
        # Score and Info Frame
        info_frame = tk.Frame(self.game_frame, bg="#34495e")
        info_frame.pack(fill="x", padx=10, pady=5)
        
        self.score_label = tk.Label(info_frame, text="Punteggio: 0", 
                                  font=("Arial", 14, "bold"), fg="white", bg="#34495e")
        self.score_label.pack(side="left", padx=10)
        
        self.progress_label = tk.Label(info_frame, text="Domanda: 0/50", 
                                     font=("Arial", 14), fg="white", bg="#34495e")
        self.progress_label.pack(side="right", padx=10)
        
        self.passes_label = tk.Label(info_frame, text="Passi rimasti: 3", 
                                   font=("Arial", 14), fg="#f39c12", bg="#34495e")
        self.passes_label.pack(side="right", padx=20)
        
        # Question Frame
        question_frame = tk.Frame(self.game_frame, bg="#2c3e50")
        question_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.question_label = tk.Label(question_frame, text="", 
                                     font=("Arial", 20, "bold"), fg="white", bg="#2c3e50",
                                     wraplength=600)
        self.question_label.pack(pady=30)
        
        # Audio Button
        self.audio_btn = tk.Button(question_frame, text="🔊", font=("Arial", 16), 
                                 bg="#9b59b6", fg="white", command=self.play_audio,
                                 width=3, height=1)
        self.audio_btn.pack(pady=10)
        
        # Answer Frame
        answer_frame = tk.Frame(question_frame, bg="#2c3e50")
        answer_frame.pack(pady=20)
        
        tk.Label(answer_frame, text="La tua risposta:", 
                font=("Arial", 14), fg="white", bg="#2c3e50").pack()
        
        self.answer_entry = tk.Entry(answer_frame, font=("Arial", 16), width=30)
        self.answer_entry.pack(pady=10)
        self.answer_entry.bind("<Return>", lambda e: self.check_answer())
        
        # Result Label
        self.result_label = tk.Label(question_frame, text="", 
                                   font=("Arial", 14, "bold"), bg="#2c3e50")
        self.result_label.pack(pady=10)
        
        # Buttons Frame
        buttons_frame = tk.Frame(question_frame, bg="#2c3e50")
        buttons_frame.pack(pady=20)
        
        tk.Button(buttons_frame, text="✓ Conferma", font=("Arial", 12, "bold"),
                bg="#27ae60", fg="white", command=self.check_answer,
                pady=5, padx=15).pack(side="left", padx=10)
        
        tk.Button(buttons_frame, text="⏭️ Passa", font=("Arial", 12, "bold"),
                bg="#f39c12", fg="white", command=self.pass_question,
                pady=5, padx=15).pack(side="left", padx=10)
        
        tk.Button(buttons_frame, text="🏁 Termina", font=("Arial", 12, "bold"),
                bg="#e74c3c", fg="white", command=self.end_game,
                pady=5, padx=15).pack(side="left", padx=10)
        
        tk.Button(buttons_frame, text="🏠 Menu", font=("Arial", 12, "bold"),
                bg="#7f8c8d", fg="white", command=self.return_to_menu,
                pady=5, padx=15).pack(side="left", padx=10)
    
    def parse_variants(self, text):
        """Estrae tutte le varianti possibili da un testo con separatori multipli."""
        if not text or not isinstance(text, str):
            return []
        
        # Prima pulisce il testo
        text = text.strip()
        
        # Pattern per catturare diversi tipi di separatori
        # / , \ ( ) con possibili spazi intorno
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
    
    def load_google_sheet(self):
        """Carica dati da Google Sheets tramite URL."""
        url = self.url_entry.get().strip()
        
        if not url:
            messagebox.showwarning("Attenzione", "Inserisci l'URL del Google Sheets!")
            return
        
        try:
            # Aggiorna lo status
            self.status_label.config(text="🔄 Caricamento in corso...", fg="#f39c12")
            self.root.update()
            
            # Converte l'URL in formato CSV export
            csv_url = self.convert_google_sheets_url(url)
            
            # Scarica i dati
            response = requests.get(csv_url, timeout=10)
            response.raise_for_status()
            
            # Legge il CSV con pandas
            from io import StringIO
            df = pd.read_csv(StringIO(response.text))
            
            if len(df.columns) < 2:
                messagebox.showerror("Errore", "Il foglio deve avere almeno 2 colonne!")
                self.status_label.config(text="❌ Errore nel caricamento", fg="#e74c3c")
                return
            
            # Processa i dati
            self.process_vocabulary_data(df)
            
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Errore di Connessione", 
                               f"Impossibile scaricare i dati:\n{str(e)}\n\n"
                               "Assicurati che:\n"
                               "• Il link sia corretto\n"
                               "• Il foglio sia condiviso pubblicamente\n"
                               "• Hai una connessione internet attiva")
            self.status_label.config(text="❌ Errore di connessione", fg="#e74c3c")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore nel caricamento: {str(e)}")
            self.status_label.config(text="❌ Errore nel caricamento", fg="#e74c3c")
    
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
            self.status_label.config(
                text=f"✅ Trovati {count} elementi e salvati correttamente!",
                fg="#2ecc71"
            )
            
            # Abilita i pulsanti del gioco
            for btn in self.mode_buttons:
                btn.config(state="normal")
                
            messagebox.showinfo("Successo", f"Caricati {count} vocaboli/verbi!")
        else:
            self.status_label.config(text="❌ Nessun dato valido trovato", fg="#e74c3c")
            messagebox.showwarning("Attenzione", "Non sono stati trovati dati validi nel foglio!")
    
    def load_excel(self):
        """Carica dati da file Excel locale."""
        file_path = filedialog.askopenfilename(
            title="Seleziona il file Excel",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("CSV files", "*.csv")]
        )
        
        if file_path:
            try:
                # Aggiorna lo status
                self.status_label.config(text="🔄 Caricamento in corso...", fg="#f39c12")
                self.root.update()
                
                # Legge il file
                if file_path.endswith('.csv'):
                    df = pd.read_csv(file_path)
                else:
                    df = pd.read_excel(file_path)
                
                if len(df.columns) < 2:
                    messagebox.showerror("Errore", "Il file deve avere almeno 2 colonne!")
                    self.status_label.config(text="❌ Errore nel caricamento", fg="#e74c3c")
                    return
                
                # Processa i dati
                self.process_vocabulary_data(df)
                
            except Exception as e:
                messagebox.showerror("Errore", f"Errore nel caricamento: {str(e)}")
                self.status_label.config(text="❌ Errore nel caricamento", fg="#e74c3c")
    
    def start_game(self, mode):
        if not self.vocabulary:
            messagebox.showwarning("Attenzione", "Carica prima un file Excel!")
            return
        
        self.current_mode = mode
        self.score = 0
        self.questions_asked = 0
        self.max_questions = int(self.max_questions_var.get())
        self.max_passes = int(self.max_passes_var.get())
        self.passes_left = self.max_passes
        
        # Nascondi menu e mostra gioco
        self.menu_frame.pack_forget()
        self.game_frame.pack(fill="both", expand=True)
        
        self.next_question()
        
    def next_question(self):
        if self.questions_asked >= self.max_questions:
            self.end_game()
            return
            
        self.current_word = random.choice(self.vocabulary)
        self.questions_asked += 1
        
        if self.current_mode == "eng_ita":
            question_text = f"Traduci in italiano:\n\n'{self.current_word['english_display']}'"
        else:
            question_text = f"Traduci in inglese:\n\n'{self.current_word['italian_display']}'"
            
        self.question_label.config(text=question_text)
        self.answer_entry.delete(0, tk.END)
        self.result_label.config(text="")
        self.answer_entry.focus()
        
        # Aggiorna le info
        self.score_label.config(text=f"Punteggio: {self.score}")
        self.progress_label.config(text=f"Domanda: {self.questions_asked}/{self.max_questions}")
        self.passes_label.config(text=f"Passi rimasti: {self.passes_left}")
        
    def check_answer(self):
        user_answer = self.answer_entry.get().strip().lower()
        
        if self.current_mode == "eng_ita":
            correct_variants = [var.lower() for var in self.current_word['italian_variants']]
            display_answer = self.current_word['italian_display']
        else:
            correct_variants = [var.lower() for var in self.current_word['english_variants']]
            display_answer = self.current_word['english_display']
        
        if user_answer in correct_variants:
            self.score += 1
            self.result_label.config(text="✅ CORRETTO!", fg="#2ecc71")
        else:
            self.score -= 1
            self.result_label.config(
                text=f"❌ SBAGLIATO!\nRisposta corretta: {display_answer}", 
                fg="#e74c3c"
            )
        
        self.root.after(2000, self.next_question)
        
    def pass_question(self):
        if self.passes_left > 0:
            self.passes_left -= 1
            self.result_label.config(text="⏭️ Domanda saltata", fg="#f39c12")
            self.root.after(1500, self.next_question)
        else:
            messagebox.showinfo("Info", "Non hai più passi disponibili!")
            
    def play_audio(self):
        if not self.current_word:
            messagebox.showinfo("Info", "Nessuna parola da pronunciare")
            return
        
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
                print(f"Errore audio: {e}")
                # Messaggio di errore nell'UI thread
                self.root.after(0, lambda: messagebox.showinfo("Info", "Audio non disponibile"))
        
        # Esegue in thread separato per non bloccare l'UI
        Thread(target=speak, daemon=True).start()
            
    def end_game(self):
        percentage = (self.score / self.questions_asked * 100) if self.questions_asked > 0 else 0
        
        result_msg = f"""
🏁 GIOCO TERMINATO!

📊 Risultati:
• Domande risposte: {self.questions_asked}
• Punteggio finale: {self.score}
• Percentuale: {percentage:.1f}%

{"🎉 Ottimo lavoro!" if percentage >= 70 else "💪 Continua così!" if percentage >= 50 else "📚 Serve più pratica!"}
        """
        
        messagebox.showinfo("Fine Gioco", result_msg)
        self.return_to_menu()
        
    def return_to_menu(self):
        self.game_frame.pack_forget()
        self.menu_frame.pack(fill="both", expand=True, padx=20, pady=10)

def main():
    root = tk.Tk()
    app = EnglishLearningApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()