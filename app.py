
import os
import re
import json
import time
import random
import urllib.parse
import urllib.request
import urllib.error

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS


# =========================================================
# FLASK APPLICATION
# =========================================================

app = Flask(__name__)

CORS(app)


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY",
    ""
)

CLIENT_EMAIL = os.environ.get(
    "CLIENT_EMAIL",
    ""
)

GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-3.5-flash"
)

PORT = int(
    os.environ.get(
        "PORT",
        8000
    )
)


# =========================================================
# BASIC ROUTES
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


@app.route("/health")
def health():

    return jsonify({
        "success": True,
        "message": "Nova AI backend is running."
    })


# =========================================================
# EMAIL COMMAND DETECTION
# =========================================================

def is_email_command(command):

    command_lower = command.lower()

    email_keywords = [
        "gmail",
        "email",
        "e-mail",
        "mail",
        "write an email",
        "send an email",
        "draft an email",
        "compose an email"
    ]

    return any(
        keyword in command_lower
        for keyword in email_keywords
    )


# =========================================================
# EMAIL ADDRESS EXTRACTION
# =========================================================

def extract_email(command):

    # -----------------------------------------------------
    # Normal email
    # Example:
    # john@gmail.com
    # -----------------------------------------------------

    normal_email = re.search(
        r'[\w\.-]+@[\w\.-]+\.\w+',
        command
    )

    if normal_email:

        return normal_email.group(0)


    # -----------------------------------------------------
    # Voice-style email
    #
    # Example:
    # john at gmail dot com
    # -----------------------------------------------------

    voice_email = re.search(
        r'([\w\.-]+)\s+at\s+([\w\.-]+)\s+dot\s+(\w+)',
        command,
        re.IGNORECASE
    )

    if voice_email:

        username = voice_email.group(1)
        domain = voice_email.group(2)
        extension = voice_email.group(3)

        return (
            f"{username}@"
            f"{domain}."
            f"{extension}"
        )


    # -----------------------------------------------------
    # If user says "my client"
    #
    # Use CLIENT_EMAIL from Render environment variable.
    # -----------------------------------------------------

    if CLIENT_EMAIL:

        client_phrases = [
            "my client",
            "the client",
            "to client",
            "for my client"
        ]

        command_lower = command.lower()

        if any(
            phrase in command_lower
            for phrase in client_phrases
        ):

            return CLIENT_EMAIL


    return ""


# =========================================================
# GEMINI EMAIL GENERATION
# =========================================================

def generate_email_with_gemini(command):

    if not GEMINI_API_KEY:

        raise Exception(
            "GEMINI_API_KEY is missing in Render."
        )


    # -----------------------------------------------------
    # PROMPT
    # -----------------------------------------------------

    prompt = f"""
You are Nova AI, a professional email writing assistant.

The user gave this voice instruction:

"{command}"

Your job is to understand the instruction and WRITE
THE ACTUAL EMAIL.

IMPORTANT:

Do NOT copy the user's voice command into the email.

Do NOT explain what you are doing.

Do NOT describe the instruction.

Generate the actual email that the user wants.

Example:

User instruction:

"Write an email to my client saying our business
proposal is ready and ask them to review it."

Generate:

SUBJECT: Business Proposal for Your Review

BODY:
Dear Client,

I hope you are doing well.

I am writing to share our business proposal for your review.
Please take some time to go through the proposal and let me
know your thoughts.

I would be happy to discuss any questions or suggestions
you may have.

Best regards,
[Your Name]


RULES:

1. Understand the user's intention.
2. Write the actual email.
3. Never copy the voice command as the email body.
4. Do not invent names.
5. Do not invent prices.
6. Do not invent dates.
7. Do not invent company information.
8. Do not invent attachments.
9. Use a professional and natural tone.
10. Include a greeting.
11. Include a suitable closing.
12. Keep the email concise.
13. Use paragraphs where appropriate.

Return ONLY this format:

SUBJECT: <email subject>

BODY:
<actual email body>
"""


    # -----------------------------------------------------
    # GEMINI API URL
    # -----------------------------------------------------

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )


    # -----------------------------------------------------
    # REQUEST PAYLOAD
    # -----------------------------------------------------

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

            "maxOutputTokens": 800

        }

    }


    request_data = json.dumps(
        payload
    ).encode("utf-8")


    # -----------------------------------------------------
    # RETRY CONFIGURATION
    # -----------------------------------------------------

    max_retries = 4


    # -----------------------------------------------------
    # GEMINI REQUEST
    # -----------------------------------------------------

    for attempt in range(
        max_retries
    ):

        try:

            print(
                f"Gemini request "
                f"attempt {attempt + 1}/"
                f"{max_retries}"
            )


            req = urllib.request.Request(

                url,

                data=request_data,

                headers={

                    "Content-Type":
                        "application/json",

                    "x-goog-api-key":
                        GEMINI_API_KEY

                },

                method="POST"

            )


            with urllib.request.urlopen(
                req,
                timeout=30
            ) as response:

                response_data = (
                    response
                    .read()
                    .decode("utf-8")
                )


                result = json.loads(
                    response_data
                )


            # -------------------------------------------------
            # EXTRACT GEMINI TEXT
            # -------------------------------------------------

            generated_text = (
                result
                ["candidates"]
                [0]
                ["content"]
                ["parts"]
                [0]
                ["text"]
            )


            generated_text = (
                generated_text
                .strip()
            )


            print(
                "================================"
            )

            print(
                "GEMINI RESPONSE"
            )

            print(
                "================================"
            )

            print(
                generated_text
            )

            print(
                "================================"
            )


            # -------------------------------------------------
            # EXTRACT SUBJECT
            # -------------------------------------------------

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

                subject = (
                    "Professional Message"
                )


            # -------------------------------------------------
            # EXTRACT BODY
            # -------------------------------------------------

            body_match = re.search(

                r"BODY\s*:\s*(.*)",

                generated_text,

                re.IGNORECASE |
                re.DOTALL

            )


            if body_match:

                body = (
                    body_match
                    .group(1)
                    .strip()
                )

            else:

                body = generated_text


            # -------------------------------------------------
            # CLEAN MARKDOWN CODE BLOCKS
            # -------------------------------------------------

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


            # -------------------------------------------------
            # RETURN EMAIL
            # -------------------------------------------------

            return {

                "subject":
                    subject,

                "body":
                    body

            }


        # =====================================================
        # HTTP ERRORS
        # =====================================================

        except urllib.error.HTTPError as e:

            error_body = (
                e.read()
                .decode(
                    "utf-8",
                    errors="ignore"
                )
            )


            print(
                "================================"
            )

            print(
                "GEMINI HTTP ERROR"
            )

            print(
                "STATUS:",
                e.code
            )

            print(
                "RESPONSE:",
                error_body
            )

            print(
                "================================"
            )


            # -------------------------------------------------
            # RATE LIMIT / QUOTA
            # -------------------------------------------------

            if e.code == 429:

                if attempt < max_retries - 1:

                    wait_time = (
                        (2 ** attempt)
                        +
                        random.uniform(
                            0,
                            1
                        )
                    )


                    print(
                        "Gemini rate limit reached."
                    )


                    print(
                        f"Waiting "
                        f"{wait_time:.2f}s..."
                    )


                    time.sleep(
                        wait_time
                    )


                    continue


                raise Exception(

                    "Gemini API rate limit "
                    "or quota has been exceeded. "
                    "Please check your Gemini "
                    "API quota and billing."

                )


            # -------------------------------------------------
            # OTHER GEMINI ERROR
            # -------------------------------------------------

            try:

                error_json = json.loads(
                    error_body
                )


                error_message = (

                    error_json
                    .get("error", {})
                    .get(
                        "message",
                        "Unknown Gemini API error."
                    )

                )

            except Exception:

                error_message = (
                    error_body
                    or
                    "Unknown Gemini API error."
                )


            raise Exception(

                f"Gemini API error "
                f"{e.code}: "
                f"{error_message}"

            )


        # =====================================================
        # GENERAL ERROR
        # =====================================================

        except Exception as e:

            print(
                "Gemini request error:",
                str(e)
            )

            raise


# =========================================================
# YOUTUBE SEARCH
# =========================================================

def get_youtube_video(command):

    command_lower = command.lower()

    query = command

    patterns = [

        r"play\s+(.+)",
        r"search\s+youtube\s+for\s+(.+)",
        r"open\s+youtube\s+and\s+play\s+(.+)",
        r"youtube\s+(.+)"

    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            command_lower
        )

        if match:

            query = match.group(1)

            break


    query = query.strip()


    youtube_url = (
        "https://www.youtube.com/results?search_query="
        +
        urllib.parse.quote(query)
    )


    return youtube_url


# =========================================================
# GOOGLE SEARCH
# =========================================================

def get_google_search_url(command):

    command_lower = command.lower()

    query = command


    patterns = [

        r"search google for\s+(.+)",

        r"google search\s+(.+)",

        r"search for\s+(.+)"

    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            command_lower
        )

        if match:

            query = match.group(1)

            break


    query = query.strip()


    google_url = (
        "https://www.google.com/search?q="
        +
        urllib.parse.quote(query)
    )


    return google_url


# =========================================================
# MAIN AGENT
# =========================================================

@app.route(
    "/agent",
    methods=["POST"]
)
def agent():

    try:

        data = request.get_json(
            silent=True
        )


        if not data:

            return jsonify({

                "success": False,

                "message":
                    "No JSON request received."

            }), 400


        command = data.get(
            "command",
            ""
        )


        if not command:

            return jsonify({

                "success": False,

                "message":
                    "No command received."

            }), 400


        command = command.strip()


        print(
            "================================"
        )

        print(
            "NOVA COMMAND"
        )

        print(
            command
        )

        print(
            "================================"
        )


        # =====================================================
        # EMAIL
        # =====================================================

        if is_email_command(
            command
        ):

            print(
                "Email command detected."
            )


            recipient = extract_email(
                command
            )


            # -------------------------------------------------
            # GENERATE EMAIL WITH GEMINI
            # -------------------------------------------------

            email_data = (
                generate_email_with_gemini(
                    command
                )
            )


            subject = email_data[
                "subject"
            ]


            body = email_data[
                "body"
            ]


            print(
                "================================"
            )

            print(
                "EMAIL GENERATED"
            )

            print(
                "Recipient:",
                recipient
            )

            print(
                "Subject:",
                subject
            )

            print(
                "Body:"
            )

            print(
                body
            )

            print(
                "================================"
            )


            # -------------------------------------------------
            # IMPORTANT
            #
            # DO NOT OPEN GMAIL HERE.
            #
            # Frontend receives the email,
            # displays it in the editor,
            # and user confirms it.
            # -------------------------------------------------

            return jsonify({

                "success": True,

                "type": "email",

                "email_generated": True,

                "recipient":
                    recipient,

                "subject":
                    subject,

                "body":
                    body,

                "message":
                    "Email generated successfully. Review and edit before opening Gmail."

            })


        # =====================================================
        # YOUTUBE
        # =====================================================

        if (
            "youtube" in
            command.lower()
        ):

            youtube_url = (
                get_youtube_video(
                    command
                )
            )


            return jsonify({

                "success": True,

                "type": "youtube",

                "url":
                    youtube_url,

                "message":
                    "Opening YouTube..."

            })


        # =====================================================
        # GOOGLE SEARCH
        # =====================================================

        if (
            "google" in
            command.lower()
        ):

            google_url = (
                get_google_search_url(
                    command
                )
            )


            return jsonify({

                "success": True,

                "type": "google",

                "url":
                    google_url,

                "message":
                    "Opening Google..."

            })


        # =====================================================
        # UNKNOWN COMMAND
        # =====================================================

        return jsonify({

            "success": False,

            "message":
                "Nova AI could not understand that command."

        })


    # =========================================================
    # AGENT ERROR
    # =========================================================

    except Exception as e:

        print(
            "================================"
        )

        print(
            "NOVA AGENT ERROR"
        )

        print(
            str(e)
        )

        print(
            "================================"
        )


        return jsonify({

            "success": False,

            "message":
                str(e)

        }), 500


# =========================================================
# APPLICATION START
# =========================================================

if __name__ == "__main__":

    print(
        "================================"
    )

    print(
        "NOVA AI BACKEND"
    )

    print(
        "Starting Flask server..."
    )

    print(
        "Port:",
        PORT
    )

    print(
        "Gemini model:",
        GEMINI_MODEL
    )

    print(
        "================================"
    )


    app.run(

        host="0.0.0.0",

        port=PORT,

        debug=False

    )

