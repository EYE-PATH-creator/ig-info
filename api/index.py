import re
import requests

from flask import Flask, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)


# ============================================================
# CONFIG
# ============================================================

REQUEST_TIMEOUT = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 15; "
        "K) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Referer": "https://www.google.com/",
}


# ============================================================
# ORIGINAL PARSER
# ============================================================

def lovepreetog1(content):
    followers_str = "0"
    following_str = "0"
    posts_str = "0"

    head = content.split(" - ")[0]

    for p in head.split(", "):
        p = p.strip()

        if "Followers" in p or "Follower" in p:
            followers_str = p.split()[0]

        elif "Following" in p:
            following_str = p.split()[0]

        elif "Posts" in p or "Post" in p:
            posts_str = p.split()[0]

    return followers_str, following_str, posts_str


# ============================================================
# NUMBER CONVERTER
# ============================================================

def parse_number(value):
    if not value:
        return 0

    value = value.upper().replace(",", "").strip()

    try:
        if value.endswith("K"):
            return int(float(value[:-1]) * 1_000)

        if value.endswith("M"):
            return int(float(value[:-1]) * 1_000_000)

        if value.endswith("B"):
            return int(float(value[:-1]) * 1_000_000_000)

        return int(float(value))

    except (ValueError, TypeError):
        return 0


# ============================================================
# INSTAGRAM LOOKUP
# ============================================================

def lovepreetog2(username):

    url = f"https://www.instagram.com/{username}/"

    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )

    except requests.RequestException as e:
        return {
            "success": False,
            "error": "request_failed",
            "message": str(e)
        }

    # --------------------------------------------------------
    # HTTP STATUS
    # --------------------------------------------------------

    if r.status_code == 404:
        return {
            "success": False,
            "error": "not_found",
            "username": username
        }

    if r.status_code != 200:
        return {
            "success": False,
            "error": "instagram_http_error",
            "status_code": r.status_code,
            "username": username
        }

    soup = BeautifulSoup(r.text, "html.parser")

    # --------------------------------------------------------
    # DETECT LOGIN / CHALLENGE RESPONSE
    # --------------------------------------------------------

    page_lower = r.text.lower()

    if (
        "login" in page_lower
        and "instagram" in page_lower
        and len(r.text) < 100000
    ):
        # Don't immediately reject every page containing
        # "login", because Instagram pages can contain that
        # word normally. Only reject when profile metadata
        # is also missing below.
        pass

    # --------------------------------------------------------
    # META DESCRIPTION
    # --------------------------------------------------------

    meta = soup.find(
        "meta",
        attrs={"name": "description"}
    )

    description = (
        meta.get("content", "").strip()
        if meta
        else ""
    )

    # --------------------------------------------------------
    # ORIGINAL BEHAVIOR:
    # If description doesn't exist, don't pretend the account
    # has zero followers/posts.
    # --------------------------------------------------------

    if not description:

        return {
            "success": False,
            "error": "profile_data_unavailable",
            "message": (
                "Instagram did not provide the expected "
                "profile description metadata"
            ),
            "username": username
        }

    followers, following, posts = lovepreetog1(
        description
    )

    # --------------------------------------------------------
    # FULL NAME
    # --------------------------------------------------------

    full_name = "N/A"

    og_title = soup.find(
        "meta",
        attrs={"property": "og:title"}
    )

    if og_title and og_title.get("content"):

        title = og_title["content"]

        if "(@" in title:
            full_name = title.split("(@")[0].strip()
        else:
            full_name = title.strip()

    # --------------------------------------------------------
    # PROFILE IMAGE URL
    #
    # IMPORTANT:
    # We DO NOT download it.
    # We only return the URL.
    # --------------------------------------------------------

    photo_url = None

    og_image = soup.find(
        "meta",
        attrs={"property": "og:image"}
    )

    if og_image and og_image.get("content"):
        photo_url = og_image["content"]

    # --------------------------------------------------------
    # BIO / OG DESCRIPTION
    # --------------------------------------------------------

    bio = None

    og_description = soup.find(
        "meta",
        attrs={"property": "og:description"}
    )

    if og_description and og_description.get("content"):
        bio = og_description["content"]

    # --------------------------------------------------------
    # VERIFY THAT WE ACTUALLY GOT PROFILE DATA
    # --------------------------------------------------------

    if (
        followers == "0"
        and following == "0"
        and posts == "0"
        and full_name == "N/A"
        and not photo_url
        and not bio
    ):
        return {
            "success": False,
            "error": "profile_data_unavailable",
            "message": (
                "Instagram returned a page, but no usable "
                "public profile metadata was found"
            ),
            "username": username
        }

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    return {
        "success": True,

        "username": username,

        "full_name": full_name,

        "followers": followers,
        "followers_numeric": parse_number(followers),

        "following": following,
        "following_numeric": parse_number(following),

        "posts": posts,
        "posts_numeric": parse_number(posts),

        "bio": bio,

        "profile_picture": photo_url,

        "profile_url": url
    }


# ============================================================
# USERNAME VALIDATION
# ============================================================

def valid_username(username):

    return bool(
        re.fullmatch(
            r"[A-Za-z0-9._]{1,30}",
            username
        )
    )


# ============================================================
# API ROUTES
# ============================================================

@app.route("/")
def home():

    return jsonify({
        "success": True,
        "service": "Instagram Lookup API",
        "status": "online",
        "version": "1.0.0"
    })


@app.route("/api/health")
def health():

    return jsonify({
        "success": True,
        "status": "online"
    })


@app.route("/api/instagram/<username>")
def instagram(username):

    username = username.strip().lstrip("@")

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if not valid_username(username):

        return jsonify({
            "success": False,
            "error": "invalid_username",
            "message": (
                "Username must contain only letters, "
                "numbers, dots or underscores"
            )
        }), 400

    # --------------------------------------------------------
    # LOOKUP
    # --------------------------------------------------------

    result = lovepreetog2(username)

    # --------------------------------------------------------
    # ERROR
    # --------------------------------------------------------

    if not result.get("success"):

        error = result.get("error")

        if error == "not_found":
            status = 404

        elif error == "invalid_username":
            status = 400

        elif error == "request_failed":
            status = 502

        elif error == "instagram_http_error":
            status = 502

        else:
            status = 503

        return jsonify(result), status

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    return jsonify(result)
