"""Editorial handoff and release preparation. No network delivery."""
import argparse, copy, hashlib, json, shutil, tempfile
from datetime import datetime, timezone
from pathlib import Path
import publication as p

def now():return datetime.now(timezone.utc).isoformat()
def item(slug,root=p.ROOT):
    import newsroom
    return newsroom.find_item(slug,root)
def review_path(slug,root=p.ROOT):return root/"editorial/reviews"/(slug+".json")
def state_path(slug,root=p.ROOT):return root/"editorial/workflow"/(slug+".json")
def state(slug,root=p.ROOT):
    path=state_path(slug,root)
    return p.read(path) if path.exists() else {"slug":slug,"events":[]}
def targets(d):
    if d["kind"]=="feature":return {"feature":d["sources"]}
    return {**{"story:"+str(i):s["sources"] for i,s in enumerate(d["stories"])},**{"fact:"+str(i):f["sources"] for i,f in enumerate(d.get("facts",[]))}}
def check_review(slug,root=p.ROOT):
    _,d=item(slug,root);p.validate(d)
    path=review_path(slug,root)
    if not path.exists():raise ValueError("Editorial source review is still needed before approval.")
    report=p.read(path)
    if report.get("revision")!=p.fingerprint(d):raise ValueError("Content changed; recheck the editorial review for this revision.")
    if report.get("verdict")!="ready" or report.get("unresolved"):raise ValueError("Resolve the editorial review concerns before approval.")
    checks=report.get("checks",{})
    if set(checks)!=set(targets(d)):raise ValueError("Editorial review must cover every story and both facts.")
    if d["kind"]=="issue" and len(d.get("facts",[]))!=2:raise ValueError("Two supported facts are required.")
    for key,sources in targets(d).items():
        check=checks[key]
        if check.get("verdict")!="supported" or not check.get("basis"):raise ValueError("Missing evidence assessment: "+key)
        checked=check.get("sources_checked",[])
        if not {x["url"] for x in sources}.issubset(set(checked)):raise ValueError("Source review is incomplete: "+key)
    if not report.get("reviewer") or not report.get("checked_at"):raise ValueError("Record who checked the sources and when.")
    return report
def status(slug,root=p.ROOT):
    _,d=item(slug,root)
    try:check_review(slug,root);review="ready"
    except ValueError as e:review=str(e)
    return {"slug":slug,"revision":p.fingerprint(d),"editorial_review":review,"approval":d["status"],"workflow":state(slug,root),"delivery":"Integrations deferred; no automatic website or newsletter delivery."}
def present(slug,root=p.ROOT):
    _,d=item(slug,root);p.validate(d)
    if d["kind"]!="issue":raise ValueError("Present an issue")
    st=status(slug,root)
    lines=["# "+d["title"],"",d["window_start"]+" through "+d["window_end"],"",d["intro"],""]
    for story in d["stories"]:
        lines += ["## "+story["title"],"",story["summary"],"","**AI's role:** "+story["ai_role"],"","**Why it matters:** "+story["why_it_matters"],"","**Keep in mind:** "+story["caveat"],""]
        lines += ["- ["+x["title"]+"]("+x["url"]+")" for x in story["sources"]]
        lines += [""]
    lines += ["## Two facts, with context",""]
    for fact in d.get("facts",[]):
        lines += ["### "+fact["topic"]+": "+fact["title"],"",fact["claim"],"",fact["context"],"",fact["as_of"],""]
        lines += ["- ["+x["title"]+"]("+x["url"]+")" for x in fact["sources"]]
        lines += [""]
    lines += ["## For your review","", "Editorial source review: "+st["editorial_review"],"",
              "[Full reader preview](http://localhost:4317/api/preview?slug="+slug+"&reader=1)",
              "", "Please share any edits. This draft has not been approved, published or emailed."]
    folder=root/".newsroom/review"/slug/p.fingerprint(d);folder.mkdir(parents=True,exist_ok=True)
    (folder/"draft.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    p.write(folder/"content.json",d)
    st=state(slug,root)
    if st.get("prepared_revision")!=p.fingerprint(d):
        st["prepared_revision"]=p.fingerprint(d);st["events"].append({"event":"prepared_for_review","revision":p.fingerprint(d),"at":now()});p.write(state_path(slug,root),st)
    return folder/"draft.md"
def feedback(slug,text,root=p.ROOT):
    if not text.strip():raise ValueError("Feedback is empty")
    path,d=item(slug,root)
    if d["status"]=="published":raise ValueError("Use a correction workflow for an already published issue.")
    st=state(slug,root);st["events"].append({"event":"feedback","revision":p.fingerprint(d),"text":text.strip(),"at":now()})
    st["feedback_pending"]=True;p.write(state_path(slug,root),st)
    d["status"]="draft";d.pop("reviewed_sha256",None);p.write(path,d)
    return "Feedback saved; approval cleared. Revise, recheck and present the updated issue."
def resolve_feedback(slug,summary,root=p.ROOT):
    if not summary.strip():raise ValueError("Describe how the feedback was addressed")
    _,d=item(slug,root);st=state(slug,root)
    st["feedback_pending"]=False;st["events"].append({"event":"feedback_addressed","revision":p.fingerprint(d),"summary":summary,"at":now()})
    p.write(state_path(slug,root),st)
def approval_gate(slug,root=p.ROOT):
    check_review(slug,root)
    if state(slug,root).get("feedback_pending"):raise ValueError("Address and record the pending feedback before approval.")
def prepare_release(slug,root=p.ROOT):
    import newsroom
    _,d=item(slug,root);approval_gate(slug,root)
    if d["status"]!="reviewed":raise ValueError("The user must approve this revision before release preparation.")
    selected=[d]
    if d.get("feature_slug"):
        _,feature=item(d["feature_slug"],root)
        if feature["status"] not in ("reviewed","published"):raise ValueError("The linked explainer also needs approval.")
        if feature["status"]=="reviewed":approval_gate(feature["slug"],root)
        selected.append(feature)
    revision=hashlib.sha256(json.dumps({"items":selected,"settings":p.config(root)},sort_keys=True).encode()).hexdigest()
    dest=root/".newsroom/releases"/slug/revision
    # Each package is an immutable snapshot; retry returns the same package.
    if (dest/"manifest.json").exists():return dest
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ai-actually-release-",dir=dest.parent) as tmp:
        clone=Path(tmp)/"source";clone.mkdir()
        for name in ("content","assets"):shutil.copytree(root/name,clone/name)
        shutil.copyfile(root/"publication.json",clone/"publication.json")
        for entry in selected:
            entry=copy.deepcopy(entry);entry["status"]="published"
            p.write(clone/"content"/("issues" if entry["kind"]=="issue" else "features")/(entry["slug"]+".json"),entry)
        p.build(clone);email=newsroom.export_email(slug,clone)
        package=Path(tmp)/"package";package.mkdir();shutil.copytree(clone/"dist",package/"website")
        shutil.copyfile(email,package/"email.html");shutil.copyfile(email.with_suffix(".txt"),package/"email.txt")
        p.write(package/"content.json",d)
        files={str(x.relative_to(package)):hashlib.sha256(x.read_bytes()).hexdigest() for x in package.rglob("*") if x.is_file()}
        p.write(package/"manifest.json",{"slug":slug,"revision":p.fingerprint(d),"package_id":revision,"created_at":now(),"website":"not_published","newsletter":"not_sent","integrations":"deferred","files":files})
        package.replace(dest)
    st=state(slug,root);st["events"].append({"event":"release_prepared","revision":p.fingerprint(d),"package":str(dest.relative_to(root)),"at":now()});p.write(state_path(slug,root),st)
    return dest
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("command",choices=["status","present","feedback","resolve-feedback","check-review","prepare-release"]);parser.add_argument("slug");parser.add_argument("--file")
    a=parser.parse_args()
    try:
        if a.command=="feedback":
            if not a.file:raise ValueError("Use --file with the user's feedback text")
            result=feedback(a.slug,Path(a.file).read_text())
        elif a.command=="resolve-feedback":
            if not a.file:raise ValueError("Use --file with the revision summary")
            result=resolve_feedback(a.slug,Path(a.file).read_text()) or "Feedback addressed."
        else:result={"status":status,"present":present,"check-review":check_review,"prepare-release":prepare_release}[a.command](a.slug)
        print(json.dumps(result,indent=2) if isinstance(result,dict) else str(result))
    except (ValueError,FileNotFoundError) as e:parser.exit(1,str(e)+"\n")
if __name__=="__main__":main()
