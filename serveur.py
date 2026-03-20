from flask import Flask, jsonify
from flask_cors import CORS
import requests, os, datetime, threading, time

app = Flask(__name__)
CORS(app)

SUBREDDITS = ["france", "emploi", "travail", "poleemploi", "formation"]
KEYWORDS = ["reconversion professionnelle", "burn-out", "burnout", "souffrance au travail", "changer de metier", "rupture conventionnelle", "bilan de competences", "plus de sens au travail", "demission CDI", "licenciement reconversion", "mal au travail"]
VALIDATION_WORDS = ["travail", "emploi", "poste", "reconversion", "formation", "metier", "bilan", "cpf", "burn", "licenci", "demission", "rupture", "salaire", "carriere", "professionnel", "entreprise", "manager", "collegue", "patron"]
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
YOUTUBE_QUERIES = ["reconversion professionnelle temoignage", "burn out travail temoignage", "bilan de competences CPF avis", "changer de metier temoignage"]
GOOGLE_ALERTS_RSS = [
    "https://www.google.fr/alerts/feeds/05258671954159722660/14179317318011172716",
    "https://www.google.fr/alerts/feeds/05258671954159722660/4236035930240063314",
    "https://www.google.fr/alerts/feeds/05258671954159722660/17234795094043658117",
    "https://www.google.fr/alerts/feeds/05258671954159722660/11065484875611424753",
    "https://www.google.fr/alerts/feeds/05258671954159722660/5243583938657747172"
]

# Cache pour eviter les timeouts
_cache = {"posts": [], "updated": 0}

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

def get_google_alerts():
    results = []
    headers = {"User-Agent": "VeilleReconversion/1.0"}
    for feed_url in GOOGLE_ALERTS_RSS:
        try:
            r = requests.get(feed_url, headers=headers, timeout=10)
            if r.status_code != 200: continue
            import xml.etree.ElementTree as ET
            root = ET.fromstring(r.content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns):
                title = entry.findtext("atom:title", "", ns)
                link = entry.find("atom:link", ns)
                url = link.get("href", "") if link is not None else ""
                summary = entry.findtext("atom:summary", "", ns)
                published = entry.findtext("atom:published", "", ns)
                entry_id = entry.findtext("atom:id", "", ns)
                if not any(w in (title+" "+summary).lower() for w in VALIDATION_WORDS): continue
                try: ts = datetime.datetime.strptime(published[:19], "%Y-%m-%dT%H:%M:%S").timestamp()
                except: ts = 0
                results.append({"id": "ga_"+str(hash(entry_id))[-10:], "author": "Google Alerts", "subreddit": "Web", "title": title, "text": summary[:500], "score": 0, "comments": 0, "url": url, "date": ts, "keyword": "Google Alert", "source": "Google"})
        except Exception as e:
            print("Google Alerts erreur", e)
    return results

def refresh_cache():
    global _cache
    results = get_reddit_posts() + get_youtube_comments() + get_google_alerts()
    seen = set()
    unique = [item for item in results if not (item["id"] in seen or seen.add(item["id"]))]
    unique.sort(key=lambda x: x.get("date", 0), reverse=True)
    _cache = {"posts": unique, "updated": time.time()}
    print("Cache updated:", len(unique), "posts")

def background_refresh():
    while True:
        try:
            refresh_cache()
        except Exception as e:
            print("Background refresh error:", e)
        time.sleep(1800)

@app.route("/")
def index():
    with open("dashboard.html", "r", encoding="utf-8") as f: return f.read()

@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})

@app.route("/search")
def search():
    if not _cache["posts"] or (time.time() - _cache["updated"]) > 3600:
        refresh_cache()
    return jsonify({"posts": _cache["posts"], "total": len(_cache["posts"])})

if __name__ == "__main__":
    t = threading.Thread(target=background_refresh, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=False)
