from flask import Flask, jsonify
from flask_cors import CORS
import requests, os, datetime

app = Flask(__name__)
CORS(app)

SUBREDDITS = ["france", "emploi", "travail", "poleemploi", "formation"]
KEYWORDS = ["reconversion professionnelle", "burn-out", "burnout", "souffrance au travail", "changer de metier", "rupture conventionnelle", "bilan de competences", "plus de sens au travail", "demission CDI", "licenciement reconversion", "mal au travail"]
VALIDATION_WORDS = ["travail", "emploi", "poste", "reconversion", "formation", "metier", "bilan", "cpf", "burn", "licenci", "demission", "rupture", "salaire", "carriere", "professionnel", "entreprise", "manager", "collegue", "patron"]
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
YOUTUBE_QUERIES = ["reconversion professionnelle temoignage", "burn out travail temoignage", "bilan de competences CPF avis", "changer de metier temoignage"]

def get_reddit_posts():
    results = []
    headers = {"User-Agent": "VeilleReconversion/1.0"}
    subs = "+".join(SUBREDDITS)
    for kw in KEYWORDS:
        url = "https://www.reddit.com/r/{}/search.json?q={}&restrict_sr=1&sort=new&limit=10&t=month".format(subs, requests.utils.quote(kw))
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                for p in r.json().get("data", {}).get("children", []):
                    d = p["data"]
                    text = d.get("selftext", "")
                    title = d.get("title", "")
                    if len(text) < 80: continue
                    if not any(w in (title+" "+text).lower() for w in VALIDATION_WORDS): continue
                    results.append({"id": "reddit_"+d.get("id",""), "author": d.get("author"), "subreddit": d.get("subreddit"), "title": title, "text": text[:500], "score": d.get("score", 0), "comments": d.get("num_comments", 0), "url": "https://reddit.com"+d.get("permalink", ""), "date": d.get("created_utc"), "keyword": kw, "source": "Reddit"})
        except Exception as e:
            print("Reddit erreur", kw, e)
    return results

def get_youtube_comments():
    if not YOUTUBE_API_KEY: return []
    results = []
    for query in YOUTUBE_QUERIES:
        try:
            r = requests.get("https://www.googleapis.com/youtube/v3/search", params={"part":"snippet","q":query,"type":"video","order":"date","maxResults":5,"relevanceLanguage":"fr","regionCode":"FR","key":YOUTUBE_API_KEY}, timeout=10)
            if r.status_code != 200: continue
            for video in r.json().get("items", []):
                vid = video["id"].get("videoId")
                vtitle = video["snippet"].get("title", "")
                if not vid: continue
                rc = requests.get("https://www.googleapis.com/youtube/v3/commentThreads", params={"part":"snippet","videoId":vid,"order":"relevance","maxResults":20,"key":YOUTUBE_API_KEY}, timeout=10)
                if rc.status_code != 200: continue
                for c in rc.json().get("items", []):
                    sn = c["snippet"]["topLevelComment"]["snippet"]
                    text = sn.get("textDisplay", "")
                    if len(text) < 80: continue
                    if not any(w in text.lower() for w in VALIDATION_WORDS): continue
                    try: ts = datetime.datetime.strptime(sn.get("publishedAt","")[:19], "%Y-%m-%dT%H:%M:%S").timestamp()
                    except: ts = 0
                    results.append({"id": "yt_"+c.get("id",""), "author": sn.get("authorDisplayName", "Anonyme"), "subreddit": "YouTube", "title": "Commentaire : "+vtitle[:80], "text": text[:500], "score": sn.get("likeCount", 0), "comments": 0, "url": "https://www.youtube.com/watch?v="+vid, "date": ts, "keyword": query, "source": "YouTube"})
        except Exception as e:
            print("YouTube erreur", query, e)
    return results

@app.route("/")
def index():
    with open("dashboard.html", "r", encoding="utf-8") as f: return f.read()

@app.route("/search")
def search():
    results = get_reddit_posts() + get_youtube_comments()
    seen = set()
    unique = [item for item in results if not (item["id"] in seen or seen.add(item["id"]))]
    unique.sort(key=lambda x: x.get("date", 0), reverse=True)
    return jsonify({"posts": unique, "total": len(unique)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=False)
