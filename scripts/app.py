import os
import secrets
from datetime import datetime, timedelta
from flask import (
    Flask, render_template_string, request, redirect, url_for, session, abort
)
from db import get_week_articles, save_session, session_done, get_session_selections, init_db, load_historical
from ranker import rank

init_db()
_HISTORICAL_CSV = os.environ.get("HISTORICAL_CSV", "model/data/asreview_labels.csv")
if os.path.exists(_HISTORICAL_CSV):
    load_historical(_HISTORICAL_CSV)

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("HTTPS", "false").lower() == "true"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
ACCESS_TOKEN = os.environ["ACCESS_TOKEN"]
WEEKLY_JOB_TOKEN = os.environ["WEEKLY_JOB_TOKEN"]

TEMPLATE = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>Publications &mdash; {{ date }}</title>
<style>
* { box-sizing: border-box; }
body { font-family: sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1.5rem; color: #111; }
h1 { font-size: 1.4rem; margin-bottom: 0.2rem; }
.subtitle { color: #6b7280; font-size: 0.9rem; margin-bottom: 1.5rem; }
.article { padding: 1rem; margin: 0.6rem 0; border: 1px solid #e5e7eb; border-radius: 6px; display: flex; gap: 0.75rem; align-items: flex-start; }
.article.checked { border-color: #2563eb; background: #eff6ff; }
input[type=checkbox] { width: 18px; height: 18px; flex-shrink: 0; margin-top: 3px; cursor: pointer; }
.body { flex: 1; min-width: 0; }
.title { font-weight: 600; font-size: 0.97rem; line-height: 1.4; }
.meta { color: #6b7280; font-size: 0.8rem; margin-top: 0.2rem; }
.meta a { color: #2563eb; }
.abstract { color: #374151; font-size: 0.86rem; margin-top: 0.45rem; line-height: 1.5; }
.score { color: #9ca3af; font-size: 0.75rem; white-space: nowrap; padding-top: 3px; }
.bar { position: sticky; bottom: 0; background: white; border-top: 1px solid #e5e7eb; padding: 0.9rem 0; margin-top: 1rem; display: flex; align-items: center; gap: 1rem; }
button { background: #2563eb; color: white; padding: 0.55rem 1.5rem; border: none; border-radius: 4px; font-size: 0.95rem; cursor: pointer; }
button:hover { background: #1d4ed8; }
.hint { color: #6b7280; font-size: 0.82rem; }
.done-banner { background: #dcfce7; border: 1px solid #bbf7d0; padding: 0.7rem 1rem; border-radius: 4px; margin-bottom: 1rem; font-size: 0.9rem; }
</style>
</head>
<body>
<h1>Publications &mdash; {{ date }}</h1>
<p class="subtitle">
  {{ ranked|length }} publications
  {%- if ranked and ranked[0][1] is not none %} &mdash; ranked by predicted relevance{% endif %}
</p>
{% if done %}
<div class="done-banner">
  Selections saved. A summary email with your selected articles and a Zotero RIS file has been sent.
</div>
{% endif %}
<form method="post" action="/week/{{ date }}/select">
<input type="hidden" name="csrf_token" value="{{ csrf_token }}">
{% for article, score in ranked %}
<div class="article{% if article.id in selected_ids %} checked{% endif %}">
  <input type="checkbox" name="selected" value="{{ article.id }}"
    {% if article.id in selected_ids %}checked{% endif %}
    {% if done %}disabled{% endif %}>
  <div class="body">
    <div class="title">{{ article.title }}</div>
    <div class="meta">
      {{ article.journal_name }}
      {% if article.authors %} &nbsp;|&nbsp; {{ article.authors }}{% endif %}
    </div>
    <div class="meta">
      <a href="https://doi.org/{{ article.doi }}" target="_blank">doi.org/{{ article.doi }}</a>
    </div>
    {% if article.abstract %}
    <div class="abstract">
      {{ article.abstract[:400] }}{% if article.abstract|length > 400 %}&hellip;{% endif %}
    </div>
    {% endif %}
  </div>
  {% if score is not none %}
  <div class="score">{{ "%.0f"|format(score * 100) }}%</div>
  {% endif %}
</div>
{% endfor %}
{% if not done %}
<div class="bar">
  <button type="submit">Save Selections</button>
  <span class="hint">Check articles you want to read or engage with.</span>
</div>
{% endif %}
</form>
</body></html>"""


@app.before_request
def require_auth():
    if request.endpoint in ("static", "run_weekly", "healthz"):
        return
    if session.get("authed"):
        return
    token = request.args.get("token") or request.form.get("token")
    if token and secrets.compare_digest(token, ACCESS_TOKEN):
        session["authed"] = True
        session["csrf_token"] = secrets.token_hex(16)
        return
    abort(401)


@app.route("/healthz")
def healthz():
    return "ok", 200


@app.route("/")
def index():
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    return redirect(url_for("week", date=monday.strftime("%Y-%m-%d")))


@app.route("/week/<date>")
def week(date):
    articles = get_week_articles(date)
    if not articles:
        return f"<p>No articles found for week of {date}.</p>", 404
    ranked = rank(articles)
    done = session_done(date)
    selected_ids = get_session_selections(date) if done else set()
    csrf_token = session.setdefault("csrf_token", secrets.token_hex(16))
    return render_template_string(
        TEMPLATE, ranked=ranked, date=date, done=done,
        selected_ids=selected_ids, csrf_token=csrf_token
    )


@app.route("/week/<date>/select", methods=["POST"])
def select(date):
    if session.get("csrf_token") != request.form.get("csrf_token"):
        abort(403)
    if session_done(date):
        return redirect(url_for("week", date=date))

    articles = get_week_articles(date)
    all_ids = [a["id"] for a in articles]
    selected_ids = request.form.getlist("selected")
    save_session(date, selected_ids, all_ids)

    selected_set = set(str(i) for i in selected_ids)
    selected_articles = [a for a in articles if str(a["id"]) in selected_set]
    try:
        from emailer import send_selection_email
        send_selection_email(date, selected_articles)
    except Exception as e:
        print(f"Selection email failed: {e}")

    return redirect(url_for("week", date=date))


@app.route("/internal/run-weekly", methods=["POST", "GET"])
def run_weekly():
    token = request.args.get("token", "")
    if not secrets.compare_digest(token, WEEKLY_JOB_TOKEN):
        abort(401)
    from weekly_job import run
    try:
        run()
    except Exception as e:
        print(f"Weekly job failed: {e}")
        return f"error: {e}", 500
    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
