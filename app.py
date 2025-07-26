# app.py - NEW MAIN FILE

from flask import Flask, render_template
from flask_cors import CORS

# Import the blueprint objects from your refactored files
from videos import video_bp
from gallery import gallery_bp
from reddit import reddit_bp

# Initialize the main Flask application
app = Flask(__name__)
CORS(app) # Apply CORS to the entire application

# Register each blueprint with the main app
# The application will now handle all routes defined in these blueprints
app.register_blueprint(video_bp)
app.register_blueprint(gallery_bp)
app.register_blueprint(reddit_bp)

# This route will now serve your main HTML page
@app.route('/')
def index():
    return render_template('index.html')

# Add routes for your other main pages
@app.route('/gallery-page') # This URL is what the user types in the browser
def gallery_page():
    return render_template('gallery.html') # This is the file in your templates folder

@app.route('/reddit-page')
def reddit_page():
    return render_template('reddit.html')

# This is the only file that needs the __main__ block
# It runs the single app, which now includes all of your functionality
if __name__ == "__main__":
    # The load_cache() call from your original videos server can be run here at startup
    from videos import load_cache
    load_cache()

    # Run the app on port 5000
    app.run(debug=True, port=5000)