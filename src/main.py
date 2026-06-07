import os
import io
import tempfile
import threading
import time
import string
import random
# pyrefly: ignore [missing-import]
import customtkinter as ctk
# pyrefly: ignore [missing-import]
from tkinterdnd2 import TkinterDnD, DND_FILES
from tkinter import filedialog, messagebox, Toplevel, Label
from PIL import Image, ImageTk

try:
    # pyrefly: ignore [missing-import]
    import pygame
    pygame.mixer.init()
    HAS_PYGAME = True
except Exception as e:
    print("Warning: Pygame not fully initialized.", e)
    HAS_PYGAME = False

from crypto_utils import encrypt_data, decrypt_data
from analysis_utils import extract_lsb_plane, generate_histogram, generate_chi_square_plot, calculate_metrics, generate_error_mask, estimate_rs_payload
from stego_engine import calculate_capacity, encode_image, decode_image

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ToastNotification:
    """A custom non-blocking toast notification sliding from the bottom."""
    def __init__(self, parent, text, color="#2ecc71", duration=3000):
        self.parent = parent
        self.toast = ctk.CTkFrame(self.parent, fg_color=color, corner_radius=8)
        self.label = ctk.CTkLabel(self.toast, text=text, text_color="white", font=ctk.CTkFont(weight="bold"))
        self.label.pack(padx=20, pady=10)
        
        self.toast.place(relx=0.5, rely=1.2, anchor="center")
        self.duration = duration
        self.animate_in()
        
    def animate_in(self, step=0):
        if step <= 20:
            rely = 1.05 - (0.15 * (step/20))
            self.toast.place(relx=0.5, rely=rely, anchor="center")
            self.parent.after(15, lambda: self.animate_in(step+1))
        else:
            self.parent.after(self.duration, self.animate_out)
            
    def animate_out(self, step=0):
        if step <= 20:
            rely = 0.90 + (0.3 * (step/20))
            self.toast.place(relx=0.5, rely=rely, anchor="center")
            self.parent.after(15, lambda: self.animate_out(step+1))
        else:
            self.toast.destroy()

class AudioPlayer(ctk.CTkFrame):
    def __init__(self, parent, audio_path, filename, **kwargs):
        # Determine appropriate frame colors for light/dark mode
        super().__init__(parent, fg_color=("gray85", "gray20"), **kwargs)
        self.audio_path = audio_path
        self.is_playing = False
        self.is_paused = False
        
        self.lbl_name = ctk.CTkLabel(self, text=f"🎵 {filename}", font=ctk.CTkFont(weight="bold"))
        self.lbl_name.pack(pady=(10, 5))
        
        self.progress = ctk.CTkProgressBar(self, width=300)
        self.progress.pack(pady=5)
        self.progress.set(0)
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)
        
        self.btn_play = ctk.CTkButton(btn_frame, text="▶ Play", width=60, command=self.play)
        self.btn_play.pack(side="left", padx=5)
        
        self.btn_pause = ctk.CTkButton(btn_frame, text="⏸ Pause", width=60, command=self.pause, state="disabled")
        self.btn_pause.pack(side="left", padx=5)
        
        self.btn_stop = ctk.CTkButton(btn_frame, text="⏹ Stop", width=60, command=self.stop, state="disabled")
        self.btn_stop.pack(side="left", padx=5)
        
        self.update_thread = None
        self.running = True

    def play(self):
        if not HAS_PYGAME: return
        if not self.is_playing and not self.is_paused:
            try:
                pygame.mixer.music.load(self.audio_path)
                pygame.mixer.music.play()
                try:
                    self.audio_length = pygame.mixer.Sound(self.audio_path).get_length()
                    self.progress.configure(mode="determinate")
                except:
                    # MP3 files often fail length check in pygame
                    self.audio_length = 0
                    self.progress.configure(mode="indeterminate")
                    self.progress.start()
            except Exception as e:
                print("Audio play error:", e)
                return
        elif self.is_paused:
            pygame.mixer.music.unpause()
            
        self.is_playing = True
        self.is_paused = False
        self.btn_play.configure(state="disabled")
        self.btn_pause.configure(state="normal")
        self.btn_stop.configure(state="normal")
        
        if self.update_thread is None or not self.update_thread.is_alive():
            self.update_thread = threading.Thread(target=self._update_progress)
            self.update_thread.start()
            
    def pause(self):
        if not HAS_PYGAME: return
        pygame.mixer.music.pause()
        self.is_playing = False
        self.is_paused = True
        self.btn_play.configure(state="normal", text="▶ Resume")
        self.btn_pause.configure(state="disabled")
        
    def stop(self):
        if not HAS_PYGAME: return
        pygame.mixer.music.stop()
        self.is_playing = False
        self.is_paused = False
        if getattr(self, 'audio_length', 0) > 0:
            self.progress.set(0)
        else:
            self.progress.stop()
            self.progress.set(0)
            
        self.btn_play.configure(state="normal", text="▶ Play")
        self.btn_pause.configure(state="disabled")
        self.btn_stop.configure(state="disabled")
        
    def _update_progress(self):
        while self.running and (self.is_playing or self.is_paused):
            if self.is_playing:
                pos = pygame.mixer.music.get_pos() / 1000.0
                if pos < 0 or not pygame.mixer.music.get_busy():
                    self.after(0, self.stop)
                    break
                if getattr(self, 'audio_length', 0) > 0:
                    ratio = min(pos / self.audio_length, 1.0)
                    self.after(0, lambda r=ratio: self.progress.set(r))
            time.sleep(0.1)
            
    def destroy(self):
        self.running = False
        if self.is_playing or self.is_paused:
            if HAS_PYGAME: pygame.mixer.music.stop()
        super().destroy()

class TkinterDnDCTk(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)

class StegoApp(TkinterDnDCTk):
    def __init__(self):
        super().__init__()
        
        self.title("Image Steganography Pro")
        self.geometry("1100x700")
        self.resizable(True, True)
        
        # Define light/dark colors
        self.fg_main = ("gray95", "gray14")
        self.fg_panel = ("gray85", "gray20")
        self.configure(fg_color=self.fg_main)
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.landing_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.encode_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.decode_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.analyze_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        
        self.setup_landing_screen()
        self.setup_encode_screen()
        self.setup_decode_screen()
        self.setup_analyze_screen()
        
        self.show_frame(self.landing_frame)
        
    def show_frame(self, frame):
        self.landing_frame.grid_forget()
        self.encode_frame.grid_forget()
        self.decode_frame.grid_forget()
        self.analyze_frame.grid_forget()
        frame.grid(row=0, column=0, sticky="nsew")
        if frame == self.landing_frame:
            self.pulse_step = 0
            self.do_pulse()
            
    def do_pulse(self):
        if not self.landing_frame.winfo_ismapped(): return
        if self.pulse_step < 10:
            w = 250 + (self.pulse_step * 2)
            self.encode_btn.configure(width=w)
            self.decode_btn.configure(width=w)
            self.analyze_btn.configure(width=w)
            self.pulse_step += 1
            self.after(20, self.do_pulse)
        elif self.pulse_step < 20:
            w = 270 - ((self.pulse_step - 10) * 2)
            self.encode_btn.configure(width=w)
            self.decode_btn.configure(width=w)
            self.analyze_btn.configure(width=w)
            self.pulse_step += 1
            self.after(20, self.do_pulse)
        else:
            self.encode_btn.configure(width=250)
            self.decode_btn.configure(width=250)
            self.analyze_btn.configure(width=250)
            
    def toggle_theme(self):
        if self.theme_switch.get():
            ctk.set_appearance_mode("Dark")
            self.theme_switch.configure(text="🌙 Dark Mode")
        else:
            ctk.set_appearance_mode("Light")
            self.theme_switch.configure(text="☀️ Light Mode")

    def setup_landing_screen(self):
        settings_frame = ctk.CTkFrame(self.landing_frame, fg_color="transparent")
        settings_frame.pack(fill="x", pady=10, padx=20)
        
        self.theme_switch = ctk.CTkSwitch(settings_frame, text="🌙 Dark Mode", command=self.toggle_theme)
        self.theme_switch.select() # Default Dark
        self.theme_switch.pack(side="right")
        
        title = ctk.CTkLabel(self.landing_frame, text="Steganography Pro", font=ctk.CTkFont(size=42, weight="bold"))
        title.pack(pady=(80, 50))
        
        self.encode_btn = ctk.CTkButton(self.landing_frame, text="Encode Message/File", font=ctk.CTkFont(size=20), 
                                        height=60, width=250, command=lambda: self.show_frame(self.encode_frame))
        self.encode_btn.pack(pady=20)
        
        self.decode_btn = ctk.CTkButton(self.landing_frame, text="Decode Message/File", font=ctk.CTkFont(size=20), 
                                        height=60, width=250, command=lambda: self.show_frame(self.decode_frame))
        self.decode_btn.pack(pady=20)
        
        self.analyze_btn = ctk.CTkButton(self.landing_frame, text="Steganalysis Testbench", font=ctk.CTkFont(size=20), 
                                         height=60, width=250, fg_color="#e67e22", hover_color="#d35400", command=lambda: self.show_frame(self.analyze_frame))
        self.analyze_btn.pack(pady=20)
        
        exit_btn = ctk.CTkButton(self.landing_frame, text="Exit", font=ctk.CTkFont(size=16), 
                                 height=40, width=150, fg_color="#c0392b", hover_color="#e74c3c", 
                                 command=self.destroy)
        exit_btn.pack(pady=(50, 0))

    def on_image_click(self, event, path):
        if not path: return
        top = Toplevel(self)
        top.title("Image Preview")
        top.geometry("800x600")
        img = Image.open(path)
        img.thumbnail((1200, 1000))
        photo = ImageTk.PhotoImage(img)
        lbl = Label(top, image=photo, bg="black")
        lbl.image = photo
        lbl.pack(expand=True, fill="both")

    def display_image_on_label(self, path, label_widget, max_size=(250, 250)):
        try:
            img = Image.open(path)
            img.thumbnail(max_size)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            label_widget.configure(image=ctk_img, text="")
            label_widget._image_ref = ctk_img
            label_widget.bind("<Button-1>", lambda e: self.on_image_click(e, path))
            label_widget.configure(cursor="hand2")
        except Exception as e:
            print("Error loading image:", e)

    def on_drop_encode(self, event):
        filepath = event.data.strip("{}")
        if filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            self.load_encode_image(filepath)
        else:
            ToastNotification(self, "Unsupported Cover Image Format!", color="#e74c3c")

    def load_encode_image(self, filepath):
        self.encode_image_path = filepath
        self.display_image_on_label(filepath, self.cover_img_label)
        self.stego_img_label.configure(image=None, text="Stego Image\n(Appears after encoding)")
        self.stego_img_label.unbind("<Button-1>")
        self.stego_img_label.configure(cursor="arrow")
        
        cap = calculate_capacity(filepath)
        self.encode_capacity = cap
        self.lbl_capacity.configure(text=f"Maximum Capacity: {cap} bytes")
        self.update_capacity_meter()

    def update_capacity_meter(self, event=None):
        if self.encode_capacity == 0:
            self.capacity_progress.set(0)
            return
            
        payload_size = 0
        ptype = self.payload_type.get()
        if ptype == "Text":
            payload_size = len(self.txt_message.get("1.0", "end-1c").encode('utf-8'))
        elif ptype == "Image":
            payload_size = self.hidden_file_size if self.hidden_file_path else 0
        elif ptype == "Audio":
            payload_size = self.hidden_audio_size if self.hidden_audio_path else 0
        elif ptype == "File":
            payload_size = self.hidden_generic_size if self.hidden_generic_path else 0
            
        ratio = payload_size / self.encode_capacity
        if ratio > 1:
            ratio = 1
            self.capacity_progress.configure(progress_color="#e74c3c") # Red
        elif ratio > 0.8:
            self.capacity_progress.configure(progress_color="#f1c40f") # Yellow
        else:
            self.capacity_progress.configure(progress_color="#2ecc71") # Green
            
        self.capacity_progress.set(ratio)

    def setup_encode_screen(self):
        self.encode_image_path = None
        self.encode_capacity = 0
        
        self.hidden_file_path = None
        self.hidden_file_size = 0
        
        self.hidden_audio_path = None
        self.hidden_audio_size = 0
        self.audio_player = None
        
        self.hidden_generic_path = None
        self.hidden_generic_size = 0
        
        top_frame = ctk.CTkFrame(self.encode_frame, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=5)
        
        back_btn = ctk.CTkButton(top_frame, text="← Home", width=60, command=lambda: self.show_frame(self.landing_frame))
        back_btn.pack(side="left", padx=5)
        
        nav_btn = ctk.CTkButton(top_frame, text="Decode ⮂", width=80, fg_color="#8e44ad", hover_color="#9b59b6", command=lambda: self.show_frame(self.decode_frame))
        nav_btn.pack(side="right", padx=5)
        
        title = ctk.CTkLabel(top_frame, text="Encode Payload", font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(side="left", expand=True)
        
        img_container = ctk.CTkFrame(self.encode_frame, fg_color="transparent")
        img_container.pack(pady=5, fill="x", padx=20)
        img_container.grid_columnconfigure(0, weight=1)
        img_container.grid_columnconfigure(1, weight=1)
        
        self.cover_img_label = ctk.CTkLabel(img_container, text="Drag & Drop Cover Image Here", width=250, height=250, fg_color=self.fg_panel, corner_radius=10)
        self.cover_img_label.grid(row=0, column=0, padx=10, pady=5)
        self.cover_img_label.drop_target_register(DND_FILES)
        self.cover_img_label.dnd_bind('<<Drop>>', self.on_drop_encode)
        
        self.stego_img_label = ctk.CTkLabel(img_container, text="Stego Image Output", width=250, height=250, fg_color=self.fg_panel, corner_radius=10)
        self.stego_img_label.grid(row=0, column=1, padx=10, pady=5)
        
        btn_sel_img = ctk.CTkButton(self.encode_frame, text="Select Cover Image", command=lambda: self.load_encode_image(filedialog.askopenfilename(parent=self, filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp")])))
        btn_sel_img.pack(pady=2)
        
        self.lbl_capacity = ctk.CTkLabel(self.encode_frame, text="Maximum Capacity: 0 bytes", text_color="gray")
        self.lbl_capacity.pack()
        self.capacity_progress = ctk.CTkProgressBar(self.encode_frame, width=500)
        self.capacity_progress.pack(pady=5)
        self.capacity_progress.set(0)
        
        # Payload Type Selection
        self.payload_type = ctk.StringVar(value="Text")
        seg_button = ctk.CTkSegmentedButton(self.encode_frame, values=["Text", "Image", "Audio", "File"], variable=self.payload_type, command=self.toggle_payload_ui)
        seg_button.pack(pady=5)
        
        self.input_container = ctk.CTkFrame(self.encode_frame, fg_color="transparent")
        self.input_container.pack(fill="x", pady=5)
        
        # Text UI
        self.txt_message = ctk.CTkTextbox(self.input_container, height=80, width=500)
        self.txt_message.bind("<KeyRelease>", self.update_capacity_meter)
        
        # Image UI
        self.btn_sel_payload_img = ctk.CTkButton(self.input_container, text="Select Image to Hide", command=self.select_hidden_image)
        self.lbl_sel_payload_img = ctk.CTkLabel(self.input_container, text="")
        self.preview_payload_img = ctk.CTkLabel(self.input_container, text="", width=150, height=150, fg_color=self.fg_panel)
        
        # Audio UI
        self.btn_sel_audio = ctk.CTkButton(self.input_container, text="Select Audio to Hide", command=self.select_hidden_audio)
        self.lbl_sel_audio = ctk.CTkLabel(self.input_container, text="")
        
        # File UI
        self.btn_sel_file = ctk.CTkButton(self.input_container, text="Select File to Hide", command=self.select_hidden_file)
        self.lbl_sel_file = ctk.CTkLabel(self.input_container, text="")
        
        self.toggle_payload_ui("Text") # default
        
        # Security Options
        sec_frame = ctk.CTkFrame(self.encode_frame, fg_color="transparent")
        sec_frame.pack(pady=5, padx=20, fill="x")
        
        opts_frame = ctk.CTkFrame(sec_frame, fg_color="transparent")
        opts_frame.pack(anchor="center", pady=5)

        ctk.CTkLabel(opts_frame, text="Encoding Scheme:", font=ctk.CTkFont(weight="bold")).pack(anchor="center", pady=(0, 2))
        self.encode_scheme = ctk.StringVar(value="Sequential LSB")
        self.seg_scheme = ctk.CTkSegmentedButton(opts_frame, values=["Sequential LSB", "Randomized Scattering"], variable=self.encode_scheme, command=self.toggle_password_state)
        self.seg_scheme.pack(anchor="center", pady=(0, 10))

        self.use_encryption = ctk.BooleanVar(value=False)
        chk_enc = ctk.CTkCheckBox(opts_frame, text="Enable AES Encryption", variable=self.use_encryption, command=self.toggle_password_state)
        chk_enc.pack(anchor="center", pady=2)
        
        self.ent_enc_pass = ctk.CTkEntry(opts_frame, placeholder_text="Enter Password", show="*", width=200)
        
        self.prog_encode = ctk.CTkProgressBar(self.encode_frame, width=300)
        self.prog_encode.set(0)
        
        self.btn_encode = ctk.CTkButton(self.encode_frame, text="Encode & Save", height=40, font=ctk.CTkFont(weight="bold"), command=self.perform_encode)
        self.btn_encode.pack(pady=10)

    def toggle_password_state(self, _=None):
        if self.use_encryption.get() or self.encode_scheme.get() == "Randomized Scattering":
            self.ent_enc_pass.pack(anchor="center", pady=(10, 0))
        else:
            self.ent_enc_pass.pack_forget()

    def toggle_payload_ui(self, value):
        for widget in self.input_container.winfo_children():
            widget.pack_forget()
            
        if value == "Text":
            self.txt_message.pack(pady=5)
        elif value == "Image":
            self.btn_sel_payload_img.pack(pady=5)
            self.lbl_sel_payload_img.pack()
            self.preview_payload_img.pack(pady=5)
        elif value == "Audio":
            self.btn_sel_audio.pack(pady=5)
            self.lbl_sel_audio.pack()
            if self.audio_player:
                self.audio_player.pack(pady=5)
        elif value == "File":
            self.btn_sel_file.pack(pady=5)
            self.lbl_sel_file.pack()
        self.update_capacity_meter()
            
    def select_hidden_image(self):
        fp = filedialog.askopenfilename(parent=self, title="Select Image to Hide", filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp")])
        if fp:
            self.hidden_file_path = fp
            self.hidden_file_size = os.path.getsize(fp)
            self.lbl_sel_payload_img.configure(text=f"{os.path.basename(fp)} ({self.hidden_file_size} bytes)")
            self.display_image_on_label(fp, self.preview_payload_img, max_size=(150, 150))
            self.update_capacity_meter()
            
    def select_hidden_audio(self):
        fp = filedialog.askopenfilename(parent=self, title="Select Audio to Hide", filetypes=[("Audio Files", "*.mp3;*.wav;*.ogg")])
        if fp:
            self.hidden_audio_path = fp
            self.hidden_audio_size = os.path.getsize(fp)
            self.lbl_sel_audio.configure(text=f"{os.path.basename(fp)} ({self.hidden_audio_size} bytes)")
            if self.audio_player:
                self.audio_player.destroy()
            self.audio_player = AudioPlayer(self.input_container, fp, os.path.basename(fp))
            self.audio_player.pack(pady=5)
            self.update_capacity_meter()

    def select_hidden_file(self):
        fp = filedialog.askopenfilename(parent=self, title="Select File to Hide", filetypes=[("All Files", "*.*")])
        if fp:
            self.hidden_generic_path = fp
            self.hidden_generic_size = os.path.getsize(fp)
            self.lbl_sel_file.configure(text=f"{os.path.basename(fp)} ({self.hidden_generic_size} bytes)")
            self.update_capacity_meter()

    def perform_encode(self):
        if not self.encode_image_path:
            ToastNotification(self, "Please select a cover image first!", color="#e74c3c")
            return
            
        payload_bytes = b""
        header = b"TEXT|"
        
        ptype = self.payload_type.get()
        if ptype == "Text":
            msg = self.txt_message.get("1.0", "end-1c")
            if not msg:
                ToastNotification(self, "Please enter a message!", color="#e74c3c")
                return
            payload_bytes = msg.encode('utf-8')
        elif ptype == "Image":
            if not self.hidden_file_path:
                ToastNotification(self, "Please select an image to hide!", color="#e74c3c")
                return
            with open(self.hidden_file_path, "rb") as f:
                payload_bytes = f.read()
            filename = os.path.basename(self.hidden_file_path)
            header = f"IMAGE:{filename}|".encode('utf-8')
        elif ptype == "Audio":
            if not self.hidden_audio_path:
                ToastNotification(self, "Please select audio to hide!", color="#e74c3c")
                return
            with open(self.hidden_audio_path, "rb") as f:
                payload_bytes = f.read()
            filename = os.path.basename(self.hidden_audio_path)
            header = f"AUDIO:{filename}|".encode('utf-8')
        elif ptype == "File":
            if not self.hidden_generic_path:
                ToastNotification(self, "Please select a file to hide!", color="#e74c3c")
                return
            with open(self.hidden_generic_path, "rb") as f:
                payload_bytes = f.read()
            filename = os.path.basename(self.hidden_generic_path)
            header = f"FILE:{filename}|".encode('utf-8')
            
        if self.use_encryption.get() or self.encode_scheme.get() == "Randomized Scattering":
            pwd = self.ent_enc_pass.get()
            if not pwd:
                ToastNotification(self, "Password required for selected security options!", color="#e74c3c")
                return
            
        if self.use_encryption.get():
            try:
                payload_bytes = encrypt_data(payload_bytes, pwd)
                header = header.replace(b"|", b":ENC|")
            except Exception as e:
                ToastNotification(self, f"Encryption failed: {e}", color="#e74c3c")
                return
                
        final_payload = header + payload_bytes
        if len(final_payload) > self.encode_capacity:
            ToastNotification(self, "Payload exceeds image capacity!", color="#e74c3c")
            return
            
        output_dir = filedialog.askdirectory(parent=self, title="Select Output Folder")
        if not output_dir: return
        
        if os.path.dirname(os.path.abspath(self.encode_image_path)) == os.path.abspath(output_dir):
            output_dir = os.path.join(output_dir, "stego_output")
            os.makedirs(output_dir, exist_ok=True)
            
        name, _ = os.path.splitext(os.path.basename(self.encode_image_path))
        output_path = os.path.join(output_dir, name + "_stego.png")
        
        self.btn_encode.configure(state="disabled", text="Encoding...")
        self.prog_encode.pack(pady=(0, 5))
        
        scatter_pwd = pwd if self.encode_scheme.get() == "Randomized Scattering" else None
        threading.Thread(target=self._run_encode_thread, args=(final_payload, output_path, scatter_pwd)).start()
        
    def _run_encode_thread(self, payload, output_path, scatter_pwd):
        def progress(val):
            self.after(0, lambda: self.prog_encode.set(val))
            
        success, info = encode_image(self.encode_image_path, payload, output_path, password=scatter_pwd, progress_callback=progress)
        self.after(0, lambda: self._encode_done(success, info, output_path))
        
    def _encode_done(self, success, info, output_path):
        self.btn_encode.configure(state="normal", text="Encode & Save")
        self.prog_encode.pack_forget()
        
        if success:
            ToastNotification(self, "Successfully Encoded & Saved!")
            self.display_image_on_label(output_path, self.stego_img_label)
        else:
            ToastNotification(self, f"Error: {info}", color="#e74c3c")

    def on_drop_decode(self, event):
        filepath = event.data.strip("{}")
        if filepath.lower().endswith(('.png', '.bmp')):
            self.decode_image_path = filepath
            self.display_image_on_label(filepath, self.dec_img_label)
            # Clear previews
            for w in self.preview_container.winfo_children(): w.destroy()
        else:
            ToastNotification(self, "Stego images must be PNG or BMP!", color="#e74c3c")

    def setup_decode_screen(self):
        self.decode_image_path = None
        self.decode_audio_player = None
        
        top_frame = ctk.CTkFrame(self.decode_frame, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=10)
        
        back_btn = ctk.CTkButton(top_frame, text="← Home", width=60, command=lambda: self.show_frame(self.landing_frame))
        back_btn.pack(side="left", padx=5)
        
        nav_btn = ctk.CTkButton(top_frame, text="Encode ⮂", width=80, fg_color="#8e44ad", hover_color="#9b59b6", command=lambda: self.show_frame(self.encode_frame))
        nav_btn.pack(side="right", padx=5)
        
        title = ctk.CTkLabel(top_frame, text="Decode Payload", font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(side="left", expand=True)
        
        self.dec_img_label = ctk.CTkLabel(self.decode_frame, text="Drag & Drop Stego Image Here", width=250, height=250, fg_color=self.fg_panel, corner_radius=10)
        self.dec_img_label.pack(pady=10)
        self.dec_img_label.drop_target_register(DND_FILES)
        self.dec_img_label.dnd_bind('<<Drop>>', self.on_drop_decode)
        
        btn_sel_img = ctk.CTkButton(self.decode_frame, text="Or Select Stego Image", command=lambda: self.on_drop_decode(type('Event', (), {'data': filedialog.askopenfilename(parent=self, filetypes=[("PNG Images", "*.png"), ("BMP Images", "*.bmp")])})))
        btn_sel_img.pack(pady=5)
        
        dec_sec_frame = ctk.CTkFrame(self.decode_frame, fg_color="transparent")
        dec_sec_frame.pack(pady=5)
        
        self.dec_use_scattering = ctk.BooleanVar(value=False)
        chk_dec_scatter = ctk.CTkCheckBox(dec_sec_frame, text="Is Data Scattered?", variable=self.dec_use_scattering, command=self.toggle_dec_password_visibility)
        chk_dec_scatter.pack(side="top", anchor="center", pady=5)
        
        self.ent_dec_pass = ctk.CTkEntry(dec_sec_frame, placeholder_text="Password (Optional)", show="*", width=150)
        
        self.prog_decode = ctk.CTkProgressBar(self.decode_frame, width=300)
        self.prog_decode.set(0)
        
        self.btn_decode = ctk.CTkButton(self.decode_frame, text="Extract Data", height=40, font=ctk.CTkFont(weight="bold"), command=self.perform_decode)
        self.btn_decode.pack(pady=10)
        
        # Dynamic Preview Container
        ctk.CTkLabel(self.decode_frame, text="Extracted Payload Preview:").pack()
        self.preview_container = ctk.CTkFrame(self.decode_frame, fg_color="transparent")
        self.preview_container.pack(fill="both", expand=True, padx=20, pady=5)

    def toggle_dec_password_visibility(self):
        if self.dec_use_scattering.get():
            self.ent_dec_pass.pack(side="top", anchor="center", pady=(5, 0))
        else:
            self.ent_dec_pass.pack_forget()
            
    def perform_decode(self):
        if not self.decode_image_path:
            ToastNotification(self, "Please select a stego image first!", color="#e74c3c")
            return
            
        pwd = self.ent_dec_pass.get()
        scatter_pwd = pwd if self.dec_use_scattering.get() else None
        
        if self.dec_use_scattering.get() and not scatter_pwd:
            ToastNotification(self, "Password required for scattered data!", color="#e74c3c")
            return
            
        self.btn_decode.configure(state="disabled", text="Extracting...")
        self.prog_decode.pack(pady=(0, 5))
        
        threading.Thread(target=self._run_decode_thread, args=(scatter_pwd, pwd)).start()
        
    def _run_decode_thread(self, scatter_pwd, general_pwd):
        def progress(val):
            self.after(0, lambda: self.prog_decode.set(val))
            
        extracted_bytes = decode_image(self.decode_image_path, password=scatter_pwd, progress_callback=progress)
        self.after(0, lambda: self._decode_done(extracted_bytes, general_pwd))
        
    def save_payload(self, payload, default_filename):
        out_path = filedialog.asksaveasfilename(parent=self, initialfile=default_filename, title="Save File As")
        if out_path:
            with open(out_path, "wb") as f:
                f.write(payload)
            ToastNotification(self, f"File saved: {os.path.basename(out_path)}")

    def _decode_done(self, extracted_bytes, general_pwd):
        self.btn_decode.configure(state="normal", text="Extract Data")
        self.prog_decode.pack_forget()
        
        for w in self.preview_container.winfo_children(): w.destroy()
        
        if extracted_bytes is None:
            ToastNotification(self, "No hidden data found or invalid format.", color="#e74c3c")
            return
            
        parts = extracted_bytes.split(b"|", 1)
        if len(parts) != 2:
            ToastNotification(self, "Invalid header format.", color="#e74c3c")
            return
            
        header = parts[0].decode('utf-8', errors='ignore')
        payload = parts[1]
        
        is_encrypted = ":ENC" in header
        if is_encrypted:
            if not general_pwd:
                dialog = ctk.CTkInputDialog(text="Data is encrypted.\nEnter password to decrypt:", title="Decryption Required")
                general_pwd = dialog.get_input()
                if not general_pwd:
                    ToastNotification(self, "Decryption cancelled.", color="#f1c40f")
                    return
            payload = decrypt_data(payload, general_pwd)
            if payload is None:
                ToastNotification(self, "Decryption failed! Wrong password.", color="#e74c3c")
                return
                
        if header.startswith("TEXT"):
            txt = ctk.CTkTextbox(self.preview_container, height=120, width=500)
            txt.pack(pady=5)
            txt.insert("1.0", payload.decode('utf-8', errors='ignore'))
            ToastNotification(self, "Text extracted successfully!")
            
        elif header.startswith("IMAGE:"):
            filename = header.split("IMAGE:")[1].replace(":ENC", "")
            try:
                img = Image.open(io.BytesIO(payload))
                img.thumbnail((180, 180))
                
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                lbl = ctk.CTkLabel(self.preview_container, image=ctk_img, text="", fg_color=self.fg_panel, corner_radius=10)
                lbl.image = ctk_img
                lbl.pack(pady=5)
                
                btn_save = ctk.CTkButton(self.preview_container, text=f"Save Image ({filename})", command=lambda: self.save_payload(payload, filename))
                btn_save.pack(pady=5)
                ToastNotification(self, "Image extracted successfully!")
            except Exception as e:
                ToastNotification(self, "Failed to load image preview.", color="#e74c3c")
                
        elif header.startswith("AUDIO:"):
            filename = header.split("AUDIO:")[1].replace(":ENC", "")
            
            # Use a unique timestamp to prevent PermissionError if Pygame is still holding the previous file open
            unique_prefix = str(int(time.time()))
            temp_path = os.path.join(tempfile.gettempdir(), f"stego_ext_{unique_prefix}_{filename}")
            
            with open(temp_path, "wb") as f:
                f.write(payload)
                
            self.decode_audio_player = AudioPlayer(self.preview_container, temp_path, filename)
            self.decode_audio_player.pack(pady=5)
            
            btn_save = ctk.CTkButton(self.preview_container, text=f"Save Audio ({filename})", command=lambda: self.save_payload(payload, filename))
            btn_save.pack(pady=5)
            ToastNotification(self, "Audio extracted successfully!")
        else:
            # Generic FILE: format
            filename = header.replace("FILE:", "").replace(":ENC", "")
            
            ext = os.path.splitext(filename)[1].lower()
            if ext in ['.pdf']: file_type = "PDF Document"
            elif ext in ['.zip', '.rar', '.7z']: file_type = "Archive File"
            elif ext in ['.exe']: file_type = "Executable File"
            elif ext in ['.txt', '.csv', '.json', '.xml', '.md']: file_type = "Text/Data File"
            elif ext in ['.doc', '.docx']: file_type = "Word Document"
            elif ext in ['.xls', '.xlsx']: file_type = "Excel Spreadsheet"
            else: file_type = f"{ext.upper().strip('.')} File" if ext else "Generic File"
            
            size_kb = len(payload) / 1024
            
            info_frame = ctk.CTkFrame(self.preview_container, fg_color=self.fg_panel, corner_radius=10)
            info_frame.pack(pady=10, padx=20, fill="x")
            
            ctk.CTkLabel(info_frame, text=f"📄 {filename}", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(10, 5))
            ctk.CTkLabel(info_frame, text=f"File Type: {file_type}", font=ctk.CTkFont(size=14)).pack()
            ctk.CTkLabel(info_frame, text=f"File Size: {size_kb:.2f} KB", font=ctk.CTkFont(size=14)).pack(pady=(0, 10))

            btn_save = ctk.CTkButton(self.preview_container, text=f"Save File", command=lambda: self.save_payload(payload, filename))
            btn_save.pack(pady=10)
            ToastNotification(self, "File extracted successfully!")

    def setup_analyze_screen(self):
        top_nav_frame = ctk.CTkFrame(self.analyze_frame, fg_color="transparent")
        top_nav_frame.pack(fill="x", padx=20, pady=5)
        back_btn = ctk.CTkButton(top_nav_frame, text="← Home", width=60, command=lambda: self.show_frame(self.landing_frame))
        back_btn.pack(side="left")
        title = ctk.CTkLabel(top_nav_frame, text="Steganalysis Testbench", font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(side="left", padx=20)

        # Top Panel: Controls and Original Thumbnails
        self.top_frame = ctk.CTkFrame(self.analyze_frame)
        self.top_frame.pack(fill="x", padx=20, pady=10)
        
        ctrl_frame = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        ctrl_frame.pack(side="left", fill="both", expand=True)
        
        ctk.CTkLabel(ctrl_frame, text="1. Select Cover Image:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.btn_select = ctk.CTkButton(ctrl_frame, text="Browse or Drop Image", command=self.select_cover)
        self.btn_select.grid(row=0, column=1, padx=10)
        self.lbl_cover_name = ctk.CTkLabel(ctrl_frame, text="No image selected")
        self.lbl_cover_name.grid(row=0, column=2, padx=10)
        
        ctk.CTkLabel(ctrl_frame, text="2. Payload Size (% of capacity):", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.slider = ctk.CTkSlider(ctrl_frame, from_=1, to=100, command=self.update_slider_label)
        self.slider.set(50)
        self.slider.grid(row=1, column=1, padx=10, sticky="ew")
        self.lbl_slider = ctk.CTkLabel(ctrl_frame, text="50%")
        self.lbl_slider.grid(row=1, column=2, padx=10, sticky="w")
        
        ctk.CTkLabel(ctrl_frame, text="3. Embedding Scheme:", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.analyze_encode_scheme = ctk.StringVar(value="Sequential LSB")
        self.analyze_seg_scheme = ctk.CTkSegmentedButton(ctrl_frame, values=["Sequential LSB", "Randomized Scattering"], variable=self.analyze_encode_scheme, command=self.toggle_analyze_password_state)
        self.analyze_seg_scheme.grid(row=2, column=1, padx=10, sticky="ew")
        
        self.ent_analyze_pass = ctk.CTkEntry(ctrl_frame, placeholder_text="Seed Password", show="*")
        
        self.btn_generate = ctk.CTkButton(ctrl_frame, text="Generate Stego Image", command=self.generate_stego, fg_color="#e67e22", hover_color="#d35400")
        self.btn_generate.grid(row=3, column=0, columnspan=3, pady=10)
        
        self.btn_select.drop_target_register(DND_FILES)
        self.btn_select.dnd_bind('<<Drop>>', self.analyze_on_drop)
        
        # Original Image Thumbnails
        thumb_frame = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        thumb_frame.pack(side="right", padx=10, pady=10)
        
        cover_thumb_container = ctk.CTkFrame(thumb_frame, fg_color="transparent")
        cover_thumb_container.pack(side="left", padx=10)
        ctk.CTkLabel(cover_thumb_container, text="Original Cover", font=ctk.CTkFont(size=12, weight="bold")).pack()
        self.lbl_thumb_cover = ctk.CTkLabel(cover_thumb_container, text="Pending", width=120, height=120, fg_color="gray20", corner_radius=8)
        self.lbl_thumb_cover.pack()
        
        stego_thumb_container = ctk.CTkFrame(thumb_frame, fg_color="transparent")
        stego_thumb_container.pack(side="left", padx=10)
        ctk.CTkLabel(stego_thumb_container, text="Original Stego", font=ctk.CTkFont(size=12, weight="bold")).pack()
        self.lbl_thumb_stego = ctk.CTkLabel(stego_thumb_container, text="Pending", width=120, height=120, fg_color="gray20", corner_radius=8)
        self.lbl_thumb_stego.pack()
        
        
        # Middle Panel: Analysis Toggles
        toggle_frame = ctk.CTkFrame(self.analyze_frame, fg_color="transparent")
        toggle_frame.pack(fill="x", padx=20, pady=5)
        
        self.view_mode = ctk.StringVar(value="LSB Plane Analysis")
        seg_btn = ctk.CTkSegmentedButton(toggle_frame, values=["LSB Plane Analysis", "Histogram Analysis", "Chi-Square Test Analysis", "Error Mask Analysis"], variable=self.view_mode, command=self.update_analysis_view)
        seg_btn.pack(pady=10)
        
        # Bottom Panel: Previews
        self.preview_frame = ctk.CTkFrame(self.analyze_frame)
        self.preview_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_frame.grid_columnconfigure(1, weight=1)
        
        self.lbl_left_title = ctk.CTkLabel(self.preview_frame, text="Cover Image Analysis", font=ctk.CTkFont(weight="bold", size=16))
        self.lbl_left_title.grid(row=0, column=0, pady=5)
        
        self.lbl_right_title = ctk.CTkLabel(self.preview_frame, text="Stego Image Analysis", font=ctk.CTkFont(weight="bold", size=16))
        self.lbl_right_title.grid(row=0, column=1, pady=5)
        
        self.lbl_img_left = ctk.CTkLabel(self.preview_frame, text="Load image to analyze")
        self.lbl_img_left.grid(row=1, column=0, padx=10, pady=10)
        
        self.lbl_img_right = ctk.CTkLabel(self.preview_frame, text="Generate stego to analyze")
        self.lbl_img_right.grid(row=1, column=1, padx=10, pady=10)
        
        # Bottom Panel: Quality Metrics Cards
        self.metrics_container = ctk.CTkFrame(self.analyze_frame, fg_color="transparent")
        self.metrics_container.pack(fill="x", padx=20, pady=10)
        self.metrics_container.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        def create_card(parent, row, col, title, initial_val, color):
            frame = ctk.CTkFrame(parent, fg_color="#2c3e50", corner_radius=10, border_width=2, border_color=color)
            frame.grid(row=row, column=col, padx=10, pady=5, sticky="ew")
            lbl_title = ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=12, weight="bold"), text_color="gray70")
            lbl_title.pack(pady=(5, 0))
            lbl_val = ctk.CTkLabel(frame, text=initial_val, font=ctk.CTkFont(size=20, weight="bold"), text_color="white")
            lbl_val.pack(pady=(0, 5))
            return lbl_val

        self.val_mse = create_card(self.metrics_container, 0, 0, "MSE Error", "N/A", "#e74c3c")
        self.val_psnr = create_card(self.metrics_container, 0, 1, "PSNR (Quality)", "N/A", "#3498db")
        self.val_ssim = create_card(self.metrics_container, 0, 2, "SSIM (Structure)", "N/A", "#2ecc71")
        self.val_rs = create_card(self.metrics_container, 0, 3, "RS Steganalysis", "N/A", "#f1c40f")

    def analyze_on_drop(self, event):
        path = event.data.strip("{}")
        self.load_cover(path)
        
    def select_cover(self):
        fp = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp")])
        if fp:
            self.load_cover(fp)
            
    def load_cover(self, path):
        self.cover_path = path
        self.capacity = calculate_capacity(path)
        self.lbl_cover_name.configure(text=f"{os.path.basename(path)} (Max: {self.capacity} bytes)")
        self.stego_path = None
        
        orig_img = Image.open(path)
        self._analyze_display_image(orig_img, self.lbl_thumb_cover, title="Original Cover Image", size=(120, 120))
        
        self.lbl_thumb_stego.configure(image=None, text="Pending")
        self.lbl_thumb_stego.unbind("<Button-1>")
        self.lbl_thumb_stego.configure(cursor="arrow")
        
        self.update_analysis_view()
        
    def update_slider_label(self, val):
        self.lbl_slider.configure(text=f"{int(val)}%")
        
    def generate_stego(self):
        if not self.cover_path:
            return
            
        pct = self.slider.get() / 100.0
        bytes_to_hide = int(self.capacity * pct)
        
        header = b"TEXT|"
        if bytes_to_hide < len(header):
            return
            
        payload_body = os.urandom(bytes_to_hide - len(header))
        payload = header + payload_body
        
        out_path = os.path.join(os.path.dirname(self.cover_path), "analysis_stego.png")
        self.btn_generate.configure(state="disabled", text="Generating...")
        
        scatter_pwd = None
        if getattr(self, "analyze_encode_scheme", None) and self.analyze_encode_scheme.get() == "Randomized Scattering":
            scatter_pwd = self.ent_analyze_pass.get()
            if not scatter_pwd:
                ToastNotification(self, "Password required for Randomized Scattering!", color="#e74c3c")
                self.btn_generate.configure(state="normal", text="Generate Stego Image")
                return
        
        def work():
            success, info = encode_image(self.cover_path, payload, out_path, password=scatter_pwd)
            self.after(0, lambda: self._on_stego_generated(success, out_path))
            
        threading.Thread(target=work).start()
        
    def _on_stego_generated(self, success, out_path):
        self.btn_generate.configure(state="normal", text="Generate Stego Image")
        if success:
            self.stego_path = out_path
            orig_stego = Image.open(out_path)
            self._analyze_display_image(orig_stego, self.lbl_thumb_stego, title="Original Stego Image", size=(120, 120))
            
            # Calculate metrics in background
            self.val_mse.configure(text="...")
            self.val_psnr.configure(text="...")
            self.val_ssim.configure(text="...")
            self.val_rs.configure(text="...")
            
            def calc():
                try:
                    m = calculate_metrics(self.cover_path, out_path)
                    rs_pct = estimate_rs_payload(out_path)
                    
                    self.after(0, lambda: self.val_mse.configure(text=f"{m['MSE']:.2f}"))
                    self.after(0, lambda: self.val_psnr.configure(text=f"{m['PSNR']:.2f} dB"))
                    self.after(0, lambda: self.val_ssim.configure(text=f"{m['SSIM']:.4f}"))
                    
                    if rs_pct > 1.0:
                        self.after(0, lambda: self.val_rs.configure(text=f"Detected: {rs_pct:.1f}%", text_color="#e74c3c"))
                    else:
                        self.after(0, lambda: self.val_rs.configure(text="Clean", text_color="#2ecc71"))
                        
                except Exception as e:
                    print("Metrics Error:", e)
                    self.after(0, lambda: self.val_mse.configure(text="Err"))
            threading.Thread(target=calc).start()
            
            self.update_analysis_view()

    def start_loading_animation(self):
        self.is_analyzing = True
        self.loading_dots = 0
        self._animate_loading()
        
    def _animate_loading(self):
        if not getattr(self, 'is_analyzing', False):
            return
            
        dots = "." * (self.loading_dots % 4)
        text = f"Analyzing{dots}\nPlease wait."
        
        if self.lbl_img_left.cget("image") == "" or self.lbl_img_left.cget("image") is None:
            self.lbl_img_left.configure(text=text)
            
        if self.stego_path and (self.lbl_img_right.cget("image") == "" or self.lbl_img_right.cget("image") is None):
            self.lbl_img_right.configure(text=text)
            
        self.loading_dots += 1
        self.after(400, self._animate_loading)

    def toggle_analyze_password_state(self, _=None):
        if self.analyze_encode_scheme.get() == "Randomized Scattering":
            self.ent_analyze_pass.grid(row=2, column=2, padx=10, sticky="w")
        else:
            self.ent_analyze_pass.grid_forget()

    def update_analysis_view(self, _=None):
        mode = self.view_mode.get()
        
        if not self.cover_path:
            return
            
        # Set loading placeholders
        self.lbl_img_left.configure(image=None, text="Loading analysis...\nPlease wait.")
        if self.stego_path:
            self.lbl_img_right.configure(image=None, text="Loading analysis...\nPlease wait.")
        else:
            self.lbl_img_right.configure(image=None, text="Generate stego to analyze")
            
        self.start_loading_animation()
        self.update_idletasks()
        
        threading.Thread(target=self._run_analysis_thread, args=(mode,), daemon=True).start()
        
    def _run_analysis_thread(self, mode):
        # Update Cover Analysis
        img_left = None
        img_right = None
        
        left_title = ""
        right_title = ""
        
        if mode == "LSB Plane Analysis":
            left_title = "Cover Image (0th Bitplane)"
            img_left = extract_lsb_plane(self.cover_path)
            if self.stego_path:
                right_title = "Stego Image (0th Bitplane)"
                img_right = extract_lsb_plane(self.stego_path)
        elif mode == "Histogram Analysis":
            left_title = "Cover Image (Histogram)"
            img_left = generate_histogram(self.cover_path)
            if self.stego_path:
                right_title = "Stego Image (Histogram)"
                img_right = generate_histogram(self.stego_path)
        elif mode == "Chi-Square Test Analysis":
            left_title = "Cover Image (Chi-Square Attack)"
            img_left = generate_chi_square_plot(self.cover_path)
            if self.stego_path:
                right_title = "Stego Image (Chi-Square Attack)"
                img_right = generate_chi_square_plot(self.stego_path)
        elif mode == "Error Mask Analysis":
            left_title = "Cover Image (Original Base)"
            img_left = Image.open(self.cover_path).convert("RGB")
            if self.stego_path:
                right_title = "Stego Image (Error Mask)"
                img_right = generate_error_mask(self.cover_path, self.stego_path)
                
        self.after(0, lambda: self._update_analysis_ui(img_left, left_title, img_right, right_title))
        
    def _update_analysis_ui(self, img_left, left_title, img_right, right_title):
        self.is_analyzing = False
        self.lbl_left_title.configure(text=left_title)
        self._analyze_display_image(img_left, self.lbl_img_left, title=left_title, size=(450, 450))
        
        if img_right:
            self.lbl_right_title.configure(text=right_title)
            self._analyze_display_image(img_right, self.lbl_img_right, title=right_title, size=(450, 450))

    def analyze_on_image_click(self, event, pil_img, title):
        if not pil_img: return
        top = Toplevel(self)
        top.title(title)
        top.geometry("800x600")
        
        display_img = pil_img.copy()
        display_img.thumbnail((1200, 1000))
        photo = ImageTk.PhotoImage(display_img)
        lbl = Label(top, image=photo, bg="black")
        lbl.image = photo
        lbl.pack(expand=True, fill="both")

    def _analyze_display_image(self, pil_img, label, title="Analysis Preview", size=(450, 450)):
        display_img = pil_img.copy()
        display_img.thumbnail(size)
        ctk_img = ctk.CTkImage(light_image=display_img, dark_image=display_img, size=display_img.size)
        label.configure(image=ctk_img, text="")
        label._image_ref = ctk_img
        
        # Unbind first to prevent CustomTkinter from stacking multiple click events
        label.unbind("<Button-1>")
        # Use default args (p=pil_img, t=title) to force early binding, preventing lambda from capturing wrong image
        label.bind("<Button-1>", lambda e, p=pil_img, t=title: self.analyze_on_image_click(e, p, t))
        
        label.configure(cursor="hand2")


if __name__ == "__main__":
    app = StegoApp()
    app.mainloop()
