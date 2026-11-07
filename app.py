import os, random, re, html, sqlite3
from datetime import datetime, timezone
import requests, feedparser, streamlit as st
from streamlit_autorefresh import st_autorefresh
from textblob import TextBlob

st.set_page_config(page_title="Goodison Oracle", page_icon="🔵", layout="wide")
st_autorefresh(interval=180000, key="refresh")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;800;900&family=Inter:wght@400;600;700;800&display=swap');
.stApp{background:linear-gradient(180deg,#071b33 0,#0b2a4a 260px,#f3f6fa 260px)}
.block-container{max-width:1450px;padding-top:1rem}
h1,h2,h3{font-family:'Barlow Condensed',sans-serif!important}
.hero{color:white;padding:16px 4px 20px}.hero h1{color:white;font-size:64px;line-height:.9;margin:8px 0}
.hero p{color:#c6d8e8}.eyebrow{font-size:10px;letter-spacing:2px;font-weight:800;color:#7c91a5;text-transform:uppercase}
.panel{background:white;border:1px solid #e1e9f0;border-radius:16px;padding:17px 19px;margin-bottom:12px;box-shadow:0 5px 20px #09243b0b}
.mood{font-family:'Barlow Condensed';font-size:32px;font-weight:900;line-height:1;color:#0a2947;margin:10px 0}
.pill{border-radius:20px;padding:5px 10px;font-size:10px;font-weight:900;letter-spacing:1px}.good{background:#def4e6;color:#17643a}.bad{background:#fde6e6;color:#a52c2c}
.muted{color:#71869a;font-size:12px}.feed{padding:11px 0;border-bottom:1px solid #edf1f5}.feed a{font-weight:750}
div[data-testid="stMetric"]{background:white;border:1px solid #e1e9f0;border-radius:12px;padding:10px}
.stButton>button{border-radius:10px;font-weight:800}
</style>
""", unsafe_allow_html=True)

def secret(k, default=""):
    try: return st.secrets.get(k, os.getenv(k, default))
    except Exception: return os.getenv(k, default)

pw=secret("DASHBOARD_PASSWORD")
if pw and not st.session_state.get("auth"):
    st.title("🔵 The Goodison Oracle")
    val=st.text_input("Personal dashboard password",type="password")
    if st.button("Unlock",type="primary"):
        if val==pw: st.session_state.auth=True; st.rerun()
        else: st.error("Incorrect password.")
    st.stop()

H={"User-Agent":"GoodisonOraclePersonalDashboard/2.0"}
@st.cache_data(ttl=180)
def matches():
    try:
        j=requests.get("https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard",headers=H,timeout=12).json()
        out=[]
        for e in j.get("events",[]):
            cs=(e.get("competitions") or [{}])[0].get("competitors",[])
            if not any("everton" in c.get("team",{}).get("displayName","").lower() for c in cs): continue
            h=next((c for c in cs if c.get("homeAway")=="home"),{})
            a=next((c for c in cs if c.get("homeAway")=="away"),{})
            out.append({"home":h.get("team",{}).get("displayName","Home"),"away":a.get("team",{}).get("displayName","Away"),
             "hs":h.get("score","—"),"as":a.get("score","—"),"date":e.get("date",""),
             "status":e.get("status",{}).get("type",{}).get("description","Unknown"),
             "state":e.get("status",{}).get("type",{}).get("state","")})
        return out
    except Exception: return []

@st.cache_data(ttl=600)
def headlines():
    feeds=[("Everton FC","https://www.evertonfc.com/news/rss"),
           ("BBC Sport","https://feeds.bbci.co.uk/sport/football/teams/everton/rss.xml"),
           ("Google News","https://news.google.com/rss/search?q=Everton+FC+when:7d&hl=en-GB&gl=GB&ceid=GB:en")]
    out=[]; seen=set()
    for src,url in feeds:
        try:
            for e in feedparser.parse(url).entries[:10]:
                title=e.get("title","Everton update")
                if title.lower() not in seen:
                    seen.add(title.lower()); out.append({"source":src,"title":title,"link":e.get("link","#"),"date":e.get("published","")})
        except Exception: pass
    return out[:25]

@st.cache_data(ttl=300)
def supporters():
    try:
        j=requests.get("https://www.reddit.com/r/Everton/hot.json?limit=25",headers=H,timeout=12).json()
        return [{"title":x["data"]["title"],"score":x["data"]["score"],"comments":x["data"]["num_comments"],
                 "url":"https://reddit.com"+x["data"]["permalink"],"body":x["data"].get("selftext","")[:350]}
                for x in j["data"]["children"]]
    except Exception: return []

def sentiment(xs):
    vals=[TextBlob(x).sentiment.polarity for x in xs if x]
    return sum(vals)/len(vals) if vals else 0.0

def score_mood(ms,ns,ps):
    gd=0
    for m in ms:
        if m["state"]=="post":
            try:
                d=int(m["hs"])-int(m["as"]); gd += d if "everton" in m["home"].lower() else -d
            except Exception: pass
    fan=sentiment([p["title"]+" "+p["body"] for p in ps])
    press=sentiment([n["title"] for n in ns])
    total=gd*.22+fan*1.35+press*.65
    return ("GLORIOUS" if total>=0 else "DOOM"),total,fan,press,gd

def save(mood,total,fan,press):
    try:
        with sqlite3.connect("oracle_history.sqlite3") as c:
            c.execute("CREATE TABLE IF NOT EXISTS mood(ts TEXT,mood TEXT,total REAL,fan REAL,press REAL)")
            c.execute("INSERT INTO mood VALUES(?,?,?,?,?)",(datetime.now(timezone.utc).isoformat(),mood,total,fan,press))
    except Exception: pass

def ask_ai(mood,total,ms,ns,ps):
    key=secret("OPENAI_API_KEY")
    if not key: return None,"Add OPENAI_API_KEY in Streamlit Secrets to activate the AI pundit."
    context={"mood":mood,"score":round(total,3),"matches":ms[:5],"headlines":[n["title"] for n in ns[:8]],"supporter_posts":[p["title"] for p in ps[:8]]}
    prompt=("You are The Goodison Oracle: eccentric, hilarious, Everton obsessed. Exactly two verdicts: GLORIOUS means best club in the world; DOOM means worst club in the world. No middle ground. Be pro-Everton, cheekily dismissive of Liverpool, never harass people. Use only supplied data; do not invent facts. Separate data from vibes. Give verdict, three evidence bullets, one watch-item and one absurd prophecy. Context: "+str(context))
    try:
        r=requests.post("https://api.openai.com/v1/responses",headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},
          json={"model":secret("OPENAI_MODEL","gpt-4.1-mini"),"input":prompt},timeout=40)
        r.raise_for_status(); d=r.json(); out=d.get("output_text","")
        if not out: out="\n".join(p.get("text","") for i in d.get("output",[]) for p in i.get("content",[]) if p.get("type")=="output_text")
        return out or "The Oracle is speechless.",None
    except Exception as e: return None,str(e)

ms,ns,ps=matches(),headlines(),supporters()
mood,total,fan,press,gd=score_mood(ms,ns,ps); save(mood,total,fan,press)
stamp=datetime.now().astimezone().strftime("%d %b %Y · %H:%M:%S")

with st.sidebar:
    st.markdown("## 🔵 Oracle controls")
    st.caption("Personal command centre · auto-refreshes every 3 minutes")
    if st.button("↻ Refresh feeds",use_container_width=True): st.cache_data.clear(); st.rerun()
    debug=st.toggle("Show diagnostics",False)
    st.divider()
    st.markdown("[Everton official](https://www.evertonfc.com/)")
    st.markdown("[Premier League](https://www.premierleague.com/en/clubs/11/everton)")
    st.markdown("[r/Everton](https://www.reddit.com/r/Everton/)")

st.markdown(f'<div class="hero"><div class="eyebrow" style="color:#9bc7ed">PERSONAL FOOTBALL INTELLIGENCE · UNOFFICIAL FAN PROJECT</div><h1>THE GOODISON<br>ORACLE 🔵</h1><p>Your Everton command centre. Live match data, news signals, supporter temperature and irrational conclusions.</p></div>',unsafe_allow_html=True)
a,b,c,d=st.columns([1.4,1,1,1])
with a:
    st.markdown('<div class="panel"><div class="eyebrow">THE ONLY TWO POSSIBLE VERDICTS</div>',unsafe_allow_html=True)
    if mood=="GLORIOUS": st.markdown('<span class="pill good">GLORY MODE · UTFT</span><div class="mood">EVERTON ARE THE BEST CLUB IN THE WORLD.</div>',unsafe_allow_html=True)
    else: st.markdown('<span class="pill bad">DOOM MODE · EMERGENCY MEETING</span><div class="mood">EVERTON ARE THE WORST CLUB IN THE WORLD.</div>',unsafe_allow_html=True)
    st.caption("No middle ground. No appeals. The Oracle has spoken."); st.markdown('</div>',unsafe_allow_html=True)
with b: st.metric("Supporter pulse",f"{fan:+.2f}"); st.caption("Text sentiment estimate")
with c: st.metric("Headline tone",f"{press:+.2f}"); st.caption("RSS headline sentiment")
with d: st.metric("Everton result signal",f"{gd:+d}"); st.caption("Fetched goal difference")

t=st.tabs(["⌂ Overview","⚽ Match centre","🗞 Newsroom","🗣 Supporters","🧠 AI pundit","🎲 Randomiser","📈 Mood history","⚙ Settings"])
with t[0]:
    x,y=st.columns([1.2,.8])
    with x:
        st.markdown('<div class="panel"><div class="eyebrow">MATCH RADAR</div><h2>Latest / upcoming Everton fixtures</h2>',unsafe_allow_html=True)
        if ms:
            for m in ms[:4]:
                st.markdown(f"**{m['home']} {m['hs']} — {m['as']} {m['away']}**"); st.caption(f"{m['status']} · {m['date'][:16].replace('T',' ')}"); st.divider()
        else: st.info("No Everton fixture data returned.")
        st.markdown('</div>',unsafe_allow_html=True)
    with y:
        st.markdown('<div class="panel"><div class="eyebrow">DAILY NONSENSE</div><h2>Oracle prophecy</h2>',unsafe_allow_html=True)
        prop=["A corner flag shall tremble. A pigeon shall understand the offside rule.","The next Everton goal will be celebrated in three time zones.","A tactical masterclass approaches. Or a weather event. The Oracle cannot distinguish them."]
        st.write(random.choice(prop))
        if st.button("Another prophecy"): st.success(random.choice(prop))
        st.markdown('</div>',unsafe_allow_html=True)
    st.markdown('<div class="panel"><div class="eyebrow">HEADLINE RADAR</div><h2>Latest signals</h2>',unsafe_allow_html=True)
    for n in ns[:5]: st.markdown(f"- [{n['title']}]({n['link']}) · {n['source']}")
    st.markdown('</div>',unsafe_allow_html=True)
with t[1]:
    st.markdown('<div class="panel"><div class="eyebrow">SCOREBOARD FEED</div><h2>Everton match centre</h2>',unsafe_allow_html=True)
    for m in ms:
        q,w=st.columns([1,1])
        q.markdown(f"**{m['home']}**"); w.markdown(f"**{m['away']}**")
        st.markdown(f"<h2 style='text-align:center'>{m['hs']} — {m['as']}</h2>",unsafe_allow_html=True); st.caption(f"{m['status']} · {m['date']}"); st.divider()
    if not ms: st.info("The scoreboard is temporarily unavailable.")
    st.markdown('</div>',unsafe_allow_html=True)
with t[2]:
    st.markdown('<div class="panel"><div class="eyebrow">LIVE RSS AGGREGATION</div><h2>Everton newsroom</h2>',unsafe_allow_html=True)
    for n in ns: st.markdown(f'<div class="feed"><a href="{html.escape(n["link"],quote=True)}" target="_blank">{html.escape(n["title"])}</a><div class="muted">{html.escape(n["source"])} · {html.escape(n["date"])}</div></div>',unsafe_allow_html=True)
    if not ns: st.info("News feeds unavailable.")
    st.markdown('</div>',unsafe_allow_html=True)
with t[3]:
    st.markdown('<div class="panel"><div class="eyebrow">PUBLIC SUPPORTER CONVERSATION</div><h2>The people have the floor</h2><p class="muted">Public r/Everton hot posts; not a representative fan poll.</p>',unsafe_allow_html=True)
    for p in ps:
        st.markdown(f"**[{p['title']}]({p['url']})**"); st.caption(f"⬆ {p['score']} · 💬 {p['comments']}")
        if p["body"]: st.write(p["body"])
        st.divider()
    if not ps: st.info("Reddit feed unavailable; no opinions fabricated.")
    st.markdown('</div>',unsafe_allow_html=True)
with t[4]:
    st.markdown('<div class="panel"><div class="eyebrow">OPTIONAL LLM BRIEFING</div><h2>Ask the Goodison Oracle</h2><p class="muted">AI uses current fetched headlines, match records and supporter-post sample.</p>',unsafe_allow_html=True)
    if st.button("Generate full Everton intelligence briefing",type="primary"):
        with st.spinner("Consulting the blue intelligence network..."):
            answer,error=ask_ai(mood,total,ms,ns,ps)
        if answer: st.markdown(answer)
        else: st.warning(error)
    st.markdown('</div>',unsafe_allow_html=True)
    st.markdown('<div class="panel"><div class="eyebrow">RIVALRY DESK</div><h2>Liverpool policy</h2><p>Not the subject of this dashboard. Our attention is reserved for Everton.</p>',unsafe_allow_html=True)
    if st.button("Issue rival-club statement"): st.info(random.choice(["Liverpool? We don't have their channel on this dashboard.","A red alert is a weather warning, not a footballing aspiration.","Focus on Everton. Roll eyes at the rest."]))
    st.caption("Playful banter only; no targeting of supporters."); st.markdown('</div>',unsafe_allow_html=True)
with t[5]:
    st.markdown('<div class="panel"><div class="eyebrow">CHAOS ENGINE</div><h2>Everton randomiser</h2>',unsafe_allow_html=True)
    if st.button("Random Everton fact"): st.info(random.choice(["Everton were founding members of the Football League in 1888.","Everton have won the English league title nine times.","The Toffees won the European Cup Winners’ Cup in 1985.","Goodison Park opened in 1892."]))
    if st.button("Random matchday ritual"): st.success(random.choice(["Wear blue. Make tea. Declare the opposition are in our jurisdiction.","Play Z-Cars and announce UTFT to an empty room.","Check team news fourteen times. Trust none of it.","Prepare a snack worthy of a European night."]))
    st.markdown('</div>',unsafe_allow_html=True)
with t[6]:
    st.markdown('<div class="panel"><div class="eyebrow">PERSONAL MOOD LOG</div><h2>Oracle mood history</h2><p class="muted">Stored in local SQLite. Some cloud hosts reset local files on restart.</p>',unsafe_allow_html=True)
    try:
        import pandas as pd
        with sqlite3.connect("oracle_history.sqlite3") as con: df=pd.read_sql_query("SELECT * FROM mood ORDER BY ts DESC LIMIT 100",con)
        if not df.empty:
            df["ts"]=pd.to_datetime(df["ts"],errors="coerce"); st.line_chart(df.set_index("ts")[["total","fan","press"]]); st.dataframe(df,use_container_width=True,hide_index=True)
        else: st.caption("No mood history yet.")
    except Exception as e: st.info(f"History unavailable: {e}")
    st.markdown('</div>',unsafe_allow_html=True)
with t[7]:
    st.markdown('<div class="panel"><div class="eyebrow">PERSONAL CONTROL ROOM</div><h2>Sources, privacy and diagnostics</h2>',unsafe_allow_html=True)
    st.write("**Sources:** ESPN public scoreboard; Everton FC, BBC Sport and Google News RSS; public r/Everton posts; TextBlob sentiment; optional OpenAI Responses API.")
    st.write("**Refresh:** dashboard every 3 minutes; scores 3 minutes, Reddit 5 minutes, news 10 minutes.")
    st.write("**Privacy:** no user account or comment submission. Set `DASHBOARD_PASSWORD` in Streamlit Secrets for a basic password gate.")
    st.write("**AI:** set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` in Streamlit Secrets. Never commit secrets to GitHub.")
    st.warning("This is a playful heuristic, not a validated prediction model. Public feeds may be delayed, incomplete or rate-limited. Unofficial fan project.")
    if debug: st.json({"last_refresh":stamp,"matches":len(ms),"news_items":len(ns),"reddit_posts":len(ps)})
    st.markdown('</div>',unsafe_allow_html=True)

st.markdown(f"<div style='text-align:center;color:#879bad;font-size:10px;padding:18px'>UNOFFICIAL PERSONAL EVERTON FAN PROJECT · LAST REFRESH {stamp} · UTFT</div>",unsafe_allow_html=True)
