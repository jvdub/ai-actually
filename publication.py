"""Content validation and static publication. Python standard library only."""
import copy, hashlib, html, json, re, shutil, tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STAGES = ["Deployed use", "Pilot", "Research", "Announcement"]
def read(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def write(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n"); name = f.name
    Path(name).replace(path)
def config(root=ROOT): return read(root / "publication.json")
def fingerprint(item):
    return hashlib.sha256(json.dumps({k:v for k,v in item.items() if k not in ("status","reviewed_sha256")}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
def safe_url(value):
    if not isinstance(value,str):return False
    try:u=urlsplit(value)
    except ValueError:return False
    return u.scheme in ("https","http") and bool(u.hostname) and not u.username and not u.password
def esc(value): return html.escape(str(value), quote=True)
def inline(text):
    # Supported Markdown is deliberately small; raw HTML is always escaped.
    parts=[]; pos=0
    for m in re.finditer(r"\[([^\]\n]+)\]\(([^)\s]+)\)", text):
        parts.append(esc(text[pos:m.start()]))
        label,url=m.groups()
        if safe_url(url) or (url.startswith("/") and not url.startswith("//")) or url.startswith("#"):
            parts.append('<a href="'+esc(url)+'">'+esc(label)+'</a>')
        else: parts.append(esc(label))
        pos=m.end()
    parts.append(esc(text[pos:]))
    return re.sub(r"\*\*([^*]+)\*\*",r"<strong>\1</strong>","".join(parts))
def markdown(text):
    out=[]; paragraph=[]; items=[]
    def flush():
        if paragraph: out.append("<p>"+inline(" ".join(paragraph))+"</p>");paragraph.clear()
        if items: out.append("<ul>"+"".join("<li>"+inline(x)+"</li>" for x in items)+"</ul>");items.clear()
    for line in text.splitlines():
        if not line.strip(): flush()
        elif re.match(r"^#{2,3} ",line):
            flush(); n=len(line)-len(line.lstrip("#"));out.append(f"<h{n}>"+inline(line[n+1:])+f"</h{n}>")
        elif line.startswith("- "):
            if paragraph: flush()
            items.append(line[2:])
        else:
            if items: flush()
            paragraph.append(line.strip())
    flush();return "\n".join(out)
def load_items(root=ROOT):
    result=[]
    for kind in ("issues","features"):
        for p in sorted((root/"content"/kind).glob("*.json")):
            d=read(p)
            if d.get("slug")!=p.stem: raise ValueError(f"{p}: filename must match slug")
            validate(d)
            result.append((kind,p,d))
    return result
def validate(d):
    for k in ("slug","kind","title","description","date","status"):
        if not isinstance(d.get(k),str) or not d[k].strip(): raise ValueError("Missing "+k)
    if not SLUG.fullmatch(d["slug"]): raise ValueError("Invalid slug")
    date.fromisoformat(d["date"])
    if d["status"] not in ("draft","reviewed","published"): raise ValueError("Invalid status")
    if d["kind"]=="issue":
        start=date.fromisoformat(d["window_start"]);end=date.fromisoformat(d["window_end"])
        if end-start!=timedelta(days=6) or end!=date.fromisoformat(d["date"])-timedelta(days=1): raise ValueError("Use seven complete days before publication")
        if not d.get("stories"): raise ValueError("An issue needs at least one story")
        if not d.get("subject") or not d.get("intro"): raise ValueError("Issue needs subject and intro")
        if "facts" in d:
            facts=d["facts"]
            if not isinstance(facts,list) or len(facts)!=2:raise ValueError("Include two facts: one AI fact and one data-center fact.")
            if {f.get("topic") for f in facts}!={"AI","Data centers"}:raise ValueError("Facts must cover AI and Data centers.")
            for f in facts:
                for key in ("title","claim","context","as_of","checked_on"):
                    if not isinstance(f.get(key),str) or not f[key].strip():raise ValueError("Fact needs "+key)
                date.fromisoformat(f["checked_on"])
                check_sources(f.get("sources",[]))
                if any(not x.get("note") for x in f["sources"]):raise ValueError("Fact sources need a note locating the supporting evidence.")
        seen=set()
        for s in d["stories"]:
            for k in ("title","topic","stage","source_date","event_date","summary","ai_role","why_it_matters","caveat","sources"):
                if not s.get(k):raise ValueError(f"Story needs {k}")
            if s["stage"] not in STAGES: raise ValueError("Unknown evidence stage")
            if not start<=date.fromisoformat(s["source_date"])<=end: raise ValueError("Story source date outside the issue window: "+s["title"])
            if s["title"] in seen:raise ValueError("Duplicate story title")
            seen.add(s["title"]);check_sources(s["sources"])
    elif d["kind"]=="feature":
        if not d.get("body"):raise ValueError("Feature needs body")
        check_sources(d.get("sources",[]))
    else: raise ValueError("Unknown content kind")
    if d["status"] in ("reviewed","published") and d.get("reviewed_sha256")!=fingerprint(d):
        raise ValueError("Content changed since review: "+d["slug"])
def check_sources(sources):
    if not sources: raise ValueError("At least one source is required")
    for s in sources:
        if not s.get("title") or not safe_url(s.get("url","")):raise ValueError("Source needs a title and HTTP(S) URL")
def route(d): return "/"+("issues" if d["kind"]=="issue" else "features")+"/"+d["slug"]+"/"
def page(title,description,body,cfg,path="/",draft=False):
    base=cfg.get("site_url","").rstrip("/")
    canonical=f'<link rel="canonical" href="{esc(base+path)}">' if base and not draft else ""
    robot='<meta name="robots" content="noindex,nofollow">' if draft or not base else ""
    signup=f'<a href="{esc(cfg["signup_url"])}">Subscribe</a>' if cfg.get("signup_url") and safe_url(cfg["signup_url"]) else ""
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>{esc(title)} — AI, Actually</title><meta name="description" content="{esc(description)}">{canonical}{robot}<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}"><link rel="stylesheet" href="/styles.css"><link rel="icon" href="/favicon.svg" type="image/svg+xml"></head><body><a class="skip" href="#main">Skip to content</a><header><div class="wrap"><div class="top"><a class="brand" href="/">AI<span>,</span> Actually<span>.</span></a><nav aria-label="Main navigation"><a href="/archive/">The roundup</a><a href="/features/">A closer look</a><a href="/about/">About</a>{signup}</nav></div></div></header>{body}<footer class="wrap"><div class="footer"><span>AI, Actually. &nbsp; Hope, with context.</span><nav aria-label="Publication information"><a href="/standards/">Editorial standards</a><a href="/corrections/">Corrections</a><a href="/privacy/">Privacy</a></nav></div></footer></body></html>'''
def sources_html(sources):
    return "<ul>"+"".join(f'<li><a href="{esc(s["url"])}">{esc(s["title"])}</a>'+(" · "+esc(s["note"]) if s.get("note") else "")+"</li>" for s in sources)+"</ul>"
def story_html(s,idx):
    return f'''<article class="story"><div class="meta"><span class="tag">{esc(s["topic"])}</span><span>{esc(s["stage"])}</span><time datetime="{esc(s["source_date"])}">{esc(s["source_date"])}</time></div><h2>{esc(s["title"])}</h2>{markdown(s["summary"])}<p><strong>AI’s role:</strong> {inline(s["ai_role"])}</p><p><strong>Why it matters:</strong> {inline(s["why_it_matters"])}</p><div class="caveat"><strong>Keep in mind:</strong> {inline(s["caveat"])}</div><details><summary>Sources &amp; timing</summary><p>{esc(s["event_date"])}</p>{sources_html(s["sources"])}</details></article>'''
def facts_html(facts,email=False):
    if not facts:return ""
    cards=[]
    for f in facts:
        cards.append('<article class="fact"><p class="eyebrow">'+esc(f["topic"])+'</p><h3>'+esc(f["title"])+'</h3><p>'+inline(f["claim"])+'</p><p class="fact-context"><strong>Context:</strong> '+inline(f["context"])+'</p><p class="fact-date">'+esc(f["as_of"])+'</p>'+sources_html(f["sources"])+'</article>')
    return '<section class="facts" aria-label="AI and data-center facts">'+"".join(cards)+'</section>'
def issue_body(d,features=None,preview=False):
    feature=next((x for x in features or [] if x["slug"]==d.get("feature_slug")),None)
    aside='<aside><div class="section-title">A closer look</div>'
    if feature:aside+=f'<article class="feature"><div class="eyebrow">Beyond the headlines</div><h2>{esc(feature["title"])}</h2><p>{esc(feature["description"])}</p><a class="read" href="{route(feature)}">Read the explainer →</a></article>'
    else:aside+='<p class="note">Occasional deeper reporting on the issues behind the headlines.</p>'
    aside+=facts_html(d.get("facts",[]))
    aside+='<div class="note"><strong>Optimistic. Eyes open.</strong><p>Benefits, possibilities, and limitations belong together. <a href="/standards/">How we choose stories</a>.</p></div></aside>'
    badge="Unpublished draft" if d["status"]!="published" else "Weekly edition"
    return f'''<main id="main" class="wrap"><div class="edition"><span>Issue {esc(d.get("number",""))} · {esc(d["window_start"])} – {esc(d["window_end"])}</span><span class="status">{badge}</span></div><section class="intro"><div class="eyebrow">The weekly roundup · {esc(d["date"])}</div><h1>{esc(d["title"])}</h1><p class="dek">{esc(d["description"])}</p>{markdown(d["intro"])}</section><div class="grid"><section aria-label="This week's stories"><div class="section-title"><span>Worth your attention</span><span>{len(d["stories"])} stories</span></div>{"".join(story_html(s,i) for i,s in enumerate(d["stories"]))}</section>{aside}</div><p class="note">Prepared with AI assistance. Sources and evidence limits are disclosed in each story.</p></main>'''
def feature_body(d):
    return f'<main id="main" class="wrap"><section class="article-head"><a class="back" href="/features/">← All explainers</a><p class="eyebrow">A closer look · {esc(d["date"])}</p><h1>{esc(d["title"])}</h1><p class="dek">{esc(d["description"])}</p>'+('<span class="status">Unpublished draft</span>' if d["status"]!="published" else "")+'</section><article class="prose standalone">'+markdown(d["body"])+'<section class="sources"><h3>Sources</h3>'+sources_html(d["sources"])+'</section></article></main>'
def email_html(d,cfg):
    base=cfg.get("site_url","").rstrip("/")
    parts=[f'<h1>{esc(d["title"])}</h1>',f'<p>{esc(d["description"])}</p>',markdown(d["intro"])]
    for s in d["stories"]:
        parts += [f'<h2>{esc(s["title"])}</h2>',f'<p><small>{esc(s["topic"])} · {esc(s["stage"])}</small></p>',markdown(s["summary"]),'<p><strong>AI’s role:</strong> '+inline(s["ai_role"])+'</p>','<p><strong>Why it matters:</strong> '+inline(s["why_it_matters"])+'</p>','<p><strong>Keep in mind:</strong> '+inline(s["caveat"])+'</p>',sources_html(s["sources"])]
    parts.append(facts_html(d.get("facts",[]),email=True))
    if base:
        parts.append(f'<p><a href="{esc(base+route(d))}">Read this issue on the website</a></p>')
        if d.get("feature_slug"):parts.append(f'<p><a href="{esc(base+"/features/"+d["feature_slug"]+"/")}">A closer look: this week’s featured explainer</a></p>')
    parts.append("<p><small>AI, Actually · Hope, with context. Prepared with AI assistance; sources linked throughout.</small></p>")
    # Kit's selected template supplies its own physical-address and unsubscribe footer.
    return '<div style="max-width:640px;margin:auto;font:17px/1.6 Georgia,serif;color:#172336">'+"".join(parts)+"</div>"
def build(root=ROOT,production=False):
    cfg=config(root)
    if production:
        if not safe_url(cfg.get("site_url","")) or not cfg["site_url"].startswith("https://"):raise ValueError("Set publication.json site_url to your HTTPS domain before production deployment")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",cfg.get("contact_email","")):raise ValueError("Set a real contact_email before public deployment")
    loaded=load_items(root);published=[d for _,_,d in loaded if d["status"]=="published"]
    issues=sorted([d for d in published if d["kind"]=="issue"],key=lambda d:d["date"],reverse=True)
    features=sorted([d for d in published if d["kind"]=="feature"],key=lambda d:d["date"],reverse=True)
    known={d["slug"] for d in features}
    for d in issues:
        if d.get("feature_slug") and d["feature_slug"] not in known:raise ValueError("Published issue references an unpublished feature")
    paths={}
    for d in published:
        body=issue_body(d,features) if d["kind"]=="issue" else feature_body(d)
        paths[route(d).lstrip("/")+"index.html"]=page(d["title"],d["description"],body,cfg,route(d))
    if issues:paths["index.html"]=page("Good news, with context",issues[0]["description"],issue_body(issues[0],features),cfg)
    else:paths["index.html"]=page("Good news, with context","Our first edition is in preparation.",'<main id="main" class="wrap intro"><h1>Good things are happening, too.</h1><p>Our first edition is in preparation.</p><a href="/about/">About the publication</a></main>',cfg)
    for name,items,title in [("archive",issues,"The weekly roundup"),("features",features,"A closer look")]:
        body='<main id="main" class="wrap"><section class="intro"><div class="eyebrow">AI, Actually</div><h1>'+title+'</h1></section><section class="archive-list">'
        for d in items:body+=f'<article class="story"><div class="meta">{esc(d["date"])}</div><h2><a href="{route(d)}">{esc(d["title"])}</a></h2><p>{esc(d["description"])}</p></article>'
        if not items:body+="<p>New stories will appear here as they are published.</p>"
        paths[name+"/index.html"]=page(title,title,body+"</section></main>",cfg,"/"+name+"/")
    contact=cfg.get("contact_email","")
    contact_line=f'Questions or corrections? [Email the editor](mailto:{contact}).' if contact else "Editorial contact details will be added before the public launch."
    info={
      "about":("About AI, Actually","A weekly publication for people who are curious about AI but uneasy about its direction.\n\nWe round up credible good news about AI and the outcomes it helps people achieve. Occasional explainers examine contentious topics, including their real costs and unresolved questions.\n\nOur goal is to help you feel more hopeful and better informed. We prioritize benefits to people over funding rounds and hype.\n\n"+contact_line),
      "standards":("Our editorial standards","## Hope grounded in evidence\nWe select encouraging developments and explain their limits. We do not claim this is a complete picture of AI's impact.\n\n## What the labels mean\n- **Deployed use:** a real application is operating; the label does not establish impact at scale.\n- **Pilot:** an initial implementation or evaluation with limited scope.\n- **Research:** a method or finding that may not yet be ready for everyday use.\n- **Announcement:** a release, award or planned development; stated benefits may remain unproven.\n\n## Sources and timing\nEach story links to its sources and distinguishes the report date from the event date. First-party claims are identified. Technical claims should trace to primary evidence, with independent verification where it matters.\n\n## AI assistance and review\nAI assists research and drafting. An editor reviews editions before publication. Automated checks validate completeness, not truth. We do not invent interviews or imply expert review that has not happened.\n\n## Conflicts and corrections\nAny future sponsorship or affiliate relationship will be labeled. Material corrections will be dated on the affected article and listed on our corrections page."),
      "corrections":("Corrections","We correct material factual errors and explain what changed. No correction notices have been recorded yet.\n\n"+contact_line),
      "privacy":("Privacy","This version has no newsletter signup form, advertising trackers or embedded analytics. The site itself does not ask readers to submit personal information.\n\nHosting providers may process ordinary request information, such as IP addresses and browser details, to operate and secure the site. Any access controls belong to the hosting service.\n\nIf a newsletter signup is connected, this notice must be updated to explain the provider, data collected and unsubscribe process before collection begins.\n\n"+contact_line)
    }
    if cfg.get("signup_url"):
        info["privacy"]=("Privacy","This website has no embedded newsletter form, advertising trackers or analytics. Its Subscribe link takes you to our external newsletter signup page.\n\nIf you subscribe through Kit, Kit processes your email address and any other information requested on that form to deliver the newsletter. Kit emails include an unsubscribe link. See [Kit privacy information](https://kit.com/privacy) for its practices, including email engagement information.\n\nHosting providers may process ordinary request information, such as IP addresses and browser details, to operate and secure the site.\n\n"+contact_line)
    for name,(title,body) in info.items():
        rendered=markdown(body)
        if contact:rendered=rendered.replace("Email the editor",f'<a href="mailto:{esc(contact)}">Email the editor</a>')
        paths[name+"/index.html"]=page(title,title,'<main id="main" class="wrap"><section class="article-head"><h1>'+title+'</h1></section><article class="prose standalone">'+rendered+'</article></main>',cfg,"/"+name+"/")
    paths["404.html"]=page("Page not found","This page could not be found.",'<main id="main" class="wrap intro"><h1>That page isn’t here.</h1><p><a href="/">Return to the latest issue</a></p></main>',cfg,draft=True)
    # Preserve legacy links as real pages, without relying on a SPA rewrite.
    if "data-centers" in known:
        d=next(x for x in features if x["slug"]=="data-centers")
        paths["data-centers.html"]=page(d["title"],d["description"],feature_body(d),cfg,route(d))
    base=cfg.get("site_url","").rstrip("/")
    paths["robots.txt"]="User-agent: *\n"+("Allow: /\nSitemap: "+base+"/sitemap.xml\n" if base else "Disallow: /\n")
    if base:
        urls=sorted("/"+p.removesuffix("index.html") for p in paths if p.endswith("index.html"))
        paths["sitemap.xml"]='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+"".join("<url><loc>"+esc(base+u)+"</loc></url>" for u in urls)+"</urlset>"
    paths["favicon.svg"]='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#172336"/><text x="9" y="45" font-family="Georgia,serif" font-size="42" fill="white">a<tspan fill="#82a5ff">.</tspan></text></svg>'
    target=root/"dist"
    with tempfile.TemporaryDirectory(prefix="ai-actually-build-") as tmp:
        stage=Path(tmp)
        for name,body in paths.items():
            p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body,encoding="utf-8")
        shutil.copyfile(root/"assets/styles.css",stage/"styles.css")
        # Exact owned output only; never operate outside the repository's dist.
        if target.is_symlink():raise ValueError("Refusing symlink output directory")
        if target.exists():shutil.rmtree(target)
        shutil.copytree(stage,target)
    return len(paths)
