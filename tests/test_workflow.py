import copy, json, os, shutil, subprocess, tempfile, unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
import publication as p
import newsroom as n
import pipeline as flow

class Workflow(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        for name in ('assets','content','editorial','editor'):
            shutil.copytree(p.ROOT/name,self.root/name)
        for name in ('publication.json','newsroom.py','publication.py','amplify.yml'):
            shutil.copyfile(p.ROOT/name,self.root/name)
        self.slug='2026-09-15'
        cfg=p.config(self.root);cfg.update(site_url='https://example.org',contact_email='editor@example.org',kit_email_address='editor@example.org',kit_email_template_id=123)
        p.write(self.root/'publication.json',cfg)
        for _,_,entry in p.load_items(self.root):self.review(entry["slug"])
    def review(self,slug):
        _,d=n.find_item(slug,self.root)
        p.write(flow.review_path(slug,self.root),{"revision":p.fingerprint(d),"reviewer":"Synthetic test fixture","checked_at":"2026-09-15T00:00:00Z","verdict":"ready","unresolved":[],"checks":{key:{"verdict":"supported","basis":"Synthetic test evidence; not an actual source review.","sources_checked":[s["url"] for s in sources]} for key,sources in flow.targets(d).items()}})
    def tearDown(self):self.tmp.cleanup()
    def item(self):return n.find_item(self.slug,self.root)
    def approve(self):self.review(self.slug);n.approve(self.slug,self.root)
    def test_drafts_private_and_links_exist(self):
        p.build(self.root,production=True)
        self.assertFalse((self.root/'dist/issues/2026-09-15').exists())
        self.assertFalse((self.root/'dist/editor').exists())
        from html.parser import HTMLParser
        from urllib.parse import urlsplit,unquote
        class Links(HTMLParser):
            def __init__(self):super().__init__();self.links=[]
            def handle_starttag(self,tag,attrs):
                self.links += [v for k,v in attrs if k in ('href','src') and v.startswith('/')]
        for path in (self.root/'dist').rglob('*.html'):
            parser=Links();parser.feed(path.read_text())
            for link in parser.links:
                target=self.root/'dist'/unquote(urlsplit(link).path).lstrip('/')
                self.assertTrue(target.exists(),(path,link))
    def test_approval_revision_and_published_guard(self):
        self.approve();path,d=self.item();d['intro']+=' An edit.'
        with self.assertRaisesRegex(ValueError,'changed since review'):p.validate(d)
        with self.assertRaisesRegex(ValueError,'cannot be approved'):n.approve('2026-09-14-pilot',self.root)
    def test_source_window_and_html(self):
        _,d=self.item();d['stories'][0]['source_date']='2026-09-01'
        with self.assertRaisesRegex(ValueError,'outside'):p.validate(d)
        rendered=p.markdown('<script>alert(1)</script> [bad](javascript:alert) [good](https://example.org)')
        self.assertNotIn('<script>',rendered);self.assertNotIn('href="javascript:',rendered);self.assertIn('href="https://example.org"',rendered)
    def test_default_date_uses_complete_window(self):
        self.assertEqual(n.issue_date(p.config(self.root),date(2026,9,16)),date(2026,9,15))
    def test_publish_dependency_rollback(self):
        self.approve()
        with self.assertRaisesRegex(ValueError,'unpublished feature'):n.publish(self.slug,root=self.root)
        self.assertEqual(self.item()[1]['status'],'reviewed')
        n.approve('data-centers-water-power',self.root)
        n.publish('data-centers-water-power',root=self.root);n.publish(self.slug,root=self.root)
        self.assertTrue((self.root/'dist/issues/2026-09-15/index.html').exists())
    def test_kit_retry_and_sent_protection(self):
        self.approve();calls=[];broadcast={}
        def request(method,path,payload=None):
            calls.append(method)
            if method in ('POST','PUT'):broadcast.update(payload,id=42,status='draft')
            return {'broadcast':copy.deepcopy(broadcast)}
        n.kit_sync(self.slug,self.root,request);n.kit_sync(self.slug,self.root,request)
        self.assertEqual(calls,['POST','GET'])
        broadcast['content']='Edited in Kit'
        n.kit_sync(self.slug,self.root,request);self.assertEqual(calls[-2:],['GET','PUT'])
        broadcast['status']='sent'
        with self.assertRaisesRegex(ValueError,'no longer'):n.kit_sync(self.slug,self.root,request)
    def test_kit_unknown_creation_never_reposts(self):
        self.approve();calls=[]
        def broken(*args):calls.append(args[0]);raise ValueError('timeout')
        with self.assertRaises(ValueError):n.kit_sync(self.slug,self.root,broken)
        with self.assertRaisesRegex(ValueError,'uncertain'):n.kit_sync(self.slug,self.root,broken)
        self.assertEqual(calls,['POST'])
    def test_draft_schema_runner_and_no_overwrite(self):
        _,d=self.item()
        d=copy.deepcopy(d);d['research_notes']='Primary sources inspected.'
        for s in d['stories']:s['source_date']='2026-09-07'
        def runner(args,**kwargs):
            self.assertNotIn('KIT_API_KEY',kwargs['env'])
            self.assertIn('read-only',args)
            Path(args[args.index('-o')+1]).write_text(json.dumps(d))
            return subprocess.CompletedProcess(args,0)
        with patch.dict(os.environ,{'CODEX_BIN':'codex','KIT_API_KEY':'test-secret'}):
            n.draft('2026-09-08',root=self.root,runner=runner)
            with self.assertRaisesRegex(ValueError,'already exists'):n.draft('2026-09-08',root=self.root,runner=runner)
        saved=p.read(self.root/'content/issues/2026-09-08.json')
        self.assertEqual(saved['status'],'draft');self.assertNotIn('research_notes',saved)
        self.assertTrue((self.root/'editorial/research/2026-09-08.md').exists())
    def test_publish_push_preserves_unrelated_work(self):
        def git(*args):return n.clean_git(list(args),self.root)
        git('init','-b','main');git('config','user.name','Test');git('config','user.email','test@example.org')
        git('add','.');git('commit','-m','Initial')
        remote=self.root/'remote.git';subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
        git('remote','add','origin',str(remote))
        path,d=self.item();d['feature_slug']='';p.write(path,d);self.approve()
        (self.root/'unrelated.txt').write_text('Keep private')
        n.publish(self.slug,push=True,root=self.root)
        changed=git('show','--pretty=format:','--name-only','HEAD').splitlines()
        self.assertTrue(all(x.startswith('dist/') or x=='content/issues/2026-09-15.json' for x in changed))
        self.assertIn('?? unrelated.txt',git('status','--short'))
        self.assertEqual(git('rev-parse','HEAD'),git('rev-parse','origin/main'))

    def test_editor_http_review_save_and_stale_guard(self):
        import socket, time, re
        from urllib.request import Request,urlopen
        from urllib.error import HTTPError
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        p.build(self.root)
        process=subprocess.Popen([os.sys.executable,'-c',
            'from pathlib import Path; import newsroom; newsroom.serve('+str(port)+',root=Path('+repr(str(self.root))+'),open_browser=False)'],
            cwd=p.ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        base='http://127.0.0.1:'+str(port)
        def get(path):return urlopen(base+path,timeout=3).read().decode()
        def post(path,data,token=''):
            return json.loads(urlopen(Request(base+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','X-Newsroom-Token':token}),timeout=3).read())
        try:
            for _ in range(30):
                try:html=get('/');break
                except OSError:time.sleep(.05)
            else:self.fail('Review server did not start')
            token=re.search(r'const TOKEN="([^"]+)"',html)[1]
            with self.assertRaises(HTTPError) as denied:post('/api/approve',{'slug':self.slug})
            self.assertEqual(denied.exception.code,403)
            loaded=json.loads(get('/api/item?slug='+self.slug))
            post('/api/approve',{'slug':self.slug,'revision':loaded['revision']},token)
            loaded['item']['intro']+=' Saved through review.'
            post('/api/save',{'slug':self.slug,'revision':loaded['revision'],'item':loaded['item']},token)
            self.assertEqual(self.item()[1]['status'],'draft')
            with self.assertRaises(HTTPError):post('/api/save',{'slug':self.slug,'revision':loaded['revision'],'item':loaded['item']},token)
            preview=get('/api/preview?slug='+self.slug)
            self.assertIn('href="/api/preview?slug=data-centers-water-power"',preview)
            reader=get('/api/preview?slug='+self.slug+'&reader=1')
            self.assertNotIn('Unpublished draft',reader)
            self.assertIn('noindex,nofollow',reader)
            self.assertEqual(self.item()[1]['status'],'draft')
            self.assertIn(self.item()[1]['facts'][0]['title'],reader)
            self.assertIn('The weekly roundup',get('/archive/'))
            with self.assertRaises(HTTPError):get('/site/%2e%2e/publication.json')
        finally:
            process.terminate();process.wait(timeout=5)

    def test_kit_definite_rejection_can_retry(self):
        self.approve()
        def denied(*args):raise n.KitRejected("401")
        with self.assertRaises(n.KitRejected):n.kit_sync(self.slug,self.root,denied)
        self.assertFalse((self.root/".newsroom/kit"/(self.slug+".json")).exists())

    def test_facts_require_sources_and_invalidate_approval(self):
        path,d=self.item();d["facts"][0]["sources"]=[]
        with self.assertRaisesRegex(ValueError,"source"):p.validate(d)
        self.approve();path,d=self.item();d["facts"][0]["claim"]+=" An edit."
        with self.assertRaisesRegex(ValueError,"changed since review"):p.validate(d)
    def test_facts_match_website_and_email(self):
        _,d=self.item()
        web=p.issue_body(d);email=p.email_html(d,p.config(self.root))
        for fact in d["facts"]:
            self.assertIn(p.inline(fact["claim"]),web)
            self.assertIn(p.inline(fact["claim"]),email)
            self.assertIn(fact["sources"][0]["url"],email)
        n.export_email(self.slug,self.root)
        plain=(self.root/".newsroom/email"/(self.slug+".txt")).read_text()
        self.assertIn(d["facts"][0]["claim"],plain)

    def test_editorial_gate_requires_current_evidence_and_feedback_resolution(self):
        flow.review_path(self.slug,self.root).unlink()
        with self.assertRaisesRegex(ValueError,"source review"):n.approve(self.slug,self.root)
        self.review(self.slug)
        flow.feedback(self.slug,"Make the caveat clearer.",self.root)
        with self.assertRaisesRegex(ValueError,"pending feedback"):n.approve(self.slug,self.root)
        flow.resolve_feedback(self.slug,"Explained the caveat in the revised presentation.",self.root)
        n.approve(self.slug,self.root)
        path,d=self.item();d["intro"]+=" Updated.";d["status"]="draft";d.pop("reviewed_sha256");p.write(path,d)
        with self.assertRaisesRegex(ValueError,"Content changed"):flow.check_review(self.slug,self.root)
    def test_review_packet_and_release_are_private_and_retry_safe(self):
        packet=flow.present(self.slug,self.root)
        first=flow.state(self.slug,self.root)
        self.assertIn("Two facts",packet.read_text())
        self.assertEqual(packet,flow.present(self.slug,self.root))
        self.assertEqual(first,flow.state(self.slug,self.root))
        with self.assertRaisesRegex(ValueError,"approve"):flow.prepare_release(self.slug,self.root)
        self.approve();n.approve("data-centers-water-power",self.root)
        release=flow.prepare_release(self.slug,self.root)
        manifest=p.read(release/"manifest.json")
        self.assertEqual(manifest["website"],"not_published")
        self.assertEqual(manifest["newsletter"],"not_sent")
        self.assertTrue((release/"website/issues/2026-09-15/index.html").exists())
        self.assertIn(self.item()[1]['facts'][0]['title'],(release/"email.html").read_text())
        self.assertEqual(self.item()[1]["status"],"reviewed")
        self.assertEqual(release,flow.prepare_release(self.slug,self.root))
        self.assertFalse((self.root/"dist/issues/2026-09-15").exists())

if __name__=='__main__':unittest.main()
