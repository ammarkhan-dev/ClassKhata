from flask import Flask

app = Flask(__name__)
COACHING_NAME = "ClassKhata"

@app.route("/")
def home():
    return f"<h1>{COACHING_NAME}</h1><p>Dashboard jaldi aa raha hai</p>"

app.run(host="0.0.0.0", port=5000)
