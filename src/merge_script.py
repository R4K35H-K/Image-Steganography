import re

main_path = 'f:/Antigravity Project/image-steganography/python/gui_master/main.py'
analysis_path = 'f:/Antigravity Project/image-steganography/python/gui_analysis/main.py'

with open(analysis_path, 'r', encoding='utf-8') as f:
    analysis_code = f.read()

# Extract from def setup_ui(self): to the end of the class
match = re.search(r'    def setup_ui\(self\):(.*?)if __name__ == "__main__":', analysis_code, re.DOTALL)
methods_code = match.group(1)

# Rename setup_ui to setup_analyze_screen
methods_code = methods_code.replace('def setup_ui(self):', 'def setup_analyze_screen(self):')
# Adjust container for the UI
methods_code = methods_code.replace('self.top_frame = ctk.CTkFrame(self)', 'self.top_frame = ctk.CTkFrame(self.analyze_frame)')
methods_code = methods_code.replace('toggle_frame = ctk.CTkFrame(self, fg_color="transparent")', 'toggle_frame = ctk.CTkFrame(self.analyze_frame, fg_color="transparent")')
methods_code = methods_code.replace('self.preview_frame = ctk.CTkFrame(self)', 'self.preview_frame = ctk.CTkFrame(self.analyze_frame)')
methods_code = methods_code.replace('self.metrics_container = ctk.CTkFrame(self, fg_color="transparent")', 'self.metrics_container = ctk.CTkFrame(self.analyze_frame, fg_color="transparent")')

# Add navigation button inside setup_analyze_screen
nav_button = '''
        top_nav_frame = ctk.CTkFrame(self.analyze_frame, fg_color="transparent")
        top_nav_frame.pack(fill="x", padx=20, pady=5)
        back_btn = ctk.CTkButton(top_nav_frame, text="← Home", width=60, command=lambda: self.show_frame(self.landing_frame))
        back_btn.pack(side="left")
        title = ctk.CTkLabel(top_nav_frame, text="Steganalysis Testbench", font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(side="left", padx=20)
'''
methods_code = methods_code.replace('def setup_analyze_screen(self):', 'def setup_analyze_screen(self):' + nav_button)

# Rename conflicting methods
methods_code = methods_code.replace('def on_drop(', 'def analyze_on_drop(')
methods_code = methods_code.replace('self.on_drop', 'self.analyze_on_drop')

methods_code = methods_code.replace('def on_image_click(', 'def analyze_on_image_click(')
methods_code = methods_code.replace('self.on_image_click', 'self.analyze_on_image_click')

methods_code = methods_code.replace('def _display_image(', 'def _analyze_display_image(')
methods_code = methods_code.replace('self._display_image', 'self._analyze_display_image')

with open(main_path, 'r', encoding='utf-8') as f:
    main_code = f.read()

# Insert the methods before if __name__
main_code = main_code.replace('if __name__ == "__main__":', '    def setup_analyze_screen(self):' + nav_button + methods_code + '\nif __name__ == "__main__":')

with open(main_path, 'w', encoding='utf-8') as f:
    f.write(main_code)
print('Phase 2 done')
