# ==================================================================
#  InstaMini - an Instagram-style website   (AICT project)
#  ALL THE CODE IN ONE FILE
#
#  HOW TO RUN (in VS Code):
#    1. Open a terminal:  Terminal -> New Terminal
#    2. Install Flask once:      pip install flask
#    3. Run this file:           python instamini.py
#    4. Open in the browser:     http://127.0.0.1:5000
#    5. Log in as   ali   with password   123456
#
#  The first time you run it, this file creates by itself:
#    - instamini.db         (the database, with 5 fake users and 10 posts)
#    - static/uploads/      (the fake pictures)
#  To start fresh again, delete instamini.db and run the file again.
#
#  WHO WROTE WHICH PART:
#    PERSON A - DATABASE  (SQL tables, database functions, fake data)
#    PERSON B - FRONTEND  (HTML + CSS of every page)
#    PERSON C - BACKEND 1 (signup, login, logout, profile, follow, search)
#    PERSON D - BACKEND 2 (feed, create post, like, comment, delete)
#
#  How the parts talk to each other:
#
#    Browser  <->  routes (Person C + D)  <->  db_ functions (Person A)  <->  instamini.db
#                        |
#                        v
#                 PAGE_HTML (Person B) shows the page
# ==================================================================

import os
import sqlite3                     # the database (built into Python)
import uuid                        # makes random unique names for pictures
from datetime import date, datetime
from functools import wraps        # used to build the login_required decorator

from flask import Flask, render_template, request, redirect, url_for, session, flash
from jinja2 import DictLoader      # lets the HTML live inside this Python file
from werkzeug.security import generate_password_hash, check_password_hash

# The folder this file is in. Everything is saved next to it,
# no matter which folder you run Python from.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "instamini.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")


# ##################################################################
# ##################################################################
#
#   PERSON A - DATABASE
#   A1 - The 5 tables (SQL)
#   A2 - Database functions (every SQL query of the app)
#   A3 - Fake data for the demo
#
# ##################################################################
# ##################################################################


# ==================================================================
#  A1 - THE 5 TABLES (SQL)
#    users     - everyone who signs up
#    posts     - pictures that users upload
#    likes     - which user liked which post
#    comments  - what users wrote under posts
#    follows   - who follows whom
# ==================================================================
SCHEMA_SQL = """
DROP TABLE IF EXISTS follows;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS likes;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS users;


-- ------------------------------------------------------------
-- 1. USERS table
--    One row = one person who signed up.
--    These columns match the fields of our signup form.
-- ------------------------------------------------------------
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,  -- unique number for every user (1, 2, 3...)
    full_name     TEXT NOT NULL,                      -- NOT NULL = this field cannot be empty
    username      TEXT NOT NULL UNIQUE,               -- UNIQUE = no two users can have the same username
    email         TEXT NOT NULL UNIQUE,               -- same for email
    password_hash TEXT NOT NULL,                      -- we NEVER store the real password, only its hash
    dob           TEXT NOT NULL,                      -- date of birth, stored like '2006-05-14'
    gender        TEXT,                               -- 'Male', 'Female' or 'Prefer not to say'
    phone         TEXT,                               -- stored as TEXT because numbers can start with 0
    city          TEXT,
    country       TEXT,
    bio           TEXT DEFAULT '',                    -- DEFAULT = value used if nothing is given
    profile_pic   TEXT DEFAULT 'default.svg',         -- only the FILE NAME, the image is in static/uploads/
    account_type  TEXT DEFAULT 'Personal',            -- 'Personal', 'Creator' or 'Business'
    interests     TEXT DEFAULT '',                    -- checkboxes joined with commas, e.g. 'travel,food'
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP      -- date and time of signup, filled in automatically
);


-- ------------------------------------------------------------
-- 2. POSTS table
--    One row = one picture a user uploaded.
-- ------------------------------------------------------------
CREATE TABLE posts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,                     -- WHO made this post (points to users.id)
    image       TEXT NOT NULL,                        -- file name of the picture
    caption     TEXT DEFAULT '',
    mood        TEXT DEFAULT 'Happy',                 -- our unique feature: Happy / Sad / Hyped / Chill
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    -- FOREIGN KEY = user_id must be a real id from the users table.
    -- ON DELETE CASCADE = if the user is deleted, their posts are deleted too.
);


-- ------------------------------------------------------------
-- 3. LIKES table
--    One row = "user X liked post Y".
-- ------------------------------------------------------------
CREATE TABLE likes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,                        -- who liked
    post_id  INTEGER NOT NULL,                        -- which post
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    UNIQUE (user_id, post_id)
    -- UNIQUE pair = the same user cannot like the same post twice.
);


-- ------------------------------------------------------------
-- 4. COMMENTS table
--    One row = one comment under a post.
-- ------------------------------------------------------------
CREATE TABLE comments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,                     -- who wrote the comment
    post_id     INTEGER NOT NULL,                     -- on which post
    text        TEXT NOT NULL,                        -- the comment itself
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);


-- ------------------------------------------------------------
-- 5. FOLLOWS table
--    One row = "follower_id follows following_id".
--    Example: (1, 3) means user 1 follows user 3.
-- ------------------------------------------------------------
CREATE TABLE follows (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    follower_id   INTEGER NOT NULL,                   -- the person who clicks "Follow"
    following_id  INTEGER NOT NULL,                   -- the person being followed
    FOREIGN KEY (follower_id)  REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (following_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (follower_id, following_id)                -- can't follow the same person twice
);
"""


# ==================================================================
#  A2 - DATABASE FUNCTIONS
#  Every function follows the same 3 steps:
#    1. open a connection   2. run ONE SQL query   3. close and return
#  The routes never write SQL themselves, they call these db_ functions.
# ==================================================================

def get_connection():
    """Open a connection to the database file."""
    conn = sqlite3.connect(DATABASE)
    # row_factory lets us read columns by NAME: user['username']
    conn.row_factory = sqlite3.Row
    # SQLite ignores FOREIGN KEYs unless we switch them on
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all 5 tables (deletes old data!)."""
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)     # executescript runs many SQL statements at once
    conn.commit()
    conn.close()


# ------------------------------------------------------------
#  USERS  (used by Person C)
# ------------------------------------------------------------

def db_create_user(full_name, username, email, password_hash, dob, gender,
                phone, city, country, bio, profile_pic, account_type, interests):
    """Save a new user from the signup form. Returns the new user's id."""
    conn = get_connection()
    # The ? marks are placeholders. Python fills them in safely.
    # We NEVER put user input directly into the SQL text, because
    # that allows "SQL injection" attacks.
    cursor = conn.execute(
        """INSERT INTO users (full_name, username, email, password_hash, dob, gender,
                              phone, city, country, bio, profile_pic, account_type, interests)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (full_name, username, email, password_hash, dob, gender,
         phone, city, country, bio, profile_pic, account_type, interests)
    )
    conn.commit()                  # commit = actually save the change
    new_id = cursor.lastrowid      # the id SQLite gave the new row
    conn.close()
    return new_id


def db_get_user_by_username(username):
    """Find one user by username. Returns None if not found."""
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()                   # fetchone = only one row
    conn.close()
    return user


def db_get_user_by_email(email):
    """Find one user by email (to check if the email is already taken)."""
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return user


def db_get_user_by_id(user_id):
    """Find one user by id (we keep the id in the session after login)."""
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return user


def db_update_profile(user_id, full_name, bio, city, country, profile_pic, account_type, interests):
    """Save changes from the Edit Profile page."""
    conn = get_connection()
    conn.execute(
        """UPDATE users
           SET full_name = ?, bio = ?, city = ?, country = ?,
               profile_pic = ?, account_type = ?, interests = ?
           WHERE id = ?""",
        (full_name, bio, city, country, profile_pic, account_type, interests, user_id)
    )
    conn.commit()
    conn.close()


def db_search_users(text):
    """Find users whose username or full name contains the search text."""
    conn = get_connection()
    # LIKE with % means "contains". '%ali%' matches 'ali', 'alina', 'khalid'.
    pattern = "%" + text + "%"
    users = conn.execute(
        """SELECT id, username, full_name, profile_pic FROM users
           WHERE username LIKE ? OR full_name LIKE ?
           ORDER BY username""",
        (pattern, pattern)
    ).fetchall()                   # fetchall = list of all matching rows
    conn.close()
    return users


# ------------------------------------------------------------
#  POSTS  (used by Person D)
# ------------------------------------------------------------

def db_create_post(user_id, image, caption, mood):
    """Save a new post. Returns the new post's id."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO posts (user_id, image, caption, mood) VALUES (?, ?, ?, ?)",
        (user_id, image, caption, mood)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def db_get_feed(user_id, mood=None):
    """
    Posts for the home feed: my own posts + posts of people I follow,
    newest first. If mood is given (e.g. 'Happy'), only show that mood.
    Each post also comes with the author's username and picture,
    plus its number of likes and comments.
    """
    conn = get_connection()
    sql = """
        SELECT posts.*,
               users.username,
               users.profile_pic,
               (SELECT COUNT(*) FROM likes    WHERE likes.post_id    = posts.id) AS like_count,
               (SELECT COUNT(*) FROM comments WHERE comments.post_id = posts.id) AS comment_count
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE (posts.user_id = ?
               OR posts.user_id IN (SELECT following_id FROM follows WHERE follower_id = ?))
    """
    values = [user_id, user_id]

    # Our unique feature: filter the feed by mood.
    if mood:
        sql += " AND posts.mood = ?"
        values.append(mood)

    sql += " ORDER BY posts.created_at DESC, posts.id DESC"   # newest first

    posts = conn.execute(sql, values).fetchall()
    conn.close()
    return posts


def db_get_post(post_id):
    """One post with its author's info and like count (for the single post page)."""
    conn = get_connection()
    post = conn.execute(
        """SELECT posts.*,
                  users.username,
                  users.profile_pic,
                  (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) AS like_count
           FROM posts
           JOIN users ON posts.user_id = users.id
           WHERE posts.id = ?""",
        (post_id,)
    ).fetchone()
    conn.close()
    return post


def db_get_user_posts(user_id):
    """All posts of one user, newest first (for the profile grid)."""
    conn = get_connection()
    posts = conn.execute(
        "SELECT * FROM posts WHERE user_id = ? ORDER BY created_at DESC, id DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return posts


def db_count_posts(user_id):
    """How many posts a user has made."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) FROM posts WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row[0]


def db_delete_post(post_id, user_id):
    """
    Delete a post, but ONLY if it belongs to this user.
    (The 'AND user_id = ?' stops user A from deleting user B's post.)
    Its likes and comments are deleted automatically (ON DELETE CASCADE).
    """
    conn = get_connection()
    conn.execute(
        "DELETE FROM posts WHERE id = ? AND user_id = ?", (post_id, user_id)
    )
    conn.commit()
    conn.close()


def db_get_trending(limit=9):
    """Most-liked posts of all time (optional Explore page)."""
    conn = get_connection()
    posts = conn.execute(
        """SELECT posts.*, users.username, COUNT(likes.id) AS like_count
           FROM posts
           JOIN users ON posts.user_id = users.id
           LEFT JOIN likes ON likes.post_id = posts.id
           GROUP BY posts.id
           ORDER BY like_count DESC
           LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close()
    return posts


# ------------------------------------------------------------
#  LIKES  (used by Person D)
# ------------------------------------------------------------

def db_has_liked(user_id, post_id):
    """True if this user already liked this post, otherwise False."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM likes WHERE user_id = ? AND post_id = ?", (user_id, post_id)
    ).fetchone()
    conn.close()
    return row is not None


def db_get_liked_post_ids(user_id):
    """
    A list of the ids of ALL posts this user has liked, e.g. [2, 5, 7].
    The feed uses it to show a red heart. One query for the whole feed
    is much faster than asking "did I like this?" once for every post.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT post_id FROM likes WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()
    return [row["post_id"] for row in rows]


def db_like_post(user_id, post_id):
    """Add a like. INSERT OR IGNORE does nothing if it is already liked."""
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO likes (user_id, post_id) VALUES (?, ?)", (user_id, post_id)
    )
    conn.commit()
    conn.close()


def db_unlike_post(user_id, post_id):
    """Remove a like."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM likes WHERE user_id = ? AND post_id = ?", (user_id, post_id)
    )
    conn.commit()
    conn.close()


# ------------------------------------------------------------
#  COMMENTS  (used by Person D)
# ------------------------------------------------------------

def db_add_comment(user_id, post_id, text):
    """Save a comment under a post."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO comments (user_id, post_id, text) VALUES (?, ?, ?)",
        (user_id, post_id, text)
    )
    conn.commit()
    conn.close()


def db_get_comments(post_id):
    """All comments of a post with the commenter's username, oldest first."""
    conn = get_connection()
    comments = conn.execute(
        """SELECT comments.*, users.username, users.profile_pic
           FROM comments
           JOIN users ON comments.user_id = users.id
           WHERE comments.post_id = ?
           ORDER BY comments.created_at ASC, comments.id ASC""",
        (post_id,)
    ).fetchall()
    conn.close()
    return comments


# ------------------------------------------------------------
#  FOLLOWS  (used by Person C)
# ------------------------------------------------------------

def db_follow(follower_id, following_id):
    """follower_id starts following following_id."""
    if follower_id == following_id:
        return                      # you can't follow yourself
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO follows (follower_id, following_id) VALUES (?, ?)",
        (follower_id, following_id)
    )
    conn.commit()
    conn.close()


def db_unfollow(follower_id, following_id):
    """follower_id stops following following_id."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM follows WHERE follower_id = ? AND following_id = ?",
        (follower_id, following_id)
    )
    conn.commit()
    conn.close()


def db_is_following(follower_id, following_id):
    """True if follower_id already follows following_id."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM follows WHERE follower_id = ? AND following_id = ?",
        (follower_id, following_id)
    ).fetchone()
    conn.close()
    return row is not None


def db_count_followers(user_id):
    """How many people follow this user."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) FROM follows WHERE following_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row[0]


def db_count_following(user_id):
    """How many people this user follows."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) FROM follows WHERE follower_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row[0]


# ==================================================================
#  A3 - FAKE DATA FOR THE DEMO
#  5 users (all with password 123456), 10 posts, follows, likes, comments.
# ==================================================================

def make_fake_pictures():
    """Draw simple pictures (SVG files) for the fake posts and the default profile picture."""
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # (file name, text on the picture, top color, bottom color)
    pictures = [
        ("post1.svg",  "First post", "#14B8A6", "#0F172A"),
        ("post2.svg",  "Sunset",     "#F59E0B", "#7C2D12"),
        ("post3.svg",  "We won!",    "#FB923C", "#1E293B"),
        ("post4.svg",  "Biryani",    "#FACC15", "#713F12"),
        ("post5.svg",  "Naran",      "#4ADE80", "#14532D"),
        ("post6.svg",  "Exams...",   "#60A5FA", "#1E3A8A"),
        ("post7.svg",  "New camera", "#F43F5E", "#4C0519"),
        ("post8.svg",  "Practice",   "#38BDF8", "#0C4A6E"),
        ("post9.svg",  "Painting",   "#A78BFA", "#2E1065"),
        ("post10.svg", "New music",  "#2DD4BF", "#134E4A"),
    ]
    for name, text, top, bottom in pictures:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600">'
            '<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/>'
            '</linearGradient></defs>'
            '<rect width="600" height="600" fill="url(#g)"/>'
            f'<text x="300" y="315" font-family="Arial" font-size="48" font-weight="bold" '
            f'fill="white" text-anchor="middle">{text}</text>'
            '<text x="300" y="560" font-family="Arial" font-size="24" fill="white" '
            'text-anchor="middle">InstaMini</text></svg>'
        )
        with open(os.path.join(UPLOAD_FOLDER, name), "w", encoding="utf-8") as f:
            f.write(svg)

    # default profile picture: a gray person shape
    avatar = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300">'
        '<rect width="300" height="300" fill="#1E293B"/>'
        '<circle cx="150" cy="105" r="45" fill="#94A3B8"/>'
        '<ellipse cx="150" cy="250" rx="90" ry="80" fill="#94A3B8"/></svg>'
    )
    with open(os.path.join(UPLOAD_FOLDER, "default.svg"), "w", encoding="utf-8") as f:
        f.write(avatar)


def seed_database():
    """Create the tables and fill them with fake data."""
    init_db()
    password = generate_password_hash("123456")     # same password for every fake user

    users = [
        # full_name,     username, email,                dob,          gender,   phone,         city,         country,    bio,                             account_type, interests
        ("Ali Raza",     "ali",    "ali@example.com",    "2006-03-12", "Male",   "03001234567", "Islamabad",  "Pakistan", "Coffee and code",               "Personal",   "tech,gaming"),
        ("Sara Khan",    "sara",   "sara@example.com",   "2005-11-02", "Female", "03111234567", "Lahore",     "Pakistan", "Taking pictures of everything", "Creator",    "photography,travel"),
        ("Hamza Malik",  "hamza",  "hamza@example.com",  "2006-07-25", "Male",   "03211234567", "Karachi",    "Pakistan", "Cricket is life",               "Personal",   "sports"),
        ("Ayesha Noor",  "ayesha", "ayesha@example.com", "2006-01-18", "Female", "03331234567", "Rawalpindi", "Pakistan", "Food lover and part-time chef", "Creator",    "food,art"),
        ("Usman Tariq",  "usman",  "usman@example.com",  "2005-09-30", "Male",   "03451234567", "Peshawar",   "Pakistan", "Music, mountains, repeat",      "Business",   "music,travel"),
    ]
    for u in users:
        db_create_user(u[0], u[1], u[2], password, u[3], u[4], u[5], u[6], u[7], u[8],
                       "default.svg", u[9], u[10])
    # the users got ids 1 to 5:  1=ali  2=sara  3=hamza  4=ayesha  5=usman

    posts = [   # (user_id, picture, caption, mood)
        (1, "post1.svg",  "First post on InstaMini!",          "Happy"),
        (2, "post2.svg",  "Sunset at Badshahi Mosque",         "Chill"),
        (3, "post3.svg",  "We won the match!!",                "Hyped"),
        (4, "post4.svg",  "Homemade biryani turned out great", "Happy"),
        (5, "post5.svg",  "Weekend in Naran",                  "Chill"),
        (1, "post6.svg",  "Exams next week...",                "Sad"),
        (2, "post7.svg",  "New camera day",                    "Hyped"),
        (3, "post8.svg",  "Practice session",                  "Hyped"),
        (4, "post9.svg",  "Painting my first canvas",          "Chill"),
        (5, "post10.svg", "Working on new music",              "Happy"),
    ]
    for p in posts:
        db_create_post(p[0], p[1], p[2], p[3])

    for a, b in [(1, 2), (1, 3), (1, 4), (2, 1), (2, 5), (3, 1), (4, 2), (5, 1), (5, 2)]:
        db_follow(a, b)          # a follows b

    for u, p in [(1, 2), (1, 3), (2, 1), (3, 1), (4, 1), (5, 2), (2, 3), (3, 7), (1, 7), (4, 5)]:
        db_like_post(u, p)       # user u likes post p

    db_add_comment(2, 1, "Welcome to InstaMini!")
    db_add_comment(3, 1, "Finally!")
    db_add_comment(1, 2, "Beautiful view")
    db_add_comment(4, 3, "Congrats!!")
    db_add_comment(1, 4, "Send some over")


# ##################################################################
# ##################################################################
#
#   PERSON B - FRONTEND (HTML + CSS of every page)
#
#   All pages are in PAGE_HTML below. A route shows a page with:
#       render_template("index.html", page="login")
#   and only that page's {% if page == ... %} section is shown.
#
# ##################################################################
# ##################################################################

PAGE_HTML = r'''<!--
  ============================================================
  InstaMini - ALL PAGES IN ONE FILE (index.html)
  Owner: Person B (Frontend)

  This one file contains every page of the website.
  The backend chooses which page to show by sending "page":

      render_template("index.html", page="login")
      render_template("index.html", page="feed", posts=..., ...)

  Then the matching IF section below is shown and the others are skipped.

  SECTIONS IN THIS FILE:
    PART A  - HEAD (title, font)
    PART A2 - CSS (all styling, 14 sections)
    PART B  - NAVBAR (top bar, only when logged in)
    PART C  - FLASH MESSAGES (red / green banners)
    PAGE 1  - LOGIN
    PAGE 2  - SIGNUP (detailed registration form)
    PAGE 3  - FEED (home page with mood filter)
    PAGE 4  - SINGLE POST (with comments)
    PAGE 5  - CREATE POST
    PAGE 6  - PROFILE
    PAGE 7  - EDIT PROFILE
    PAGE 8  - SEARCH
  ============================================================
-->
<!DOCTYPE html>
<html lang="en">

<!-- ============================================================
     PART A - HEAD
     ============================================================ -->
<head>
  <meta charset="UTF-8">
  <!-- makes the page fit phone screens -->
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>InstaMini</title>

  <!-- Poppins font from Google Fonts -->
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">

  <!-- ============================================================
       PART A2 - CSS (all the styling of the website)
       Everything between <style> and </style> is CSS.
       ============================================================ -->
  <style>
    /* ============================================================
       InstaMini - Stylesheet (style.css)
       Owner: Person B (Frontend)
       Theme: "Midnight Teal" (dark navy + teal)
       ============================================================ */

    /* ---------- 1. Theme colors (CSS variables) ----------
       All colors live here. To change the theme, edit only these lines.
       Use them anywhere with var(--name). */
    :root {
      --bg: #0F172A;        /* page background (deep navy) */
      --card: #1E293B;      /* cards, navbar, inputs */
      --border: #334155;    /* thin borders */
      --text: #E2E8F0;      /* main text */
      --muted: #94A3B8;     /* gray text: times, counts */
      --accent: #14B8A6;    /* teal: buttons, links, logo */
      --like: #F43F5E;      /* red heart */
      --error: #F87171;
      --success: #4ADE80;

      /* mood tag colors (our unique feature) */
      --happy: #FACC15;
      --sad: #60A5FA;
      --hyped: #FB923C;
      --chill: #4ADE80;

      /* tells the browser to draw its own controls (date picker, file button) in dark mode */
      color-scheme: dark;
    }

    /* ---------- 2. Basic reset ---------- */
    * {
      box-sizing: border-box;   /* width includes padding and border */
      margin: 0;
      padding: 0;
    }

    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Poppins', sans-serif;
      line-height: 1.5;
    }

    a {
      color: var(--accent);
      text-decoration: none;
    }

    a:hover {
      text-decoration: underline;
    }

    /* ---------- 3. Navbar (top bar on every page) ---------- */
    .navbar {
      background: var(--card);
      border-bottom: 1px solid var(--border);
      position: sticky;          /* stays at the top when scrolling */
      top: 0;
      z-index: 10;
    }

    .nav-inner {
      max-width: 935px;
      margin: 0 auto;            /* centers the bar */
      padding: 12px 16px;
      display: flex;             /* puts logo and links in one row */
      justify-content: space-between;
      align-items: center;
    }

    .logo {
      font-size: 26px;
      font-weight: 700;
      color: var(--accent);
    }

    .logo:hover {
      text-decoration: none;
    }

    .nav-links {
      display: flex;
      gap: 18px;
      align-items: center;
    }

    .nav-links a {
      color: var(--text);
      font-size: 15px;
    }

    .nav-links a.new-post {
      background: var(--accent);
      color: var(--bg);
      padding: 6px 14px;
      border-radius: 20px;
      font-weight: 600;
    }

    /* ---------- 4. Page container ---------- */
    .container {
      max-width: 935px;
      margin: 24px auto;
      padding: 0 16px;
    }

    .narrow {
      max-width: 500px;          /* for feed and forms */
      margin: 0 auto;
    }

    /* ---------- 5. Flash messages (red / green banners) ---------- */
    .flash {
      padding: 10px 14px;
      border-radius: 8px;
      margin-bottom: 16px;
      font-size: 14px;
    }

    .flash.error {
      background: rgba(248, 113, 113, 0.15);
      border: 1px solid var(--error);
      color: var(--error);
    }

    .flash.success {
      background: rgba(74, 222, 128, 0.15);
      border: 1px solid var(--success);
      color: var(--success);
    }

    /* ---------- 6. Cards ---------- */
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 20px;
    }

    /* ---------- 7. Forms ---------- */
    .auth-box {
      max-width: 400px;
      margin: 40px auto;
      text-align: center;
    }

    .auth-box .logo {
      display: block;
      font-size: 40px;
      margin-bottom: 6px;
    }

    .tagline {
      color: var(--muted);
      margin-bottom: 20px;
    }

    .form-section {
      text-align: left;
      margin-bottom: 22px;
    }

    .form-section h3 {
      color: var(--accent);
      font-size: 15px;
      text-transform: uppercase;
      letter-spacing: 1px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 6px;
      margin-bottom: 12px;
    }

    label {
      display: block;
      font-size: 13px;
      color: var(--muted);
      margin: 10px 0 4px;
      text-align: left;
    }

    input[type="text"],
    input[type="email"],
    input[type="password"],
    input[type="tel"],
    input[type="date"],
    input[type="search"],
    select,
    textarea {
      width: 100%;
      padding: 10px 12px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--text);
      font-family: inherit;
      font-size: 14px;
    }

    input:focus,
    select:focus,
    textarea:focus {
      outline: none;
      border-color: var(--accent);   /* teal border when clicked */
    }

    input[type="file"] {
      color: var(--muted);
      font-size: 14px;
    }

    textarea {
      resize: vertical;
      min-height: 80px;
    }

    /* two fields side by side */
    .row {
      display: flex;
      gap: 12px;
    }

    .row > div {
      flex: 1;
    }

    /* radio buttons and checkboxes in a row */
    .choices {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 18px;
    }

    .choices label {
      display: flex;
      align-items: center;
      gap: 6px;
      color: var(--text);
      margin: 0;
      font-size: 14px;
      cursor: pointer;
    }

    input[type="radio"],
    input[type="checkbox"] {
      accent-color: var(--accent);
    }

    .hint {
      font-size: 12px;
      color: var(--muted);
    }

    /* ---------- 8. Buttons ---------- */
    .btn {
      display: inline-block;
      background: var(--accent);
      color: var(--bg);
      border: none;
      padding: 10px 20px;
      border-radius: 8px;
      font-family: inherit;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
    }

    .btn:hover {
      opacity: 0.9;
      text-decoration: none;
    }

    .btn-full {
      width: 100%;
      margin-top: 12px;
    }

    .btn-outline {
      background: transparent;
      color: var(--text);
      border: 1px solid var(--border);
    }

    .btn-small {
      padding: 6px 14px;
      font-size: 13px;
    }

    .btn-danger {
      background: transparent;
      color: var(--error);
      border: 1px solid var(--error);
    }

    .switch-box {
      text-align: center;
      font-size: 14px;
    }

    /* ---------- 9. Posts (feed and single post) ---------- */
    .post {
      padding: 0;
      overflow: hidden;          /* keeps the image inside the rounded corners */
    }

    .post-header {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 14px;
    }

    .post-header .username {
      font-weight: 600;
      color: var(--text);
    }

    .post-header .time {
      color: var(--muted);
      font-size: 12px;
      margin-left: auto;         /* pushes the time to the right */
    }

    .post-image {
      width: 100%;
      display: block;
      aspect-ratio: 1 / 1;       /* square, like Instagram */
      object-fit: cover;
    }

    .post-body {
      padding: 12px 14px;
    }

    .post-actions {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 6px;
    }

    .post-actions form {
      display: inline;
    }

    .icon-btn {
      background: none;
      border: none;
      color: var(--text);
      font-size: 22px;
      cursor: pointer;
    }

    .icon-btn.liked {
      color: var(--like);
    }

    .count {
      font-weight: 600;
      font-size: 14px;
    }

    .caption {
      font-size: 14px;
    }

    .caption b {
      margin-right: 4px;
    }

    .view-comments {
      color: var(--muted);
      font-size: 13px;
    }

    /* round profile pictures */
    .avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      object-fit: cover;
      border: 2px solid var(--accent);
    }

    .avatar-big {
      width: 130px;
      height: 130px;
      border-radius: 50%;
      object-fit: cover;
      border: 3px solid var(--accent);
    }

    /* ---------- 10. Mood tags (our unique feature) ---------- */
    .mood {
      display: inline-block;
      font-size: 12px;
      font-weight: 600;
      padding: 2px 10px;
      border-radius: 12px;
      color: var(--bg);
    }

    .mood-happy { background: var(--happy); }
    .mood-sad   { background: var(--sad); }
    .mood-hyped { background: var(--hyped); }
    .mood-chill { background: var(--chill); }

    /* mood filter buttons above the feed */
    .mood-filter {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 20px;
    }

    .mood-filter a {
      padding: 6px 14px;
      border-radius: 20px;
      border: 1px solid var(--border);
      color: var(--text);
      font-size: 13px;
    }

    .mood-filter a.active {
      background: var(--accent);
      color: var(--bg);
      border-color: var(--accent);
    }

    /* ---------- 11. Comments ---------- */
    .comment {
      display: flex;
      gap: 10px;
      padding: 10px 0;
      border-bottom: 1px solid var(--border);
      font-size: 14px;
    }

    .comment:last-child {
      border-bottom: none;
    }

    .comment .time {
      display: block;
      color: var(--muted);
      font-size: 11px;
    }

    .comment-form {
      display: flex;
      gap: 8px;
      margin-top: 12px;
    }

    .comment-form input {
      flex: 1;
    }

    /* ---------- 12. Profile page ---------- */
    .profile-header {
      display: flex;
      gap: 40px;
      align-items: center;
      padding: 10px 20px 30px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
    }

    .profile-top {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 14px;
    }

    .profile-top h2 {
      font-weight: 400;
      font-size: 24px;
    }

    .stats {
      display: flex;
      gap: 28px;
      margin-bottom: 12px;
    }

    .stats b {
      font-size: 17px;
    }

    .badge {
      display: inline-block;
      font-size: 11px;
      border: 1px solid var(--accent);
      color: var(--accent);
      border-radius: 10px;
      padding: 1px 8px;
      margin-left: 6px;
    }

    .about {
      color: var(--muted);
      font-size: 14px;
      margin-top: 6px;
    }

    .interest {
      display: inline-block;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 2px 10px;
      font-size: 12px;
      margin: 4px 4px 0 0;
    }

    /* 3-column grid of posts (CSS grid) */
    .grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 6px;
    }

    .grid a {
      position: relative;
      display: block;
    }

    .grid img {
      width: 100%;
      aspect-ratio: 1 / 1;
      object-fit: cover;
      display: block;
      border-radius: 4px;
    }

    .grid .mood {
      position: absolute;
      top: 8px;
      left: 8px;
    }

    /* ---------- 13. Search ---------- */
    .search-form {
      display: flex;
      gap: 8px;
      margin-bottom: 20px;
    }

    .search-form input {
      flex: 1;
    }

    .user-row {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 0;
      border-bottom: 1px solid var(--border);
    }

    .user-row .avatar {
      width: 44px;
      height: 44px;
    }

    .user-row .name {
      color: var(--muted);
      font-size: 13px;
    }

    .empty {
      text-align: center;
      color: var(--muted);
      padding: 40px 0;
    }

    /* ---------- 14. Mobile phones (screens under 600px) ---------- */
    @media (max-width: 600px) {
      .nav-inner { flex-direction: column; gap: 8px; }   /* logo on top, links below */
      .nav-links { gap: 12px; }
      .nav-links a { font-size: 13px; white-space: nowrap; }
      .nav-links a.new-post { padding: 4px 10px; }
      .logo { font-size: 20px; }
      .row { flex-direction: column; gap: 0; }
      .profile-header { flex-direction: column; text-align: center; gap: 16px; }
      .profile-top, .stats { justify-content: center; }
      .avatar-big { width: 90px; height: 90px; }
    }
  </style>
</head>

<body>

<!-- ============================================================
     PART B - NAVBAR
     Shown on every page, but only when someone is logged in.
     ============================================================ -->
{% if session.get('user_id') %}
<nav class="navbar">
  <div class="nav-inner">
    <a class="logo" href="{{ url_for('feed') }}">InstaMini</a>
    <div class="nav-links">
      <a href="{{ url_for('feed') }}">Home</a>
      <a href="{{ url_for('search') }}">Search</a>
      <a class="new-post" href="{{ url_for('create_post') }}">+ New Post</a>
      <a href="{{ url_for('profile', username=session.get('username')) }}">Profile</a>
      <a href="{{ url_for('logout') }}">Logout</a>
    </div>
  </div>
</nav>
{% endif %}

<main class="container">

<!-- ============================================================
     PART C - FLASH MESSAGES
     The backend sends these with flash("text", "error") for red
     or flash("text", "success") for green.
     ============================================================ -->
{% with messages = get_flashed_messages(with_categories=true) %}
  {% for category, message in messages %}
    <div class="flash {{ category }}">{{ message }}</div>
  {% endfor %}
{% endwith %}



<!-- ############################################################
     PAGE 1 - LOGIN
     Sends: username, password  (POST to the login route)
     ############################################################ -->
{% if page == 'login' %}
<div class="auth-box">

  <div class="card">
    <span class="logo">InstaMini</span>
    <p class="tagline">Share your moments, share your mood.</p>

    <!-- method="POST" so the password does not appear in the URL -->
    <form method="POST" action="{{ url_for('login') }}">

      <!-- name="username" is what the backend reads: request.form['username'] -->
      <input type="text" name="username" placeholder="Username" required
             value="{{ request.form.get('username', '') }}">

      <br><br>
      <input type="password" name="password" placeholder="Password" required>

      <button type="submit" class="btn btn-full">Log in</button>
    </form>
  </div>

  <div class="card switch-box">
    Don't have an account? <a href="{{ url_for('signup') }}">Sign up</a>
  </div>

</div>



<!-- ############################################################
     PAGE 2 - SIGNUP (detailed registration form)
     Every name="..." matches a column in the users table.
     request.form.get(...) puts back what the user typed if there
     was an error, so they don't have to fill everything again.
     ############################################################ -->
{% elif page == 'signup' %}
<div class="auth-box" style="max-width: 560px;">
  <div class="card">
    <span class="logo">InstaMini</span>
    <p class="tagline">Create your account. Fields marked * are required.</p>

    <!-- enctype="multipart/form-data" is REQUIRED to upload a file (profile picture) -->
    <form method="POST" action="{{ url_for('signup') }}" enctype="multipart/form-data">

      <!-- ----- Section 1: Account Details ----- -->
      <div class="form-section">
        <h3>1. Account Details</h3>

        <label for="username">Username *</label>
        <input type="text" id="username" name="username" required
               placeholder="e.g. ali_raza" value="{{ request.form.get('username', '') }}">
        <span class="hint">Lowercase letters, numbers and _ only. No spaces.</span>

        <label for="email">Email *</label>
        <input type="email" id="email" name="email" required
               placeholder="you@example.com" value="{{ request.form.get('email', '') }}">

        <div class="row">
          <div>
            <label for="password">Password *</label>
            <input type="password" id="password" name="password" required minlength="6">
          </div>
          <div>
            <label for="confirm_password">Confirm Password *</label>
            <input type="password" id="confirm_password" name="confirm_password" required minlength="6">
          </div>
        </div>
        <span class="hint">At least 6 characters.</span>
      </div>

      <!-- ----- Section 2: Personal Information ----- -->
      <div class="form-section">
        <h3>2. Personal Information</h3>

        <label for="full_name">Full Name *</label>
        <input type="text" id="full_name" name="full_name" required
               value="{{ request.form.get('full_name', '') }}">

        <div class="row">
          <div>
            <label for="dob">Date of Birth *</label>
            <input type="date" id="dob" name="dob" required
                   value="{{ request.form.get('dob', '') }}">
          </div>
          <div>
            <label for="phone">Phone Number</label>
            <input type="tel" id="phone" name="phone" placeholder="03001234567"
                   value="{{ request.form.get('phone', '') }}">
          </div>
        </div>

        <label>Gender *</label>
        <div class="choices">
          <!-- radio buttons have the same name, so only ONE can be picked -->
          {% for g in ['Male', 'Female', 'Prefer not to say'] %}
          <label>
            <input type="radio" name="gender" value="{{ g }}" required
                   {% if request.form.get('gender') == g %}checked{% endif %}>
            {{ g }}
          </label>
          {% endfor %}
        </div>
      </div>

      <!-- ----- Section 3: Location & Profile ----- -->
      <div class="form-section">
        <h3>3. Location &amp; Profile</h3>

        <div class="row">
          <div>
            <label for="country">Country</label>
            <select id="country" name="country">
              {% for c in ['Pakistan', 'India', 'Bangladesh', 'Saudi Arabia', 'UAE', 'UK', 'USA', 'Canada', 'Other'] %}
              <option value="{{ c }}" {% if request.form.get('country') == c %}selected{% endif %}>{{ c }}</option>
              {% endfor %}
            </select>
          </div>
          <div>
            <label for="city">City</label>
            <input type="text" id="city" name="city" placeholder="e.g. Islamabad"
                   value="{{ request.form.get('city', '') }}">
          </div>
        </div>

        <label for="profile_pic">Profile Picture (optional)</label>
        <input type="file" id="profile_pic" name="profile_pic" accept="image/*">

        <label for="bio">Bio</label>
        <textarea id="bio" name="bio" maxlength="150"
                  placeholder="Tell people about yourself (max 150 characters)">{{ request.form.get('bio', '') }}</textarea>

        <label>Account Type</label>
        <div class="choices">
          {% for t in ['Personal', 'Creator', 'Business'] %}
          <label>
            <input type="radio" name="account_type" value="{{ t }}"
                   {% if request.form.get('account_type', 'Personal') == t %}checked{% endif %}>
            {{ t }}
          </label>
          {% endfor %}
        </div>
      </div>

      <!-- ----- Section 4: Interests ----- -->
      <div class="form-section">
        <h3>4. Interests</h3>
        <span class="hint">Pick as many as you like.</span>
        <div class="choices" style="margin-top: 8px;">
          <!-- checkboxes with the same name: backend gets a LIST with request.form.getlist('interests') -->
          {% for i in ['Photography', 'Travel', 'Food', 'Sports', 'Tech', 'Art', 'Music', 'Gaming'] %}
          <label>
            <input type="checkbox" name="interests" value="{{ i|lower }}"
                   {% if i|lower in request.form.getlist('interests') %}checked{% endif %}>
            {{ i }}
          </label>
          {% endfor %}
        </div>
      </div>

      <!-- ----- Section 5: Agreement ----- -->
      <div class="form-section">
        <h3>5. Agreement</h3>
        <div class="choices">
          <label>
            <input type="checkbox" name="terms" value="yes" required>
            I agree to the Terms &amp; Conditions *
          </label>
        </div>
      </div>

      <button type="submit" class="btn btn-full">Create Account</button>
    </form>
  </div>

  <div class="card switch-box">
    Already have an account? <a href="{{ url_for('login') }}">Log in</a>
  </div>
</div>



<!-- ############################################################
     PAGE 3 - FEED (home page)
     Backend sends:
       posts        = list from db_get_feed()
       liked_ids    = list of post ids I have liked
       current_mood = the mood filter in use (empty = all)
     ############################################################ -->
{% elif page == 'feed' %}
<div class="narrow">

  <!-- Mood filter (our unique feature). Clicking adds ?mood=Happy to the URL -->
  <div class="mood-filter">
    <a href="{{ url_for('feed') }}" class="{% if not current_mood %}active{% endif %}">All</a>
    <a href="{{ url_for('feed', mood='Happy') }}" class="{% if current_mood == 'Happy' %}active{% endif %}">😊 Happy</a>
    <a href="{{ url_for('feed', mood='Sad') }}"   class="{% if current_mood == 'Sad' %}active{% endif %}">😢 Sad</a>
    <a href="{{ url_for('feed', mood='Hyped') }}" class="{% if current_mood == 'Hyped' %}active{% endif %}">🔥 Hyped</a>
    <a href="{{ url_for('feed', mood='Chill') }}" class="{% if current_mood == 'Chill' %}active{% endif %}">😌 Chill</a>
  </div>

  <!-- One card for every post -->
  {% for post in posts %}
  <div class="card post">

    <!-- top of the card: profile pic, username, mood, date -->
    <div class="post-header">
      <img class="avatar" src="{{ url_for('static', filename='uploads/' + post['profile_pic']) }}" alt="">
      <a class="username" href="{{ url_for('profile', username=post['username']) }}">{{ post['username'] }}</a>
      <span class="mood mood-{{ post['mood']|lower }}">{{ post['mood'] }}</span>
      <span class="time">{{ post['created_at'][:10] }}</span>
    </div>

    <!-- the picture. Clicking it opens the single post page -->
    <a href="{{ url_for('view_post', post_id=post['id']) }}">
      <img class="post-image" src="{{ url_for('static', filename='uploads/' + post['image']) }}" alt="post">
    </a>

    <div class="post-body">
      <div class="post-actions">
        <!-- Like button inside a small form, so it sends a POST -->
        <form method="POST" action="{{ url_for('like', post_id=post['id']) }}">
          {% if post['id'] in liked_ids %}
            <button class="icon-btn liked" title="Unlike">♥</button>
          {% else %}
            <button class="icon-btn" title="Like">♡</button>
          {% endif %}
        </form>
        <a class="icon-btn" href="{{ url_for('view_post', post_id=post['id']) }}" title="Comment">💬</a>
      </div>

      <p class="count">{{ post['like_count'] }} like{% if post['like_count'] != 1 %}s{% endif %}</p>
      <p class="caption"><b>{{ post['username'] }}</b>{{ post['caption'] }}</p>

      {% if post['comment_count'] > 0 %}
        <a class="view-comments" href="{{ url_for('view_post', post_id=post['id']) }}">
          View {{ post['comment_count'] }} comment{% if post['comment_count'] != 1 %}s{% endif %}
        </a>
      {% endif %}
    </div>
  </div>

  {% else %}
  <!-- this part runs when the posts list is EMPTY -->
  <div class="empty">
    <p>No posts here yet.</p>
    <p><a href="{{ url_for('search') }}">Find people to follow</a> or <a href="{{ url_for('create_post') }}">make your first post</a>.</p>
  </div>
  {% endfor %}

</div>



<!-- ############################################################
     PAGE 4 - SINGLE POST (with comments)
     Backend sends:
       post     = from db_get_post()
       comments = list from db_get_comments()
       liked    = True if I liked this post
     ############################################################ -->
{% elif page == 'post' %}
<div class="narrow">

  <div class="card post">
    <div class="post-header">
      <img class="avatar" src="{{ url_for('static', filename='uploads/' + post['profile_pic']) }}" alt="">
      <a class="username" href="{{ url_for('profile', username=post['username']) }}">{{ post['username'] }}</a>
      <span class="mood mood-{{ post['mood']|lower }}">{{ post['mood'] }}</span>
      <span class="time">{{ post['created_at'][:16] }}</span>
    </div>

    <img class="post-image" src="{{ url_for('static', filename='uploads/' + post['image']) }}" alt="post">

    <div class="post-body">
      <div class="post-actions">
        <form method="POST" action="{{ url_for('like', post_id=post['id']) }}">
          {% if liked %}
            <button class="icon-btn liked" title="Unlike">♥</button>
          {% else %}
            <button class="icon-btn" title="Like">♡</button>
          {% endif %}
        </form>

        <!-- Delete button: only shown to the owner of the post -->
        {% if post['user_id'] == session.get('user_id') %}
        <form method="POST" action="{{ url_for('delete_post', post_id=post['id']) }}"
              onsubmit="return confirm('Delete this post?');" style="margin-left: auto;">
          <button class="btn btn-danger btn-small">Delete</button>
        </form>
        {% endif %}
      </div>

      <p class="count">{{ post['like_count'] }} like{% if post['like_count'] != 1 %}s{% endif %}</p>
      <p class="caption"><b>{{ post['username'] }}</b>{{ post['caption'] }}</p>
    </div>
  </div>

  <!-- Comments box -->
  <div class="card">
    <h3 style="font-size: 16px; margin-bottom: 6px;">Comments ({{ comments|length }})</h3>

    {% for c in comments %}
    <div class="comment">
      <img class="avatar" src="{{ url_for('static', filename='uploads/' + c['profile_pic']) }}" alt="">
      <div>
        <a href="{{ url_for('profile', username=c['username']) }}"><b>{{ c['username'] }}</b></a>
        {{ c['text'] }}
        <span class="time">{{ c['created_at'][:16] }}</span>
      </div>
    </div>
    {% else %}
    <p class="hint">No comments yet. Be the first!</p>
    {% endfor %}

    <!-- Add a comment: sends "text" to the comment route -->
    <form class="comment-form" method="POST" action="{{ url_for('comment', post_id=post['id']) }}">
      <input type="text" name="text" placeholder="Add a comment..." required maxlength="300">
      <button type="submit" class="btn btn-small">Post</button>
    </form>
  </div>

</div>



<!-- ############################################################
     PAGE 5 - CREATE POST
     Sends: image (file), caption, mood  (POST to create_post)
     ############################################################ -->
{% elif page == 'create_post' %}
<div class="narrow">
  <div class="card">
    <h2 style="margin-bottom: 10px;">Create a new post</h2>

    <!-- enctype="multipart/form-data" is needed because we upload a picture -->
    <form method="POST" action="{{ url_for('create_post') }}" enctype="multipart/form-data">

      <label for="image">Picture *</label>
      <input type="file" id="image" name="image" accept="image/*" required>

      <label for="caption">Caption</label>
      <textarea id="caption" name="caption" maxlength="300"
                placeholder="Write a caption...">{{ request.form.get('caption', '') }}</textarea>

      <!-- Our unique feature: every post has a mood -->
      <label>How are you feeling? *</label>
      <div class="choices">
        {% for m, emoji in [('Happy', '😊'), ('Sad', '😢'), ('Hyped', '🔥'), ('Chill', '😌')] %}
        <label>
          <input type="radio" name="mood" value="{{ m }}" required
                 {% if request.form.get('mood', 'Happy') == m %}checked{% endif %}>
          {{ emoji }} {{ m }}
        </label>
        {% endfor %}
      </div>

      <button type="submit" class="btn btn-full">Share</button>
    </form>
  </div>
</div>



<!-- ############################################################
     PAGE 6 - PROFILE
     Backend sends:
       user         = from db_get_user_by_username()
       posts        = list from db_get_user_posts()
       post_count, followers, following = numbers
       is_me        = True if this is my own profile
       is_following = True if I already follow this person
     ############################################################ -->
{% elif page == 'profile' %}

<div class="profile-header">
  <img class="avatar-big" src="{{ url_for('static', filename='uploads/' + user['profile_pic']) }}" alt="">

  <div>
    <div class="profile-top">
      <h2>{{ user['username'] }}</h2>

      <!-- my own profile: Edit button. Someone else: Follow / Unfollow -->
      {% if is_me %}
        <a class="btn btn-outline btn-small" href="{{ url_for('edit_profile') }}">Edit Profile</a>
      {% elif is_following %}
        <form method="POST" action="{{ url_for('unfollow', user_id=user['id']) }}">
          <button class="btn btn-outline btn-small">Unfollow</button>
        </form>
      {% else %}
        <form method="POST" action="{{ url_for('follow', user_id=user['id']) }}">
          <button class="btn btn-small">Follow</button>
        </form>
      {% endif %}
    </div>

    <div class="stats">
      <span><b>{{ post_count }}</b> posts</span>
      <span><b>{{ followers }}</b> followers</span>
      <span><b>{{ following }}</b> following</span>
    </div>

    <p><b>{{ user['full_name'] }}</b><span class="badge">{{ user['account_type'] }}</span></p>
    {% if user['bio'] %}<p>{{ user['bio'] }}</p>{% endif %}

    <!-- "About" built from the signup details -->
    <p class="about">
      {% if user['city'] %}📍 {{ user['city'] }}{% if user['country'] %}, {{ user['country'] }}{% endif %}{% endif %}
    </p>
    {% if user['interests'] %}
      <div>
        <!-- interests are saved like "travel,food"; split(',') turns it into a list -->
        {% for i in user['interests'].split(',') %}
          <span class="interest">{{ i|capitalize }}</span>
        {% endfor %}
      </div>
    {% endif %}
  </div>
</div>

<!-- 3-column grid of the user's posts -->
<div class="grid">
  {% for post in posts %}
    <a href="{{ url_for('view_post', post_id=post['id']) }}">
      <img src="{{ url_for('static', filename='uploads/' + post['image']) }}" alt="post">
      <span class="mood mood-{{ post['mood']|lower }}">{{ post['mood'] }}</span>
    </a>
  {% endfor %}
</div>

{% if not posts %}
  <div class="empty">No posts yet.</div>
{% endif %}



<!-- ############################################################
     PAGE 7 - EDIT PROFILE
     Backend sends: user (the logged-in user)
     The form is pre-filled with the current values.
     ############################################################ -->
{% elif page == 'edit_profile' %}
<div class="narrow">
  <div class="card">
    <h2 style="margin-bottom: 10px;">Edit Profile</h2>

    <form method="POST" action="{{ url_for('edit_profile') }}" enctype="multipart/form-data">

      <div style="text-align: center; margin-bottom: 8px;">
        <img class="avatar-big" src="{{ url_for('static', filename='uploads/' + user['profile_pic']) }}" alt="">
      </div>

      <label for="profile_pic">Change Profile Picture</label>
      <input type="file" id="profile_pic" name="profile_pic" accept="image/*">

      <label for="full_name">Full Name</label>
      <input type="text" id="full_name" name="full_name" required value="{{ user['full_name'] }}">

      <label for="bio">Bio</label>
      <textarea id="bio" name="bio" maxlength="150">{{ user['bio'] }}</textarea>

      <div class="row">
        <div>
          <label for="city">City</label>
          <input type="text" id="city" name="city" value="{{ user['city'] or '' }}">
        </div>
        <div>
          <label for="country">Country</label>
          <select id="country" name="country">
            {% for c in ['Pakistan', 'India', 'Bangladesh', 'Saudi Arabia', 'UAE', 'UK', 'USA', 'Canada', 'Other'] %}
            <option value="{{ c }}" {% if user['country'] == c %}selected{% endif %}>{{ c }}</option>
            {% endfor %}
          </select>
        </div>
      </div>

      <label>Account Type</label>
      <div class="choices">
        {% for t in ['Personal', 'Creator', 'Business'] %}
        <label>
          <input type="radio" name="account_type" value="{{ t }}"
                 {% if user['account_type'] == t %}checked{% endif %}>
          {{ t }}
        </label>
        {% endfor %}
      </div>

      <label>Interests</label>
      <div class="choices">
        {% set my_interests = (user['interests'] or '').split(',') %}
        {% for i in ['Photography', 'Travel', 'Food', 'Sports', 'Tech', 'Art', 'Music', 'Gaming'] %}
        <label>
          <input type="checkbox" name="interests" value="{{ i|lower }}"
                 {% if i|lower in my_interests %}checked{% endif %}>
          {{ i }}
        </label>
        {% endfor %}
      </div>

      <button type="submit" class="btn btn-full">Save Changes</button>
      <a class="btn btn-outline btn-full" style="text-align: center;"
         href="{{ url_for('profile', username=user['username']) }}">Cancel</a>
    </form>
  </div>
</div>



<!-- ############################################################
     PAGE 8 - SEARCH
     method="GET": the search text appears in the URL (/search?q=ali)
     Backend sends:
       q     = what the user typed
       users = list from db_search_users(q)
     ############################################################ -->
{% elif page == 'search' %}
<div class="narrow">

  <form class="search-form" method="GET" action="{{ url_for('search') }}">
    <input type="search" name="q" placeholder="Search by username or name..." value="{{ q or '' }}" autofocus>
    <button type="submit" class="btn">Search</button>
  </form>

  {% if q %}
    <div class="card">
      {% for u in users %}
      <div class="user-row">
        <img class="avatar" src="{{ url_for('static', filename='uploads/' + u['profile_pic']) }}" alt="">
        <div>
          <a href="{{ url_for('profile', username=u['username']) }}"><b>{{ u['username'] }}</b></a>
          <div class="name">{{ u['full_name'] }}</div>
        </div>
      </div>
      {% else %}
      <p class="empty">No users found for "{{ q }}".</p>
      {% endfor %}
    </div>
  {% endif %}

</div>

{% endif %}
<!-- ============================ END OF PAGES ============================ -->

</main>

</body>
</html>
'''


# ##################################################################
#   Create the Flask app
# ##################################################################
app = Flask(__name__)

# The secret key signs the session cookie, so nobody can
# change their user_id and pretend to be someone else.
app.secret_key = "instamini-secret-key-2026"

# Don't accept uploads bigger than 5 MB
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

# Tell Flask that "index.html" means the PAGE_HTML text above
app.jinja_loader = DictLoader({"index.html": PAGE_HTML})


# ##################################################################
# ##################################################################
#
#   PERSON C - BACKEND 1: AUTH & USERS
#   C0 - Helpers (login_required, save_image)
#   C1 - Signup   C2 - Login   C3 - Logout   C4 - Profile
#   C5 - Edit Profile   C6 - Follow / Unfollow   C7 - Search
#
# ##################################################################
# ##################################################################

# ==================================================================
#  C0 - HELPERS (used by Person C and Person D)
# ==================================================================

# The interest checkboxes on the signup form (must match the HTML)
INTERESTS = ["photography", "travel", "food", "sports", "tech", "art", "music", "gaming"]

# Only these picture types can be uploaded
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def login_required(route_function):
    """
    A decorator: put @login_required above a route.
    Before the route runs, it checks if someone is logged in.
    If not, it sends them to the login page instead.
    """
    @wraps(route_function)          # keeps the original function's name (Flask needs it)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return route_function(*args, **kwargs)
    return wrapper


def save_image(file):
    """
    Save an uploaded picture into static/uploads/.
    Returns the new file name, or None if no valid picture was given.
    """
    if file is None or file.filename == "":
        return None                                   # no file chosen

    if "." not in file.filename:
        return None
    extension = file.filename.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        return None                                   # not a picture (e.g. .exe)

    # Give the picture a brand-new random name, keeping only its type.
    # Example: "my photo.JPG"  ->  "3f9a1c2b7d4e.jpg"
    # uuid makes the name unique, so two "pic.jpg" files never overwrite each other.
    filename = uuid.uuid4().hex[:12] + "." + extension

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    return filename


# ============================================================
#  C1 - SIGNUP
#  GET  -> show the empty registration form
#  POST -> check every field, save the user, go to login
# ============================================================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    # Already logged in? No need to sign up again.
    if "user_id" in session:
        return redirect(url_for("feed"))

    # Just opening the page (GET): show the form
    if request.method == "GET":
        return render_template("index.html", page="signup")

    # ---- The form was submitted (POST): read every field ----
    # .get(..., "") gives "" instead of crashing if a field is missing
    # .strip() removes spaces at the start and end
    username = request.form.get("username", "").strip().lower()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    full_name = request.form.get("full_name", "").strip()
    dob = request.form.get("dob", "")
    phone = request.form.get("phone", "").strip()
    gender = request.form.get("gender", "")
    country = request.form.get("country", "")
    city = request.form.get("city", "").strip()
    bio = request.form.get("bio", "").strip()
    account_type = request.form.get("account_type", "Personal")
    terms = request.form.get("terms")

    # Checkboxes: getlist gives a LIST of everything ticked, e.g. ['travel', 'food']
    interests_list = request.form.getlist("interests")
    # keep only real options, then join into one string: "travel,food"
    interests = ",".join(i for i in interests_list if i in INTERESTS)

    # ---- Validation: collect every mistake in a list ----
    errors = []

    if not username or not email or not password or not full_name or not dob or not gender:
        errors.append("Please fill in all required fields (marked *).")

    # username: only lowercase letters, numbers and _
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789_"
    if username and not all(ch in allowed for ch in username):
        errors.append("Username can only have letters, numbers and _ (no spaces).")
    if username and (len(username) < 3 or len(username) > 20):
        errors.append("Username must be 3 to 20 characters.")

    if email and ("@" not in email or "." not in email):
        errors.append("Please enter a valid email address.")
 
    if len(password) < 6:
        errors.append("Password must be at least 6 characters.")
    if password != confirm_password:
        errors.append("Passwords do not match.")
 
    if phone and not phone.isdigit():
        errors.append("Phone number can only contain digits.")
 
    # age must be 13 or more
    if dob:
        try:
            birth = datetime.strptime(dob, "%Y-%m-%d").date()
            today = date.today()
            # subtract 1 if the birthday hasn't come yet this year
            age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
            if age < 13:
                errors.append("You must be at least 13 years old to sign up.")
        except ValueError:
            errors.append("Please enter a valid date of birth.")
 
    if gender and gender not in ["Male", "Female", "Prefer not to say"]:
        errors.append("Please choose a gender option.")
 
    if account_type not in ["Personal", "Creator", "Business"]:
        account_type = "Personal"
 
    if not terms:
        errors.append("You must agree to the Terms & Conditions.")
 
    # Ask Person A's functions if the username / email is already used
    if username and db_get_user_by_username(username):
        errors.append("That username is already taken.")
    if email and db_get_user_by_email(email):
        errors.append("An account with this email already exists.")
 
    # Any mistakes? Show the form again with red messages.
    # (index.html refills what the user typed, using request.form)
    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("index.html", page="signup")
 
    # ---- Everything is fine: save the user ----
    # Profile picture is optional. If none, use the default picture.
    profile_pic = save_image(request.files.get("profile_pic")) or "default.svg"
 
    # NEVER save the real password. Save its hash instead.
    password_hash = generate_password_hash(password)
 
    db_create_user(full_name, username, email, password_hash, dob, gender,
                   phone, city, country, bio, profile_pic, account_type, interests)
 
    flash("Account created! You can log in now.", "success")
    return redirect(url_for("login"))
 
 
# ============================================================
#  C2 - LOGIN
#  GET  -> show the login form
#  POST -> check username + password, then remember the user in the session
# ============================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("feed"))
 
    if request.method == "GET":
        return render_template("index.html", page="login")
 
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")
 
    user = db_get_user_by_username(username)
 
    # check_password_hash compares the typed password with the saved hash.
    # We show the SAME message for "no such user" and "wrong password",
    # so attackers can't find out which usernames exist.
    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Wrong username or password.", "error")
        return render_template("index.html", page="login")
 
    # Login successful: the session remembers who is logged in,
    # page after page, until logout.
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]     # the navbar uses this
 
    flash("Welcome back, " + user["full_name"] + "!", "success")
    return redirect(url_for("feed"))
 
 
# ============================================================
#  C3 - LOGOUT
# ============================================================
@app.route("/logout")
def logout():
    session.clear()           # forget who was logged in
    flash("You have logged out.", "success")
    return redirect(url_for("login"))
 
 
# ============================================================
#  C4 - PROFILE
#  Shows any user's profile: /profile/ali, /profile/sara ...
# ============================================================
@app.route("/profile/<username>")
@login_required
def profile(username):
    user = db_get_user_by_username(username)
 
    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("feed"))
 
    my_id = session["user_id"]
 
    # Send everything the profile section of index.html needs
    return render_template(
        "index.html",
        page="profile",
        user=user,
        posts=db_get_user_posts(user["id"]),
        post_count=db_count_posts(user["id"]),
        followers=db_count_followers(user["id"]),
        following=db_count_following(user["id"]),
        is_me=(user["id"] == my_id),
        is_following=db_is_following(my_id, user["id"]),
    )
 
 
# ============================================================
#  C5 - EDIT PROFILE
#  GET  -> show the form filled with current details
#  POST -> save the changes
# ============================================================
@app.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    user = db_get_user_by_id(session["user_id"])
 
    if request.method == "GET":
        return render_template("index.html", page="edit_profile", user=user)
 
    full_name = request.form.get("full_name", "").strip()
    bio = request.form.get("bio", "").strip()[:150]      # [:150] = max 150 characters
    city = request.form.get("city", "").strip()
    country = request.form.get("country", "")
    account_type = request.form.get("account_type", "Personal")
    interests = ",".join(i for i in request.form.getlist("interests") if i in INTERESTS)
 
    if not full_name:
        flash("Full name cannot be empty.", "error")
        return render_template("index.html", page="edit_profile", user=user)
 
    if account_type not in ["Personal", "Creator", "Business"]:
        account_type = "Personal"
 
    # New picture uploaded? Use it. Otherwise keep the old one.
    new_pic = save_image(request.files.get("profile_pic"))
    profile_pic = new_pic or user["profile_pic"]
 
    db_update_profile(user["id"], full_name, bio, city, country,
                      profile_pic, account_type, interests)
 
    flash("Profile updated!", "success")
    return redirect(url_for("profile", username=user["username"]))
 
 
# ============================================================
#  C6 - FOLLOW / UNFOLLOW
#  These use POST because they CHANGE data.
# ============================================================
@app.route("/follow/<int:user_id>", methods=["POST"])
@login_required
def follow(user_id):
    other = db_get_user_by_id(user_id)
    if other is None:
        flash("User not found.", "error")
        return redirect(url_for("feed"))
 
    db_follow(session["user_id"], user_id)    # db_follow ignores following yourself
    flash("You are now following " + other["username"] + ".", "success")
    return redirect(url_for("profile", username=other["username"]))
 
 
@app.route("/unfollow/<int:user_id>", methods=["POST"])
@login_required
def unfollow(user_id):
    other = db_get_user_by_id(user_id)
    if other is None:
        flash("User not found.", "error")
        return redirect(url_for("feed"))
 
    db_unfollow(session["user_id"], user_id)
    flash("You unfollowed " + other["username"] + ".", "success")
    return redirect(url_for("profile", username=other["username"]))
 
 
# ============================================================
#  C7 - SEARCH
#  /search?q=ali   (GET, the search text comes from the URL)
# ============================================================
@app.route("/search")
@login_required
def search():
    q = request.args.get("q", "").strip()     # request.args = values in the URL
    users = db_search_users(q) if q else []   # only search if something was typed
    return render_template("index.html", page="search", q=q, users=users)
 
 
# ##################################################################
# ##################################################################
#
#   PERSON D - BACKEND 2: POSTS & INTERACTIONS
#   D1 - Feed   D2 - Create Post   D3 - View Post
#   D4 - Like / Unlike   D5 - Comment   D6 - Delete Post
#
# ##################################################################
# ##################################################################
 
# The 4 moods of our unique feature
MOODS = ["Happy", "Sad", "Hyped", "Chill"]
 
 
# ========================================================
#  D1 - FEED (home page)
#  Shows my posts + posts of people I follow, newest first.
#  /?mood=Happy shows only Happy posts.
# ========================================================
@app.route("/")
@login_required
def feed():
    my_id = session["user_id"]
 
    # mood from the URL, e.g. /?mood=Happy  (None if not given)
    mood = request.args.get("mood")
    if mood not in MOODS:
        mood = None          # ignore anything that isn't a real mood
 
    posts = db_get_feed(my_id, mood)
    liked_ids = db_get_liked_post_ids(my_id)   # to show red hearts
 
    return render_template("index.html", page="feed",
                           posts=posts, liked_ids=liked_ids, current_mood=mood)
 
 
# ========================================================
#  D2 - CREATE A POST
#  GET  -> show the form
#  POST -> save the picture and the post
# ========================================================
@app.route("/create_post", methods=["GET", "POST"])
@login_required
def create_post():
    if request.method == "GET":
        return render_template("index.html", page="create_post")
 
    caption = request.form.get("caption", "").strip()[:300]   # max 300 characters
    mood = request.form.get("mood", "Happy")
    if mood not in MOODS:
        mood = "Happy"
 
    # save_image returns the new file name, or None if no valid picture
    image = save_image(request.files.get("image"))
    if image is None:
        flash("Please choose a picture (png, jpg, jpeg, gif or webp).", "error")
        return render_template("index.html", page="create_post")
 
    db_create_post(session["user_id"], image, caption, mood)
 
    flash("Post shared!", "success")
    return redirect(url_for("feed"))
 
 
# ========================================================
#  D3 - VIEW ONE POST (with its comments)
# ========================================================
@app.route("/post/<int:post_id>")
@login_required
def view_post(post_id):
    post = db_get_post(post_id)
    if post is None:
        flash("Post not found.", "error")
        return redirect(url_for("feed"))
 
    return render_template("index.html", page="post",
                           post=post,
                           comments=db_get_comments(post_id),
                           liked=db_has_liked(session["user_id"], post_id))
 
 
# ========================================================
#  D4 - LIKE / UNLIKE  (one button does both = "toggle")
#  Already liked -> unlike.  Not liked -> like.
# ========================================================
@app.route("/like/<int:post_id>", methods=["POST"])
@login_required
def like(post_id):
    my_id = session["user_id"]
 
    if db_get_post(post_id) is None:
        flash("Post not found.", "error")
        return redirect(url_for("feed"))
 
    if db_has_liked(my_id, post_id):
        db_unlike_post(my_id, post_id)
    else:
        db_like_post(my_id, post_id)
 
    # go back to the page the user clicked from (feed or post page)
    return redirect(request.referrer or url_for("feed"))
 
 
# ========================================================
#  D5 - COMMENT
# ========================================================
@app.route("/comment/<int:post_id>", methods=["POST"])
@login_required
def comment(post_id):
    text = request.form.get("text", "").strip()[:300]
 
    if db_get_post(post_id) is None:
        flash("Post not found.", "error")
        return redirect(url_for("feed"))
 
    if text == "":
        flash("Comment cannot be empty.", "error")
    else:
        db_add_comment(session["user_id"], post_id, text)
 
    return redirect(url_for("view_post", post_id=post_id))
 
 
# ========================================================
#  D6 - DELETE A POST (only your own)
# ========================================================
@app.route("/delete_post/<int:post_id>", methods=["POST"])
@login_required
def delete_post(post_id):
    post = db_get_post(post_id)
 
    # Stop user A from deleting user B's post
    if post is None or post["user_id"] != session["user_id"]:
        flash("You can only delete your own posts.", "error")
        return redirect(url_for("feed"))
 
    db_delete_post(post_id, session["user_id"])   # likes + comments go too (CASCADE)
 
    # also delete the picture file, so the uploads folder doesn't fill up
    image_path = os.path.join(UPLOAD_FOLDER, post["image"])
    if os.path.exists(image_path):
        os.remove(image_path)
 
    flash("Post deleted.", "success")
    return redirect(url_for("profile", username=session["username"]))
 
 
# ##################################################################
#   START THE APP
#   Runs only when you do:  python instamini.py
# ##################################################################
if __name__ == "__main__":
    # First run: create the pictures and the database with fake data
    if not os.path.exists(os.path.join(UPLOAD_FOLDER, "default.svg")):
        make_fake_pictures()
    if not os.path.exists(DATABASE):
        seed_database()
        print("Database created with fake data. Log in as ali / 123456")
 
    # debug=True: shows errors in the browser and restarts when you save the file
    app.run(debug=True)
 