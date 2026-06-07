# Master Stego Suite

A powerful, high-performance Image Steganography and Steganalysis application built with Python and CustomTkinter. 

This suite allows you to hide secret messages and full files (like MP3s, JPEGs, PDFs) seamlessly inside image files using Least Significant Bit (LSB) embedding. It also features a fully-fledged mathematical Steganalysis Testbench to crack LSB images, and a highly advanced "Randomized Scattering" engine that leverages password-seeded PRNGs and AES encryption to completely defeat mathematical detection.


## ✨ Features

- **File Steganography:** Hide entire binary files (Images, Audio, Zips) directly inside a Cover Image. The decoder perfectly reconstructs the original file.
- **Sequential LSB Engine:** A standard, high-capacity embedding scheme for fast performance.
- **Randomized Scattering Engine:** A mathematically secure embedding scheme that uses a password-seeded PRNG to scatter your payload randomly across the image pixels, fully bypassing Chi-Square attack detection.
- **AES Encryption:** Secure your payload with AES-256 before embedding it into the image.
- **Steganalysis Testbench:** An interactive lab featuring live tools to crack stego images:
  - **Chi-Square Attack Plotting:** Mathematically detect sequential LSB payloads.
  - **PoV Histogram Analysis:** Visually analyze Pairs of Values anomalies.
  - **0th Bitplane Extraction:** Inspect the raw LSB data layer.
  - **Error Mask Generation:** Highlight the exact modified pixels.
- **Drag & Drop UI:** A sleek, resizable, Light/Dark mode enabled graphical interface.

## 🚀 Quick Start (Pre-built Executable)

For Windows users, you don't need to install Python! You can simply download the standalone executable:

1. Go to the [Releases](../../releases) page.
2. Download `MasterStegoSuite.exe`.
3. Double click to run!

## 💻 Developer Setup

If you'd like to run the source code directly or modify the app, follow these steps:

### Prerequisites
- Python 3.10+
- Git

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/image-steganography.git
   cd image-steganography
   ```
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the Master Stego Suite:
   ```bash
   python python/gui_master/main.py
   ```

## 🛠 Building the Executable

You can compile the python code into your own `.exe` using PyInstaller.

1. Ensure `pyinstaller` is installed: `pip install pyinstaller`
2. Run the build script:
   ```bash
   build.bat
   ```
3. Find your compiled `MasterStegoSuite.exe` in the `dist/` directory.

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
