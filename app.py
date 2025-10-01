import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, redirect, url_for, session

# OpenAI SDK (v1+)
from openai import OpenAI

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev_secret_change_me")

# Init OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

#####################################
# Basic "login" (very lightweight)  #
#####################################
@app.route("/", methods=["GET", "POST"])
def login():
    # If already "logged in", go to home
    if session.get("user"):
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username") or "Guest"
        session["user"] = username
        return redirect(url_for("home"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


#####################################
# Home → "Talk to Run.AI Coach"     #
#####################################
@app.route("/home")
def home():
    if not session.get("user"):
        return redirect(url_for("login"))
    return render_template("index.html", user=session["user"])


#####################################
# Chat (your requested route shape) #
#####################################
@app.route("/chat")
def chat_page():
    if not session.get("user"):
        return redirect(url_for("login"))
    return render_template("chat.html")


#####################################
# Chat API → OpenAI Responses API   #
#####################################
@app.route("/chat_api", methods=["POST"])
def chat_api():
    """
    Expects JSON:
      {
        "message": "user text",
        "messages": [{"role":"user|assistant|system","content":"..."}]
      }
    Returns:
      { "reply": "...", "messages": [...] }
    """
    try:
        data = request.get_json(force=True)
        user_msg = data.get("message", "").strip()
        history = data.get("messages", [])

        if not user_msg:
            return jsonify({"error": "Empty message"}), 400

        # Build a compact system prompt for your Run.AI Coach persona
        system_prompt = (
            "You are Run.AI Coach, a friendly, concise athletic assistant for a club fair. "
            "Help students with running advice, training tips, and motivation. "
            "Keep answers short, practical, and positive."
        )

        # Transform the web history to a single input for the Responses API.
        # (The Responses API also supports multi-part input, but a single string works fine here.)
        def stringify_messages(msgs):
            lines = []
            for m in msgs:
                role = m.get("role", "user")
                content = m.get("content", "")
                if role == "system":
                    lines.append(f"[system] {content}")
                elif role == "assistant":
                    lines.append(f"[assistant] {content}")
                else:
                    lines.append(f"[user] {content}")
            return "\n".join(lines)

        prior_text = stringify_messages(
            [{"role": "system", "content": system_prompt}] + history
        )
        prompt_text = f"{prior_text}\n[user] {user_msg}\n[assistant]"

        # Call OpenAI Responses API (choose a fast, cost-effective model)
        response = client.responses.create(
            model="gpt-4o-mini",
            input=prompt_text,
            max_output_tokens=500,
            temperature=0.7,
        )

        # Extract text
        reply = ""
        try:
            reply = response.output_text.strip()
        except Exception:
            # Fallback if the SDK shape changes
            reply = (response.dict().get("output_text") or "").strip()

        if not reply:
            reply = "Sorry—I didn’t catch that. Could you try again?"

        # Update history for the client
        updated_messages = history + [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": reply},
        ]

        return jsonify({"reply": reply, "messages": updated_messages})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # For local dev only
    app.run(debug=True)
