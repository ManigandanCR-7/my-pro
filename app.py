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

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

CLIENT_EMAIL = os.environ.get("CLIENT_EMAIL", "")

GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-3.6-flash"
)

PORT = int(os.environ.get("PORT", 8000))


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "online",
        "service": "Nova AI",
        "gemini_configured": bool(GEMINI_API_KEY),
        "model": GEMINI_MODEL
    })


# ============================================================
# EMAIL COMMAND DETECTION
# ============================================================

def is_email_command(command):

    command_lower = command.lower()

    email_words = [
        "gmail",
        "email",
        "e-mail",
        "mail"
    ]

    action_words = [
        "write",
        "draft",
        "compose",
        "create",
        "generate",
        "prepare",
        "send"
    ]

    has_email_word = any(
        word in command_lower
        for word in email_words
    )

    has_action_word = any(
        word in command_lower
        for word in action_words
    )

    # Examples:
    #
    # "write an email"
    # "compose email"
    # "draft a mail"
    # "send an email"
    #
    return (
        has_email_word and has_action_word
    ) or any(
        phrase in command_lower
        for phrase in [
            "business proposal",
            "proposal email",
            "write an email",
            "draft an email",
            "compose an email",
            "create an email",
            "generate an email",
            "write email",
            "draft email",
            "compose email"
        ]
    )


# ============================================================
# EXTRACT EMAIL ADDRESS
# ============================================================

def extract_email(command):

    # --------------------------------------------------------
    # Normal email
    # --------------------------------------------------------

    match = re.search(
        r'[\w\.-]+@[\w\.-]+\.\w+',
        command
    )

    if match:
        return match.group(0)

    # --------------------------------------------------------
    # Voice email
    #
    # john at gmail dot com
    # --------------------------------------------------------

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
        return match.group(0)

    # --------------------------------------------------------
    # CLIENT EMAIL
    # --------------------------------------------------------

    if any(
        phrase in command.lower()
        for phrase in [
            "my client",
            "the client",
            "client email",
            "send to my client"
        ]
    ):

        if CLIENT_EMAIL:
            return CLIENT_EMAIL

    return ""


# ============================================================
# GEMINI EMAIL GENERATOR
# ============================================================

def generate_email_with_gemini(command):

    if not GEMINI_API_KEY:

        raise Exception(
            "GEMINI_API_KEY is not configured in Render."
        )

    prompt = f"""
You are Nova AI, an intelligent professional email assistant.

The user gave this voice command:

"{command}"

Your task is to UNDERSTAND what the user wants and then WRITE
the actual email.

IMPORTANT:

The user's command is an instruction.

DO NOT copy the user's command into the email.

DO NOT simply repeat the user's words.

Instead, transform the request into a natural,
professional email.

For example:

User:
"Write an email to my client explaining our new business
proposal and ask them to review it."

You should generate something like:

Subject:
Business Proposal for Your Review

Body:
Dear Client,

I hope you are doing well.

I am writing to share our new business proposal for your
review. The proposal outlines the key aspects of the
opportunity and how we can work together effectively.

Please take some time to review the proposal and let me know
your thoughts. I would be happy to discuss any questions or
suggestions you may have.

Best regards,
[Your Name]

Another example:

User:
"Write an email to my client saying the project is ready
and ask them to review it."

Generate a proper professional email saying that the project
is ready and requesting their review.

RULES:

1. Understand the user's intention.
2. Generate the actual email.
3. Never copy the user's command as the email body.
4. Never explain what you are doing.
5. Do not mention that you are an AI.
6. Do not invent specific facts.
7. Do not invent prices.
8. Do not invent dates.
9. Do not invent company names.
10. Do not invent recipient names.
11. Use a professional and natural tone.
12. Use paragraphs where appropriate.
13. Include an appropriate greeting.
14. Include a professional closing.
15. If the user asks for a business proposal email,
    make it persuasive but professional.
16. If the user asks to request something,
    clearly make that request in the email.
17. If the user asks to inform someone about something,
    clearly communicate that information.

Return ONLY:

SUBJECT: <subject>

BODY:
<actual generated email>
"""

    # ========================================================
    # GEMINI API URL
    # ========================================================

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

        ],

        "generationConfig": {

            "temperature": 0.7,

            "maxOutputTokens": 1200

        }

    }

    request_data = json.dumps(
        payload
    ).encode("utf-8")

    req = urllib.request.Request(

        url,

        data=request_data,

        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        },

        method="POST"
    )

    # ========================================================
    # CALL GEMINI
    # ========================================================

    try:

        with urllib.request.urlopen(
            req,
            timeout=30
        ) as response:

            response_data = response.read().decode(
                "utf-8"
            )

            result = json.loads(
                response_data
            )

    except urllib.error.HTTPError as e:

        error_body = e.read().decode(
            "utf-8",
            errors="ignore"
        )

        print("================================")
        print("GEMINI HTTP ERROR")
        print(error_body)
        print("================================")

        raise Exception(
            f"Gemini API error: {e.code}"
        )

    except Exception as e:

        print("Gemini connection error:", e)

        raise Exception(
            "Unable to connect to Gemini API."
        )

    # ========================================================
    # EXTRACT RESPONSE
    # ========================================================

    try:

        generated_text = (
            result
            ["candidates"][0]
            ["content"]
            ["parts"][0]
            ["text"]
        )

    except (
        KeyError,
        IndexError,
        TypeError
    ):

        print("Unexpected Gemini response:")
        print(result)

        raise Exception(
            "Gemini returned an invalid response."
        )

    generated_text = generated_text.strip()

    print("================================")
    print("GEMINI GENERATED EMAIL")
    print("================================")
    print(generated_text)
    print("================================")

    # ========================================================
    # EXTRACT SUBJECT
    # ========================================================

    subject_match = re.search(
        r"SUBJECT\s*:\s*(.+?)(?=\n|$)",
        generated_text,
        re.IGNORECASE
    )

    if subject_match:

        subject = (
            subject_match
            .group(1)
            .strip()
        )

    else:

        subject = "Professional Message"

    # ========================================================
    # EXTRACT BODY
    # ========================================================

    body_match = re.search(
        r"BODY\s*:\s*(.*)",
        generated_text,
        re.IGNORECASE | re.DOTALL
    )

    if body_match:

        body = (
            body_match
            .group(1)
            .strip()
        )

    else:

        body = generated_text

    # ========================================================
    # REMOVE MARKDOWN CODE BLOCKS
    # ========================================================

    body = re.sub(
        r"^```(?:text|email)?",
        "",
        body,
        flags=re.IGNORECASE
    )

    body = re.sub(
        r"```$",
        "",
        body
    )

    body = body.strip()

    return {
        "subject": subject,
        "body": body
    }


# ============================================================
# GMAIL URL
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

    encoded_params = urllib.parse.urlencode(
        params,
        quote_via=urllib.parse.quote
    )

    return (
        base_url
        + "&"
        + encoded_params
    )


# ============================================================
# YOUTUBE
# ============================================================

def get_youtube_video(command):

    try:

        query = re.sub(
            r"\b(open|play|search|show|find|watch)\b",
            "",
            command,
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

        encoded_query = urllib.parse.quote_plus(
            query
        )

        search_url = (
            "https://www.youtube.com/results?"
            "search_query="
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

        with urllib.request.urlopen(
            req,
            timeout=10
        ) as response:

            html = response.read().decode(
                "utf-8",
                errors="ignore"
            )

        match = re.search(
            r'"videoId":"([a-zA-Z0-9_-]{11})"',
            html
        )

        if match:

            return match.group(1)

        return None

    except Exception as e:

        print(
            "YouTube error:",
            e
        )

        return None


# ============================================================
# AGENT
# ============================================================

@app.route(
    "/agent",
    methods=["POST"]
)
def agent():

    try:

        data = request.get_json(
            silent=True
        ) or {}

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

                "message":
                    "No command received."

            }), 400

        print("\n================================")
        print("NOVA AI COMMAND")
        print("================================")
        print(command)
        print("================================")

        command_lower = command.lower()

        # ====================================================
        # GMAIL + GEMINI
        # ====================================================

        if is_email_command(command):

            print(
                "Email request detected."
            )

            recipient = extract_email(
                command
            )

            print(
                "Recipient:",
                recipient or "Not specified"
            )

            # ------------------------------------------------
            # GENERATE ACTUAL EMAIL
            # ------------------------------------------------

            email = generate_email_with_gemini(
                command
            )

            subject = email["subject"]

            body = email["body"]

            # ------------------------------------------------
            # CREATE GMAIL COMPOSE URL
            # ------------------------------------------------

            gmail_url = create_gmail_url(

                recipient=recipient,

                subject=subject,

                body=body

            )

            return jsonify({

                "success": True,

                "service": "gmail",

                "email_generated": True,

                "recipient": recipient,

                "subject": subject,

                "body": body,

                "message":
                    "Professional email generated successfully.",

                "url": gmail_url

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

                    "service": "youtube",

                    "message":
                        "Opening YouTube.",

                    "url":
                        youtube_url

                })

            search_query = re.sub(
                r"\byoutube\b",
                "",
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

                "service": "youtube",

                "message":
                    "Opening YouTube search.",

                "url":
                    youtube_url

            })

        # ====================================================
        # GOOGLE
        # ====================================================

        if (
            "google" in command_lower
            or "search for" in command_lower
            or command_lower.startswith("search ")
        ):

            query = re.sub(
                r"\b(open|google|search|for)\b",
                "",
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

                "service": "google",

                "message":
                    "Opening Google search.",

                "url":
                    google_url

            })

        # ====================================================
        # UNKNOWN
        # ====================================================

        return jsonify({

            "success": False,

            "message":
                "Nova AI could not understand the command.",

            "command":
                command

        }), 400

    except Exception as e:

        print("\n================================")
        print("NOVA AI ERROR")
        print("================================")
        print(str(e))
        print("================================")

        return jsonify({

            "success": False,

            "message":
                str(e)

        }), 500


# ============================================================
# RUN
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
