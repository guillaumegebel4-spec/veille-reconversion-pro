from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

SUBREDDITS = ["france", "emploi", "travail"]
KEYWORDS = [
    "reconversion professionnelle",
    "burn-out",
    "souffrance au travail",
    "changer de metier",
    "rupture conventionnelle",
    "bilan de competences",
    "plus de sens au travail"
]

@app.route('/')
def index():
    with open('dashboard.html', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/search')
def search():
    results = []
    headers = {"User-Agent": "VeilleReconversion/1.0"}
    subs = "+".join(SUBREDDITS)
    for kw in KEYWORDS:
        url = "https://www.reddit.com/r/{}/search.json?q={}&restrict_sr=1&sort=new&limit=10&t=month".format(subs, requests.utils.quote(kw))
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                posts = r.json().get("data", {}).get("children", [])
                for p in posts:
                    d = p["data"]
                    text = d.get("selftext", "")
                    if len(text) > 80:
                        results.append({"id": d.get("id"), "author": d.get("author"), "subreddit": d.get("subreddit"), "title": d.get("title"), "text": text[:500], "score": d.get("score", 0), "comments": d.get("num_comments", 0), "url": "https://reddit.com" + d.get("permalink", ""), "date": d.get("created_utc"), "keyword": kw})
        except Exception as e:
            print("Erreur {}: {}".format(kw, e))
    seen = set()
    unique = []
    for item in results:
        if item["id"] not in seen:
            seen.add(item["id"])
            unique.append(item)
    return jsonify({"posts": unique, "total": len(unique)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
