# app.py (with Admin Page + Chat)

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    abort,
)
from chatbot import get_response, log_chat
from pymongo import MongoClient
from flask_bcrypt import Bcrypt
from bson.objectid import ObjectId
from functools import wraps
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24)

# ----------------- DB & EXTENSIONS -----------------

bcrypt = Bcrypt(app)

client = MongoClient("mongodb://localhost:27017/")
db = client["neuronest"]
users_collection = db["users"]
chat_collection = db["chat_history"]

# ----------------- DECORATORS -----------------


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        user = users_collection.find_one({"_id": ObjectId(session["user_id"])})
        if not user or user.get("role") != "admin":
            abort(403)  # Forbidden
        return f(*args, **kwargs)

    return decorated_function


# ----------------- AUTH ROUTES -----------------


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template("register.html", error="Email and password required.")

        if users_collection.find_one({"email": email}):
            return render_template(
                "register.html", error="Email already registered."
            )

        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
        users_collection.insert_one(
            {"email": email, "password": hashed_password, "role": "user"}
        )
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = users_collection.find_one({"email": email})
        if user and bcrypt.check_password_hash(user["password"], password):
            session["user_id"] = str(user["_id"])
            session["user_email"] = user["email"]
            session["user_role"] = user.get("role", "user")
            return redirect(url_for("chat_page"))
        else:
            return render_template(
                "login.html", error="Invalid email or password."
            )

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ----------------- MAIN CHAT ROUTES -----------------


@app.route("/")
@login_required
def chat_page():
    # Pass the user's role to the template to conditionally show the admin link
    return render_template("index.html", user_role=session.get("user_role"))


@app.route("/get", methods=["POST"])
@login_required
def get_bot_response():
    """
    Ajax endpoint: frontend sends JSON {message, personality}
    Returns JSON {response}
    """
    try:
        data = request.get_json(force=True) or {}
        user_msg = (data.get("message") or "").strip()
        personality = data.get("personality", "calm therapist")

        if not user_msg:
            return jsonify({"response": "Please type a message first."}), 200

        user_id = session.get("user_id")

        # Call chatbot backend
        bot_text = get_response(user_msg, personality, user_id)

        return jsonify({"response": bot_text}), 200

    except Exception as e:
        import traceback

        err = traceback.format_exc()
        print("ERROR in /get route:\n", err)
        # For debugging: show full error in UI
        return jsonify({"response": f"DEBUG FLASK ERROR:\n{err}"}), 500


@app.route("/history", methods=["GET"])
@login_required
def get_chat_history():
    user_chats = list(
        chat_collection.find(
            {"user_id": session["user_id"]},
            {"_id": 0, "user_id": 0},
        ).sort("timestamp", 1)
    )
    return jsonify(user_chats)


# ----------------- ADMIN ROUTE -----------------


@app.route("/admin")
@admin_required
def admin_page():
    all_users = list(users_collection.find({}, {"password": 0}))

    all_chats = list(
        chat_collection.aggregate(
            [
                {
                    # Convert stored string user_id to ObjectId
                    "$addFields": {
                        "user_obj_id": {"$toObjectId": "$user_id"}
                    }
                },
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "user_obj_id",
                        "foreignField": "_id",
                        "as": "user_details",
                    }
                },
                {
                    "$unwind": {
                        "path": "$user_details",
                        "preserveNullAndEmptyArrays": True,
                    }
                },
                {"$sort": {"timestamp": -1}},
                {
                    "$project": {
                        "user_email": "$user_details.email",
                        "user_msg": 1,
                        "bot_response": 1,
                        "timestamp": 1,
                        "_id": 0,
                    }
                },
            ]
        )
    )

    return render_template("admin.html", users=all_users, chats=all_chats)


# ----------------- ENTRY POINT -----------------

if __name__ == "__main__":
    app.run(debug=True)
