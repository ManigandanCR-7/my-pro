
import os
import re
import json
import urllib.parse
import urllib.request
import urllib.error

from flask import Flask, abort, jsonify, render_template, request


# ==========================================
# FLASK
# ==========================================

app = Flask(__name__)


# ==========================================
# ENVIRONMENT VARIABLES
# ==========================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# You can configure your client's email here
# through an environment variable.
#
# Example:
# CLIENT_EMAIL=client@example.com
#
CLIENT_EMAIL = os.environ.get("CLIENT_EMAIL", "")

# Current Gemini model can be changed through
# GEMINI_MODEL environment variable if required.
GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-3.8-flash"
)


# ==========================================
# YOUTUBE SEARCH
# ==========================================

def get_vid(q):
    try:
        enc = urllib.parse.quote(q)

        url = f"https://www.youtube.com/results?search_query={enc}"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        data = urllib.request.urlopen(
            req,
            timeout=5
        ).read().decode()

        ids = re.findall(
            r"\"videoId\":\"([^\"]+)\"",
            data
        )

        return ids[0] if ids else None

    except Exception:
        return None


# ==========================================
# GEMINI API
# ==========================================

def generate_email_with_gemini(command):
    """
    Sends the user's email request to Gemini
    and receives a professionally written email.
    """

    if not GEMINI_API_KEY:
        return None, None

    prompt = f"""
You are an AI email writing assistant.

The user gave this command:

"{command}"

Write a professional business email based on the
user's request.

Return ONLY the following format:

SUBJECT: <email subject>

BODY:
<complete email body>

Rules:
- Make the email professional and natural.
- Do not include markdown.
- Do not include explanations outside the email.
- Do not invent a client's name.
- Do not invent pricing, dates, company names,
  services, or promises that the user did not provide.
- If the user says "business proposal", write a
  professional proposal-introduction email.
- Keep it concise but persuasive.
"""

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

    data = json.dumps(payload).encode("utf-8")

    url = (
        f"https://generativelanguage.googleapis.com/"
        f"v1beta/models/{GEMINI_MODEL}:generateContent"
    )

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        },
        method="POST"
    )

    try:

        with urllib.request.urlopen(
            req,
            timeout=30
        ) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )

        candidates = result.get(
            "candidates",
            []
        )

        if not candidates:
            return None, None

        content = candidates[0].get(
            "content",
            {}
        )

        parts = content.get(
            "parts",
            []
        )

        if not parts:
            return None, None

        generated_text = parts[0].get(
            "text",
            ""
        ).strip()

        if not generated_text:
            return None, None

        # --------------------------------------
        # Extract SUBJECT
        # --------------------------------------

        subject_match = re.search(
            r"SUBJECT\s*:\s*(.+)",
            generated_text,
            re.IGNORECASE
        )

        if subject_match:
            subject = subject_match.group(1).strip()
        else:
            subject = "Business Proposal"

        # --------------------------------------
        # Extract BODY
        # --------------------------------------

        body_match = re.search(
            r"BODY\s*:\s*(.*)",
            generated_text,
            re.IGNORECASE | re.DOTALL
        )

        if body_match:
            body = body_match.group(1).strip()
        else:
            body = generated_text

        return subject, body

    except urllib.error.HTTPError as e:

        try:
            error_body = e.read().decode()

            print(
                "Gemini API Error:",
                error_body
            )

        except Exception:
            pass

        return None, None

    except Exception as e:

        print(
            "Gemini Error:",
            str(e)
        )

        return None, None


# ==========================================
# GMAIL EMAIL PARSER
# ==========================================

def extract_email_details(command):
    """
    Extracts recipient and email body information
    from the user's command.
    """

    to = ""
    body = ""

    clean_cmd = re.sub(
        r'^(please\s+)?(open\s+)?'
        r'(gmail|email|mail|message)\s*',
        '',
        command,
        flags=re.IGNORECASE
    ).strip()

    clean_cmd = re.sub(
        r'\b(com(and|mand)?)\b',
        'com',
        clean_cmd,
        flags=re.IGNORECASE
    )

    # --------------------------------------
    # Detect explicit email address
    # --------------------------------------

    email_match = re.search(
        r'[\w\.-]+@[\w\.-]+\.\w+',
        clean_cmd
    )

    if email_match:
        to = email_match.group(0)

    # --------------------------------------
    # Detect "my client"
    # --------------------------------------

    if not to and re.search(
        r'\bmy\s+client\b',
        clean_cmd,
        re.IGNORECASE
    ):

        if CLIENT_EMAIL:
            to = CLIENT_EMAIL

    # --------------------------------------
    # Existing recipient parsing logic
    # --------------------------------------

    parts = re.split(
        r'\b(type|write|saying|message|content|with body)\b',
        clean_cmd,
        flags=re.IGNORECASE
    )

    recip_part = parts[0].strip()

    recip_part = re.sub(
        r'^(update\s+to|to|send\s+to|'
        r'and\s+update\s+to)\s*',
        '',
        recip_part,
        flags=re.IGNORECASE
    ).strip()

    # --------------------------------------
    # Existing body extraction
    # --------------------------------------

    if len(parts) > 1:
        body = parts[-1].strip()

    # --------------------------------------
    # If no email was found,
    # try converting spoken email
    # --------------------------------------

    if not to and recip_part:

        c = (
            recip_part
            .replace(" at ", "@")
            .replace(" dot ", ".")
            .replace(" ", "")
        )

        c = re.sub(
            r'[^a-zA-Z0-9@._%-]',
            '',
            c
        )

        if "@" in c:
            to = c

        elif c and c.lower() != "myclient":
            to = f"{c}@gmail.com"

    return to, body


# ==========================================
# HOME
# ==========================================

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


# ==========================================
# AI AGENT ROUTER
# ==========================================

@app.route("/agent", methods=["POST"])
def ai_agent_router():

    d = request.get_json(
        silent=True
    )

    if not d or (
        "command" not in d
        and
        "text_command" not in d
    ):
        abort(400)

    cmd_raw = (
        d.get("command")
        or
        d.get("text_command")
    )

    cmd = cmd_raw.strip().lower()


    # ======================================
    # YOUTUBE
    # ======================================

    if "youtube" in cmd:

        q = cmd

        patterns = [
            "open youtube and search",
            "open youtube and play",
            "open youtube",
            "and play",
            "play",
            "on youtube"
        ]

        for p in patterns:
            q = q.replace(
                p,
                ""
            )

        q = q.strip()

        vid = get_vid(q)

        if vid:

            target = (
                "https://www.youtube.com/embed/"
                f"{vid}?autoplay=1&mute=1"
            )

            msg = f"Playing {q}"

        else:

            target = (
                "https://www.youtube.com/results"
                f"?search_query={urllib.parse.quote(q)}"
            )

            msg = f"Searching YouTube for {q}"


    # ======================================
    # GMAIL / EMAIL
    # ======================================

    elif any(
        k in cmd
        for k in [
            "gmail",
            "email",
            "mail",
            "message"
        ]
    ):

        # ----------------------------------
        # Extract recipient
        # ----------------------------------

        to, body = extract_email_details(
            cmd
        )


        # ----------------------------------
        # Detect whether AI generation
        # is required
        # ----------------------------------

        ai_email_request = any(
            phrase in cmd
            for phrase in [
                "write an email",
                "write email",
                "draft an email",
                "draft email",
                "compose an email",
                "compose email",
                "business proposal",
                "proposal",
                "professional email",
                "write a message"
            ]
        )


        # ----------------------------------
        # Generate email using Gemini
        # ----------------------------------

        subject = ""

        if ai_email_request:

            generated_subject, generated_body = (
                generate_email_with_gemini(cmd)
            )

            if generated_body:

                subject = generated_subject
                body = generated_body

            else:

                # Gemini failed.
                # Keep a simple fallback.
                if not body:
                    body = (
                        "Hello,\n\n"
                        "I would like to discuss "
                        "a business proposal with you."
                    )

                subject = (
                    "Business Proposal"
                )


        # ----------------------------------
        # Gmail base compose URL
        # ----------------------------------

        base = (
            "https://mail.google.com/mail/u/0/"
            "?view=cm&fs=1"
        )


        # ----------------------------------
        # Gmail parameters
        # ----------------------------------

        params = urllib.parse.urlencode(
            {
                "to": to,
                "su": subject,
                "body": body
            }
        )


        target = (
            f"{base}&{params}"
        )


        # ----------------------------------
        # Response message
        # ----------------------------------

        if ai_email_request:

            msg = (
                f"Drafting AI-generated email "
                f"to {to or 'your client'}"
            )

        else:

            msg = (
                f"Drafting email to "
                f"{to or 'recipient'}"
            )


    # ======================================
    # UNKNOWN COMMAND
    # ======================================

    else:

        return jsonify({
            "success": False,
            "message": "I don't know how to handle that command.",
            "url": None
        }), 400


    # ======================================
    # FINAL API RESPONSE
    # ======================================

    return jsonify({

        "success": True,

        "message": msg,

        "url": target,

        # Extra information for frontend
        # if you want to display it.

        "email_subject": (
            subject
            if "subject" in locals()
            else ""
        ),

        "email_body": (
            body
            if "body" in locals()
            else ""
        )

    })


# ==========================================
# RUN
# ==========================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                8000
            )
        )
    )
