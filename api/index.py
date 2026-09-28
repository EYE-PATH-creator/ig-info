import re
import requests

from flask import Flask, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 15) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def valid_username(username):
    return bool(
        re.fullmatch(r"[A-Za-z0-9._]{1,30}", username)
    )


def parse_number(value):
    if not value:
        return 0

    value = value.upper().replace(",", "").strip()

    try:
        if value.endswith("K"):
            return int(float(value[:-1]) * 1000)

        if value.endswith("M"):
            return int(float(value[:-1]) * 1000000)

        if value.endswith("B"):
            return int(float(value[:-1]) * 1000000000)

        return int(float(value))

    except ValueError:
        return 0


def parse_description(description):

    followers = "0"
    following = "0"
    posts = "0"

    if not description:
        return followers, following, posts

    head = description.split(" - ")[0]

    for item in head.split(","):
        item = item.strip()

        if "Follower" in item:
            followers = item.split()[0]

        elif "Following" in item:
            following = item.split()[0]

        elif "Post" in item:
            posts = item.split()[0]

    return followers, following, posts


def lookup_instagram(username):

    url = f"https://www.instagram.com/{username}/"

    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=10
        )

    except requests.RequestException as e:
        return {
            "success": False,
            "error": "request_failed",
            "message": str(e)
        }

    if r.status_code == 404:
        return {
            "success": False,
            "error": "not_found",
            "username": username
        }

    if r.status_code != 200:
        return {
            "success": False,
            "error": "instagram_response",
            "status_code": r.status_code
        }

    soup = BeautifulSoup(
        r.text,
        "html.parser"
    )

    # Description
    meta = soup.find(
        "meta",
        attrs={"name": "description"}
    )

    description = meta.get("content", "") if meta else ""

    followers, following, posts = parse_description(
        description
    )

    # Full name
    full_name = None

    og_title = soup.find(
        "meta",
        attrs={"property": "og:title"}
    )

    if og_title:
        title = og_title.get("content", "")

        if "(@" in title:
            full_name = title.split("(@")[0].strip()
        else:
            full_name = title

    # Profile picture URL
    profile_picture = None

    og_image = soup.find(
        "meta",
        attrs={"property": "og:image"}
    )

    if og_image:
        profile_picture = og_image.get("content")

    # Bio
    bio = None

    og_description = soup.find(
        "meta",
        attrs={"property": "og:description"}
    )

    if og_description:
        bio = og_description.get("content")

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

        "profile_picture": profile_picture,

        "profile_url": url
    }


@app.route("/")
def home():
    return jsonify({
        "success": True,
        "service": "Instagram Lookup API",
        "status": "online"
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

    if not valid_username(username):
        return jsonify({
            "success": False,
            "error": "invalid_username"
        }), 400

    result = lookup_instagram(username)

    if not result.get("success"):
        return jsonify(result), 404

    return jsonify(result)
