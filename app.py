import os
import re
import json
import urllib.parse
import urllib.request
import urllib.error

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)
CORS(app)


# ============================================================
# RENDER ENVIRONMENT VARIABLES
# ============================================================

# These values come directly from:
# Render → Your Service → Environment → Environment Variables

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

CLIENT_EMAIL = os.environ.get("CLIENT_EMAIL", "")

GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-3.8-flash"
)


# ============================================================
# BASIC CONFIGURATION
# ============================================================

PORT = int(os.environ.get("PORT", 8000))


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")


# ============================================================
# YOUTUBE VIDEO SEARCH
# ============================================================

def get_youtube_video(command):
    """
    Searches YouTube and extracts the first video ID.
    """

    try:
        query = command

        # Remove common voice commands
        query = re.sub(
            r"\b(open|play|search|show|find|watch)\b",
            "",
            query,
            flags=re.IGNORECASE
        )

        query = re.sub(
            r"\byoutube\b",
            "",
            query,
            flags=re.IGNORECASE
        )

        query = query.strip()

        if not query:
            return None

        encoded_query = urllib.parse.quote_plus(query)

        search_url = (
            "https://www.youtube.com/results?search_query="
            + encoded_query
        )

        req = urllib.request.Request(
            search_url,
            headers={
                "User-Agent":
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/120 Safari/537.36"
            }
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8", errors="ignore")

        match = re.search(
            r'"videoId":"([a-zA-Z0-9_-]{11})"',
            html
        )

        if match:
            return match.group(1)

        return None

    except Exception as e:
        print("YouTube search error:", e)
        return None


# ============================================================
# GEMINI EMAIL GENERATOR
# ============================================================

def generate_email_with_gemini(command):
    """
    Sends the user's voice command to Gemini.

    Gemini returns:

    SUBJECT: ...
    BODY: ...
    """

    if not GEMINI_API_KEY:
        raise Exception(
            "GEMINI_API_KEY is not configured in Render."
        )

    prompt = f"""
You are Nova AI, a professional AI voice assistant.

The user gave this voice command:

"{command}"

Create a professional email based on the user's request.

Return ONLY this format:

SUBJECT: <email subject>

BODY:
<complete email body>

Important rules:

1. Make the email professional and natural.
2. Keep it concise but useful.
3. Do not invent names.
4. Do not invent prices.
5. Do not invent dates.
6. Do not invent company information.
7. Do not invent attachments.
8. If the user says "business proposal", create a professional business-proposal-style email.
9. If the user mentions a client, keep the tone professional.
10. Do not include explanations outside SUBJECT and BODY.
"""

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )

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

        with urllib.request.urlopen(req, timeout=30) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as e:

        error_body = e.read().decode(
            "utf-8",
            errors="ignore"
        )

        print("Gemini HTTP error:", error_body)

        raise Exception(
            f"Gemini API error: {e.code}"
        )

    except Exception as e:

        print("Gemini connection error:", e)

        raise Exception(
            "Unable to connect to Gemini."
        )

    # ========================================================
    # EXTRACT GEMINI TEXT
    # ========================================================

    try:

        text = (
            result["candidates"][0]
            ["content"]["parts"][0]["text"]
        )

    except (KeyError, IndexError, TypeError):

        print("Unexpected Gemini response:")
        print(result)

        raise Exception(
            "Gemini returned an unexpected response."
        )

    # ========================================================
    # PARSE SUBJECT
    # ========================================================

    subject_match = re.search(
        r"SUBJECT:\s*(.+)",
        text,
        re.IGNORECASE
    )

    if subject_match:
        subject = subject_match.group(1).strip()
    else:
        subject = "Business Proposal"

    # ========================================================
    # PARSE BODY
    # ========================================================

    body_match = re.search(
        r"BODY:\s*(.*)",
        text,
        re.IGNORECASE | re.DOTALL
    )

    if body_match:
        body = body_match.group(1).strip()
    else:
        body = text.strip()

    return {
        "subject": subject,
        "body": body
    }


# ============================================================
# EMAIL ADDRESS EXTRACTION
# ============================================================

def extract_email_details(command):
    """
    Extracts an email address from the voice command.

    Supports examples such as:

    john@gmail.com
    john at gmail dot com
    email my client
    """

    email = None

    # --------------------------------------------------------
    # Normal email address
    # --------------------------------------------------------

    match = re.search(
        r'[\w\.-]+@[\w\.-]+\.\w+',
        command
    )

    if match:
        email = match.group(0)

    # --------------------------------------------------------
    # Voice-style email
    # Example:
    # john at gmail dot com
    # --------------------------------------------------------

    if not email:

        voice_command = command.lower()

        voice_command = voice_command.replace(
            " at ",
            "@"
        )

        voice_command = voice_command.replace(
            " dot ",
            "."
        )

        voice_command = voice_command.replace(
            " underscore ",
            "_"
        )

        voice_command = voice_command.replace(
            " dash ",
            "-"
        )

        match = re.search(
            r'[\w\.-]+@[\w\.-]+\.\w+',
            voice_command
        )

        if match:
            email = match.group(0)

    # --------------------------------------------------------
    # CLIENT EMAIL FROM RENDER
    # --------------------------------------------------------

    if not email:

        client_phrases = [
            "my client",
            "the client",
            "client email",
            "send to my client"
        ]

        command_lower = command.lower()

        for phrase in client_phrases:

            if phrase in command_lower:

                if CLIENT_EMAIL:
                    email = CLIENT_EMAIL

                break

    return email


# ============================================================
# DETECT AI EMAIL REQUEST
# ============================================================

def is_ai_email_request(command):

    command_lower = command.lower()

    ai_email_phrases = [

        "write an email",
        "write email",

        "draft an email",
        "draft email",

        "compose an email",
        "compose email",

        "create an email",
        "create email",

        "generate an email",
        "generate email",

        "send an email",
        "send email",

        "business proposal",

        "proposal email",

        "professional email",

        "mail my client",

        "email my client"
    ]

    return any(
        phrase in command_lower
        for phrase in ai_email_phrases
    )


# ============================================================
# NORMAL EMAIL BODY PARSER
# ============================================================

def parse_normal_email(command):

    subject = "Message from Nova AI"

    # --------------------------------------------------------
    # SUBJECT
    # --------------------------------------------------------

    subject_match = re.search(
        r'subject\s+(?:is|:)?\s*(.+?)(?:\s+body\s+|\s+message\s+|$)',
        command,
        re.IGNORECASE
    )

    if subject_match:
        subject = subject_match.group(1).strip()

    # --------------------------------------------------------
    # BODY
    # --------------------------------------------------------

    body_match = re.search(
        r'(?:body|message|content|saying|write)\s+(?:is|:)?\s*(.+)',
        command,
        re.IGNORECASE | re.DOTALL
    )

    if body_match:
        body = body_match.group(1).strip()
    else:
        body = command

    return subject, body


# ============================================================
# GMAIL COMPOSE URL
# ============================================================

def create_gmail_url(
    recipient="",
    subject="",
    body=""
):

    base_url = (
        "https://mail.google.com/mail/u/0/"
        "?view=cm&fs=1"
    )

    params = {
        "to": recipient,
        "su": subject,
        "body": body
    }

    return (
        base_url
        + "&"
        + urllib.parse.urlencode(
            params,
            quote_via=urllib.parse.quote
        )
    )


# ============================================================
# AGENT ROUTE
# ============================================================

@app.route("/agent", methods=["POST"])
def agent():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        # Support both frontend formats
        command = (
            data.get("command")
            or data.get("text_command")
            or data.get("text")
            or ""
        )

        command = command.strip()

        if not command:

            return jsonify({
                "success": False,
                "message": "No command received."
            }), 400

        print("--------------------------------")
        print("NOVA COMMAND:")
        print(command)
        print("--------------------------------")

        command_lower = command.lower()

        # ====================================================
        # GMAIL + GEMINI AI EMAIL
        # ====================================================

        if is_ai_email_request(command):

            try:

                recipient = extract_email_details(
                    command
                )

                # --------------------------------------------
                # Generate professional email with Gemini
                # --------------------------------------------

                email_data = (
                    generate_email_with_gemini(
                        command
                    )
                )

                subject = email_data["subject"]
                body = email_data["body"]

                # --------------------------------------------
                # Gmail URL
                # --------------------------------------------

                gmail_url = create_gmail_url(
                    recipient=recipient or "",
                    subject=subject,
                    body=body
                )

                return jsonify({

                    "success": True,

                    "message":
                        "AI email generated successfully.",

                    "service":
                        "gmail",

                    "email_generated":
                        True,

                    "recipient":
                        recipient or "",

                    "subject":
                        subject,

                    "body":
                        body,

                    "url":
                        gmail_url
                })

            except Exception as e:

                print(
                    "AI email generation error:",
                    e
                )

                return jsonify({

                    "success": False,

                    "message":
                        str(e)

                }), 500

        # ====================================================
        # SIMPLE GMAIL COMMAND
        # ====================================================

        if (
            "gmail" in command_lower
            or "email" in command_lower
            or "mail" in command_lower
        ):

            recipient = extract_email_details(
                command
            )

            subject, body = parse_normal_email(
                command
            )

            gmail_url = create_gmail_url(
                recipient=recipient or "",
                subject=subject,
                body=body
            )

            return jsonify({

                "success": True,

                "message":
                    "Gmail compose window ready.",

                "service":
                    "gmail",

                "recipient":
                    recipient or "",

                "subject":
                    subject,

                "body":
                    body,

                "url":
                    gmail_url
            })

        # ====================================================
        # YOUTUBE
        # ====================================================

        if "youtube" in command_lower:

            video_id = get_youtube_video(
                command
            )

            if video_id:

                youtube_url = (
                    "https://www.youtube.com/watch?v="
                    + video_id
                )

                return jsonify({

                    "success": True,

                    "message":
                        "Opening YouTube video.",

                    "service":
                        "youtube",

                    "url":
                        youtube_url
                })

            else:

                search_query = re.sub(
                    r'\byoutube\b',
                    '',
                    command,
                    flags=re.IGNORECASE
                ).strip()

                youtube_url = (
                    "https://www.youtube.com/results?"
                    + urllib.parse.urlencode({
                        "search_query":
                            search_query
                    })
                )

                return jsonify({

                    "success": True,

                    "message":
                        "Opening YouTube search.",

                    "service":
                        "youtube",

                    "url":
                        youtube_url
                })

        # ====================================================
        # GOOGLE SEARCH
        # ====================================================

        if (
            "google" in command_lower
            or "search for" in command_lower
            or "search" in command_lower
        ):

            query = re.sub(
                r'\b(open|google|search|for)\b',
                '',
                command,
                flags=re.IGNORECASE
            ).strip()

            google_url = (
                "https://www.google.com/search?"
                + urllib.parse.urlencode({
                    "q": query
                })
            )

            return jsonify({

                "success": True,

                "message":
                    "Opening Google search.",

                "service":
                    "google",

                "url":
                    google_url
            })

        # ====================================================
        # UNKNOWN COMMAND
        # ====================================================

        return jsonify({

            "success": False,

            "message":
                "Nova AI could not understand the command.",

            "command":
                command

        }), 400

    except Exception as e:

        print(
            "Agent error:",
            e
        )

        return jsonify({

            "success": False,

            "message":
                "Internal server error.",

            "error":
                str(e)

        }), 500


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({

        "status": "online",

        "service": "Nova AI",

        "gemini_configured":
            bool(GEMINI_API_KEY)

    })


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    print("========================================")
    print("        NOVA AI AGENT SERVER")
    print("========================================")

    print(
        "Gemini configured:",
        bool(GEMINI_API_KEY)
    )

    print(
        "Gemini model:",
        GEMINI_MODEL
    )

    print(
        "Client email configured:",
        bool(CLIENT_EMAIL)
    )

    print(
        "Port:",
        PORT
    )

    print("========================================")

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )
