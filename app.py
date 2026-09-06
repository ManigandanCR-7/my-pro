import os
import re
import urllib.parse
import urllib.request
import json

from flask import Flask, abort, jsonify, render_template, request
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
CLIENT_EMAIL = os.environ.get("CLIENT_EMAIL", "")

# Change this if you want to use another Gemini model
GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-3.8-flash"
)


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)


# ============================================================
# YOUTUBE VIDEO SEARCH
# ============================================================

def get_vid(q):
    """
    Search YouTube and return the first video ID.
    """

    try:

        enc = urllib.parse.quote(q)

        url = (
            "https://www.youtube.com/results"
            f"?search_query={enc}"
        )

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
            r'"videoId":"([^"]+)"',
            data
        )

        return ids[0] if ids else None

    except Exception as e:

        print(
            "YouTube search error:",
            e
        )

        return None


# ============================================================
# GEMINI EMAIL GENERATOR
# ============================================================

def generate_email_with_gemini(command):
    """
    Send the user's email-writing request to Gemini.

    Gemini returns:

        SUBJECT: ...
        BODY: ...

    The function then extracts both values.
    """

    if not GEMINI_API_KEY:

        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )


    endpoint = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )


    prompt = f"""
You are the email-writing assistant inside Nova AI.

The user gave this voice command:

"{command}"

Create a professional email based on the user's request.

Rules:

1. Return ONLY this format:

SUBJECT: <short professional subject>

BODY:
<complete email body>

2. Do not add explanations outside this format.

3. Do not invent:
   - names
   - company names
   - prices
   - dates
   - phone numbers
   - addresses
   - URLs
   - business details

4. If the user says "my client", address the recipient naturally
   without inventing a client name.

5. If the user asks for a business proposal email,
   make the email professional, persuasive and concise.

6. Include a suitable greeting and professional closing.

7. Do not use markdown formatting.

8. The final body must be ready to paste directly into Gmail.
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


    data = json.dumps(
        payload
    ).encode("utf-8")


    req = urllib.request.Request(
        endpoint,
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
                response.read().decode(
                    "utf-8"
                )
            )

    except urllib.error.HTTPError as e:

        error_body = e.read().decode(
            "utf-8",
            errors="ignore"
        )

        print(
            "Gemini API error:",
            error_body
        )

        raise RuntimeError(
            "Gemini API request failed."
        )

    except Exception as e:

        print(
            "Gemini connection error:",
            e
        )

        raise RuntimeError(
            "Could not connect to Gemini."
        )


    try:

        text = (
            result["candidates"][0]
            ["content"]["parts"][0]["text"]
            .strip()
        )

    except Exception:

        print(
            "Unexpected Gemini response:",
            result
        )

        raise RuntimeError(
            "Gemini returned an unexpected response."
        )


    # ========================================================
    # EXTRACT SUBJECT
    # ========================================================

    subject_match = re.search(
        r"SUBJECT\s*:\s*(.*?)(?=\n\s*BODY\s*:)",
        text,
        re.IGNORECASE | re.DOTALL
    )


    # ========================================================
    # EXTRACT BODY
    # ========================================================

    body_match = re.search(
        r"BODY\s*:\s*(.*)",
        text,
        re.IGNORECASE | re.DOTALL
    )


    if subject_match:

        subject = (
            subject_match.group(1)
            .strip()
        )

    else:

        subject = "Business Proposal"


    if body_match:

        body = (
            body_match.group(1)
            .strip()
        )

    else:

        # Fallback if Gemini does not follow format
        body = text.strip()


    # Remove accidental markdown fences
    body = body.replace(
        "```",
        ""
    ).strip()


    return subject, body


# ============================================================
# EXTRACT EMAIL DETAILS
# ============================================================

def extract_email_details(command):
    """
    Try to find the recipient email from the command.

    Supports examples like:

        john@gmail.com

        john at gmail.com

        john dot gmail dot com

    If the user says "my client", CLIENT_EMAIL from .env
    will be used when available.
    """

    cmd = command.lower().strip()


    # --------------------------------------------------------
    # Direct email address
    # --------------------------------------------------------

    email_match = re.search(
        r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}',
        cmd
    )


    if email_match:

        return email_match.group(0)


    # --------------------------------------------------------
    # Voice-style email
    #
    # john at gmail dot com
    # --------------------------------------------------------

    voice_email_match = re.search(
        r'([a-zA-Z0-9._%+-]+)'
        r'\s+at\s+'
        r'([a-zA-Z0-9.-]+)'
        r'\s+dot\s+'
        r'([a-zA-Z]{2,})',
        cmd
    )


    if voice_email_match:

        username = voice_email_match.group(1)
        domain = voice_email_match.group(2)
        extension = voice_email_match.group(3)

        return (
            f"{username}@"
            f"{domain}."
            f"{extension}"
        )


    # --------------------------------------------------------
    # "my client"
    # --------------------------------------------------------

    if (
        "my client" in cmd
        and CLIENT_EMAIL
    ):

        return CLIENT_EMAIL


    # --------------------------------------------------------
    # "client"
    # --------------------------------------------------------

    if (
        "client" in cmd
        and CLIENT_EMAIL
    ):

        return CLIENT_EMAIL


    return ""


# ============================================================
# CLEAN EMAIL COMMAND
# ============================================================

def clean_email_command(command):
    """
    Removes command prefixes that are not useful
    to Gemini.
    """

    clean_cmd = command.strip()


    patterns = [
        r'^\s*please\s+',
        r'^\s*open\s+gmail\s*[,:\-]?\s*',
        r'^\s*open\s+email\s*[,:\-]?\s*',
        r'^\s*open\s+mail\s*[,:\-]?\s*',
        r'^\s*gmail\s*[,:\-]?\s*',
        r'^\s*email\s*[,:\-]?\s*',
        r'^\s*mail\s*[,:\-]?\s*'
    ]


    for pattern in patterns:

        clean_cmd = re.sub(
            pattern,
            "",
            clean_cmd,
            flags=re.IGNORECASE
        )


    return clean_cmd.strip()


# ============================================================
# NORMAL GMAIL COMMAND PARSER
# ============================================================

def parse_normal_email(command):
    """
    Handles simple email commands such as:

        Email john at gmail.com type hello

        Email john@gmail.com saying hello

        Send email to john@gmail.com message hello
    """

    cmd = command.strip().lower()


    to = ""


    # --------------------------------------------------------
    # Extract recipient
    # --------------------------------------------------------

    email_match = re.search(
        r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}',
        cmd
    )


    if email_match:

        to = email_match.group(0)


    else:

        voice_email_match = re.search(
            r'([a-zA-Z0-9._%+-]+)'
            r'\s+at\s+'
            r'([a-zA-Z0-9.-]+)'
            r'\s+dot\s+'
            r'([a-zA-Z]{2,})',
            cmd
        )


        if voice_email_match:

            to = (
                f"{voice_email_match.group(1)}@"
                f"{voice_email_match.group(2)}."
                f"{voice_email_match.group(3)}"
            )


    # --------------------------------------------------------
    # Find body
    # --------------------------------------------------------

    parts = re.split(
        r'\b(type|write|saying|message|content|with body)\b',
        cmd,
        maxsplit=1,
        flags=re.IGNORECASE
    )


    body = ""


    if len(parts) > 1:

        body = parts[-1].strip()


    # --------------------------------------------------------
    # Fallback recipient
    # --------------------------------------------------------

    if not to:

        to = extract_email_details(
            command
        )


    # --------------------------------------------------------
    # Convert "at" / "dot" email format
    # --------------------------------------------------------

    if to:

        to = (
            to.replace(
                " at ",
                "@"
            )
            .replace(
                " dot ",
                "."
            )
            .replace(
                " ",
                ""
            )
        )


        to = re.sub(
            r'[^a-zA-Z0-9@._%+\-]',
            '',
            to
        )


        if "@" not in to:

            to = f"{to}@gmail.com"


    return to, body


# ============================================================
# DETECT AI EMAIL REQUEST
# ============================================================

def is_ai_email_request(command):
    """
    Detect whether Gemini should generate the email.
    """

    cmd = command.lower()


    ai_phrases = [

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

        "write a mail",

        "draft a mail",

        "compose a mail",

        "business proposal",

        "business proposal email",

        "proposal email",

        "write proposal",

        "draft proposal",

        "create proposal"

    ]


    return any(
        phrase in cmd
        for phrase in ai_phrases
    )


# ============================================================
# HOME
# ============================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# MAIN AI AGENT ROUTER
# ============================================================

@app.route(
    "/agent",
    methods=["POST"]
)
def ai_agent_router():

    d = request.get_json(
        silent=True
    )


    # --------------------------------------------------------
    # Validate request
    # --------------------------------------------------------

    if (
        not d
        or (
            "command" not in d
            and "text_command" not in d
        )
    ):

        abort(400)


    cmd_raw = (
        d.get("command")
        or d.get("text_command")
    )


    if not isinstance(
        cmd_raw,
        str
    ):

        return jsonify({
            "success": False,
            "message": "Invalid command."
        }), 400


    cmd = cmd_raw.strip()


    if not cmd:

        return jsonify({
            "success": False,
            "message": "Command is empty."
        }), 400


    cmd_lower = cmd.lower()


    # ========================================================
    # DEFAULT RESPONSE VALUES
    # ========================================================

    target = None
    msg = None

    email_subject = ""
    email_body = ""


    # ========================================================
    # YOUTUBE
    # ========================================================

    if "youtube" in cmd_lower:

        q = cmd_lower


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


        if not q:

            target = (
                "https://www.youtube.com"
            )

            msg = (
                "Opening YouTube"
            )


        else:

            vid = get_vid(q)


            if vid:

                target = (
                    "https://www.youtube.com/"
                    f"embed/{vid}"
                    "?autoplay=1&mute=1"
                )

                msg = (
                    f"Playing {q}"
                )

            else:

                target = (
                    "https://www.youtube.com/"
                    f"results?search_query="
                    f"{urllib.parse.quote(q)}"
                )

                msg = (
                    f"Searching YouTube for {q}"
                )


    # ========================================================
    # GMAIL / EMAIL
    # ========================================================

    elif any(
        k in cmd_lower
        for k in [
            "gmail",
            "email",
            "mail",
            "message"
        ]
    ):


        # ----------------------------------------------------
        # AI GENERATED EMAIL
        # ----------------------------------------------------

        if is_ai_email_request(cmd):

            try:

                email_subject, email_body = (
                    generate_email_with_gemini(
                        cmd
                    )
                )


            except Exception as e:

                print(
                    "Email generation error:",
                    e
                )


                return jsonify({
                    "success": False,
                    "message": str(e)
                }), 500


            # ------------------------------------------------
            # Find recipient
            # ------------------------------------------------

            to = extract_email_details(
                cmd
            )


            # ------------------------------------------------
            # Gmail compose URL
            # ------------------------------------------------

            base = (
                "https://mail.google.com/"
                "mail/u/0/"
                "?view=cm&fs=1"
            )


            params = {
                "to": to,
                "su": email_subject,
                "body": email_body
            }


            target = (
                f"{base}&"
                f"{urllib.parse.urlencode(params)}"
            )


            if to:

                msg = (
                    f"Drafting email to {to}"
                )

            else:

                msg = (
                    "Opening Gmail with "
                    "your generated email"
                )


        # ----------------------------------------------------
        # NORMAL EMAIL COMMAND
        # ----------------------------------------------------

        else:

            to, body = (
                parse_normal_email(
                    cmd
                )
            )


            base = (
                "https://mail.google.com/"
                "mail/u/0/"
                "?view=cm&fs=1"
            )


            params = {
                "to": to,
                "body": body
            }


            target = (
                f"{base}&"
                f"{urllib.parse.urlencode(params)}"
            )


            if to:

                msg = (
                    f"Drafting email to {to}"
                )

            else:

                msg = (
                    "Opening Gmail compose"
                )


    # ========================================================
    # GOOGLE
    # ========================================================

    elif (
        "open google" in cmd_lower
        or cmd_lower.strip() == "google"
    ):

        target = (
            "https://www.google.com"
        )

        msg = (
            "Opening Google"
        )


    # ========================================================
    # UNKNOWN COMMAND
    # ========================================================

    else:

        return jsonify({
            "success": False,
            "message": (
                "I don't know how to handle "
                "that command yet."
            )
        }), 400


    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    return jsonify({

        "success": True,

        "message": msg,

        "url": target,

        "email_subject": email_subject,

        "email_body": email_body

    })


# ============================================================
# APPLICATION START
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            8000
        )
    )


    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
