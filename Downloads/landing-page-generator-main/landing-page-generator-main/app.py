import os
import uuid
import threading
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from pathlib import Path

# Add project root to sys.path so we can import from scripts
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.generate_page import generate_landing_page, create_sample_brief

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['OUTPUT_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Global dictionary to store job statuses
jobs = {}

def process_generation_job(job_id, brief, output_dir):
    try:
        def progress_cb(current, total, section_key):
            jobs[job_id] = {
                "status": "generating",
                "current": current,
                "total": total,
                "section": section_key
            }
            
        jobs[job_id] = {
            "status": "planning",
            "current": 0,
            "total": 13,
            "section": "AI가 기획 및 카피라이팅 중입니다..."
        }
        
        result_path = generate_landing_page(
            brief=brief,
            output_dir=output_dir,
            skip_generation=False,
            progress_callback=progress_cb
        )
        
        if result_path:
            jobs[job_id] = {
                "status": "completed",
                "current": 13,
                "total": 13,
                "section": "done",
                "result": "final_page.png"
            }
        else:
            jobs[job_id] = {
                "status": "failed",
                "error": "Failed to generate landing page."
            }
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        jobs[job_id] = {
            "status": "failed",
            "error": str(e)
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    if 'reference_image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400
        
    file = request.files['reference_image']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    product_name = request.form.get('product_name', '제품명')
    features = request.form.get('features', '')
    
    # Save the uploaded file
    filename = secure_filename(file.filename)
    job_id = str(uuid.uuid4())
    
    # Create a unique upload path for this job to avoid conflicts
    job_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], job_id)
    os.makedirs(job_upload_dir, exist_ok=True)
    
    file_path = os.path.join(job_upload_dir, filename)
    file.save(file_path)
    
    # Create a unique output directory for this job
    job_output_dir = os.path.join(app.config['OUTPUT_FOLDER'], job_id)
    
    # Setup the brief based on user input
    brief = create_sample_brief()
    brief["product_name"] = product_name
    brief["features"] = features
    brief["reference_image"] = file_path
    
    # Start background thread
    thread = threading.Thread(target=process_generation_job, args=(job_id, brief, f"output/{job_id}"))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "job_id": job_id,
        "status": "starting"
    })

@app.route('/status/<job_id>')
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)

@app.route('/output/<job_id>/<path:filename>')
def serve_output(job_id, filename):
    return send_from_directory(os.path.join(app.config['OUTPUT_FOLDER'], job_id), filename)

@app.route('/output/<job_id>/sections/<path:filename>')
def serve_section_output(job_id, filename):
    return send_from_directory(os.path.join(app.config['OUTPUT_FOLDER'], job_id, 'sections'), filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
