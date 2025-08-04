import os

from dotenv import load_dotenv
from flask import Flask, render_template

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env")
)  # Load .env from root

app = Flask(__name__, template_folder="templates", static_folder="static")

# These will be read from the .env file at the project root
FASTAPI_URL = os.getenv(
    "FASTAPI_BACKEND_URL", "http://localhost:8001"
)  # Default if not set


@app.route("/")
def index():
    return render_template(
        "index.html",
        api_chat_url=f"{FASTAPI_URL}/api/chat",
        api_history_url=f"{FASTAPI_URL}/api/history",
        api_clear_url=f"{FASTAPI_URL}/api/history/clear",
    )


def run_frontend():
    print("Starting Flask frontend server on http://localhost:5000")
    # For client delivery, debug should be False.
    # use_reloader can be True if the deployment environment supports/benefits from it,
    # or False for simpler single-process servers.
    app.run(port=5000, debug=False, use_reloader=True)


if __name__ == "__main__":
    run_frontend()
