# Solar Module Datasheet Parser

A powerful AI-driven tool that extracts technical specifications from Solar Module datasheets (PDF).
Powered by **AWS Bedrock (Claude 3.5 Sonnet)** and wrapped in a modern web interface.

**[Live Demo](https://solar-datasheet-parser.onrender.com)**


## Features
- **Accurate Extraction**: Parses electrical, mechanical, and warranty data into structured JSON.
- **Smart Summary**: Generates a human-readable summary of key specs.
- **Modern UI**: Drag & Drop interface with real-time progress feedback.
- **Strict Schema**: Enforces consistent JSON output (product, power variants, certifications, etc.).

## Requirements
- Python 3.8+
- AWS Credentials (access to Bedrock `anthropic.claude-3-5-sonnet-20241022-v2:0`)

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Setup Keys**
   - Create a file named `.env` in the project root.
   - Copy the contents from `.env.example` into `.env`.
   - Add your AWS keys:
     ```ini
     AWS_ACCESS_KEY_ID=your_key_here
     AWS_SECRET_ACCESS_KEY=your_secret_here
     AWS_REGION=us-west-2
     ```

3. **Run the App**
   ```bash
   python app.py
   ```
   Open **http://127.0.0.1:5000** in your browser.

## Project Structure
- `app.py`: Flask web application.
- `solar_parser.py`: Core logic for PDF extraction and AI parsing.
- `templates/index.html`: Modern, responsive frontend.
- `requirements.txt`: Python dependencies.
