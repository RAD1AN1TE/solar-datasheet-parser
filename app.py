from flask import Flask, render_template, request, jsonify
import os
import tempfile
from solar_parser import process_pdf
import traceback
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max limit
app.config['JSON_SORT_KEYS'] = False  # Preserve JSON key order (Important for Certifications at bottom)
app.json.sort_keys = False # For newer Flask versions

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and file.filename.lower().endswith('.pdf'):
        temp_path = None
        try:
            # Save uploaded file to a temporary file
            fd, temp_path = tempfile.mkstemp(suffix='.pdf')
            os.close(fd)
            file.save(temp_path)
            
            # Live Processing
            json_data, summary = process_pdf(temp_path)
            
            return jsonify({
                'success': True,
                'data': json_data,
                'summary': summary
            })
            
        except Exception as e:
            print(traceback.format_exc())
            return jsonify({'error': str(e)}), 500
        finally:
            # Clean up temporary file
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
    
    return jsonify({'error': 'Invalid file type. Please upload a PDF.'}), 400

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
