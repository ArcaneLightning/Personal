# app.py - CORRECTED

from flask import Flask, render_template # <-- Make sure render_template is imported
from flask_cors import CORS

# Import the blueprint objects from your refactored files
from videos import video_bp, load_cache
from gallery import gallery_bp
from reddit import reddit_bp

# Initialize the main Flask application
app = Flask(__name__)
CORS(app) 

# Register each blueprint with the main app
app.register_blueprint(video_bp)
app.register_blueprint(gallery_bp)
app.register_blueprint(reddit_bp)


# --- ADD THESE ROUTES ---
# This is the fix. These routes tell Flask how to serve your HTML pages.

@app.route('/')
def index():
    """Serves the main video classifier page."""
    return render_template('index.html')

@app.route('/gallery-page')
def gallery_page():
    """Serves the media gallery page."""
    return render_template('gallery.html')

@app.route('/reddit-page')
def reddit_page():
    """Serves the Reddit gallery page."""
    return render_template('reddit_gallery.html')

# --- END OF FIX ---


if __name__ == "__main__":
    # The load_cache() call from your videos server can be run here at startup
    load_cache()
    # Run the app on port 5000
    app.run(debug=True, port=5000)