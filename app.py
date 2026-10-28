import asyncio, csv, io, ipaddress, json, re, socket, time, uuid
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse, urldefrag
from urllib.robotparser import RobotFileParser
from typing import Any
import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

app=FastAPI(title="Webscrapperzz Intelligence",version="1.0.0")
JOBS: dict[str,dict[str,Any]]={}
ROBOTS={}
UA="WebscrapperzzBot/1.0 (+public website indexing)"
def normalize(raw:str)->str:
    raw=raw.strip()
    if "://" not in raw: raw="https://"+raw
    p=urlparse(raw)
    if p.scheme not in ("http","https") or not p.hostname or p.username or p.password: raise ValueError("Enter a valid public HTTP/HTTPS URL.")
    host=p.hostname.rstrip(".").lower()
    if host=="localhost" or host.endswith((".localhost",".local")): raise ValueError("Local network targets are blocked.")
    try:
        for x in socket.getaddrinfo(host,p.port or (443 if p.scheme=="https" else 80),type=socket.SOCK_STREAM):
            if not ipaddress.ip_address(x[4][0].split("%")[0]).is_global: raise ValueError("Private network targets are blocked.")
    except socket.gaierror: raise ValueError("Hostname could not be resolved.")
    return urlunparse((p.scheme,p.netloc.lower(),p.path or "/", "",p.query,""))
def canon(u): 
    p=urlparse(urldefrag(u).url); return urlunparse((p.scheme.lower(),p.netloc.lower(),re.sub(r"/{2,}","/",p.path or "/"),"",p.query,""))
def scope(u,host,sub=False):
    h=(urlparse(u).hostname or "").lower().rstrip("."); return h==host or (sub and h.endswith("."+host))
async def get(client,u):
    for _ in range(5):
        normalize(u)
        r=await client.get(u,follow_redirects=False)
        if r.status_code in (301,302,303,307,308) and r.headers.get("location"): u=urljoin(u,r.headers["location"]); continue
        return r
    raise ValueError("Too many redirects")
async def robots(client,origin):
    if origin in ROBOTS:return ROBOTS[origin]
    rp=RobotFileParser()
    try:
        r=await get(client,origin+"/robots.txt")
        if r.status_code==200 and len(r.content)<250000: rp.parse(r.text.splitlines()); ROBOTS[origin]=rp; return rp
    except Exception: pass
    ROBOTS[origin]=None; return None
def extract(url,r):
    ct=r.headers.get("content-type","")
    html=r.text[:2000000] if "html" in ct.lower() else ""
    s=BeautifulSoup(html,"html.parser")
    title=s.title.get_text(" ",strip=True) if s.title else ""
    desc=s.find("meta",attrs={"name":re.compile("^description$",re.I)})
    canon_tag=s.find("link",rel="canonical")
    structured=[]
    assets.extend({"type":"json-ld","data":item} for item in structured)
    return {"url":str(r.url),"status":r.status_code,"content_type":ct,"title":title,"description":desc.get("content","") if desc else "","canonical_url":urljoin(url,canon_tag.get("href")) if canon_tag and canon_tag.get("href") else "","language":s.html.get("lang","") if s.html else "","headings":{f"h{i}":[x.get_text(" ",strip=True) for x in s.find_all(f"h{i}")[:60]] for i in range(1,7)},"word_count":len(re.findall(r"\b\w+\b",text)),"text":text[:80000],"emails":sorted(set(re.findall(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",html))),"phone_candidates":sorted(set(re.findall(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)",text)))[:60],"social_profiles":list({x["url"]:x for x in socials}.values()),"links":list({x["url"]:x for x in links}.values()),"assets":assets[:250],"fetched_at":datetime.now(timezone.utc).isoformat(),"bytes":len(r.content)}
class Crawl(BaseModel):
    url:str=Field(min_length=8,max_length=2048)
    max_pages:int=Field(default=50,ge=1,le=300)
    include_subdomains:bool=False
    respect_robots:bool=True
async def execute(jid,req):
    job=JOBS[jid]; start=time.monotonic()
    try:
        first=normalize(req.url); host=urlparse(first).hostname; origin=f"{urlparse(first).scheme}://{urlparse(first).netloc}"
        q=deque([first]); seen=set(); pages=[]; errors=[]; emails=set(); socials={}
        async with httpx.AsyncClient(timeout=12,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml;q=0.9,*/*;q=0.4"},limits=httpx.Limits(max_connections=5)) as c:
            rp=await robots(c,origin) if req.respect_robots else None
            job.update(status="running",root_url=first)
            while q and len(pages)<req.max_pages:
                u=canon(q.popleft())
                if u in seen: continue
                seen.add(u)
                if not scope(u,host,req.include_subdomains): continue
                if rp and not rp.can_fetch(UA,u): job["skipped"]+=1; continue
                try:
                    r=await get(c,u); ct=r.headers.get("content-type","").lower()
                    if "text/html" not in ct and "xhtml" not in ct: job["skipped"]+=1; continue
                    record=extract(u,r); pages.append(record); emails.update(record["emails"])
                    for x in record["social_profiles"]: socials[x["url"]]=x
                    if r.status_code<400:
                        for link in record["links"]:
                            target=canon(link["url"])
                            if scope(target,host,req.include_subdomains) and target not in seen and len(q)+len(seen)<req.max_pages*8: q.append(target)
                except Exception as e: errors.append({"url":u,"error":str(e)[:250]})
                job.update(pages_found=len(pages),pages_visited=len(seen),queued=len(q),emails_found=len(emails),progress=min(99,int(len(pages)*100/req.max_pages)))
                await asyncio.sleep(.05)
        job.update(status="completed",progress=100,pages=pages,errors=errors,emails=sorted(emails),social_profiles=list(socials.values()),duration_seconds=round(time.monotonic()-start,2),summary={"pages":len(pages),"emails":len(emails),"social_profiles":len(socials),"words":sum(x["word_count"] for x in pages),"errors":len(errors)})
    except Exception as e: job.update(status="failed",error=str(e)[:400])
@app.get("/",response_class=HTMLResponse)
async def home():
    try:
        with open("index.html",encoding="utf-8") as f:return f.read()
    except FileNotFoundError:return "<h1>Webscrapperzz</h1><p>Dashboard file missing.</p>"
@app.get("/health")
async def health(): return {"status":"ok","service":"Webscrapperzz Intelligence","version":"1.0.0"}
@app.post("/api/crawls",status_code=202)
async def create(req:Crawl):
    try: normalize(req.url)
    except ValueError as e: raise HTTPException(400,str(e))
    jid=str(uuid.uuid4()); JOBS[jid]={"id":jid,"url":req.url,"status":"queued","created_at":datetime.now(timezone.utc).isoformat(),"max_pages":req.max_pages,"pages_found":0,"pages_visited":0,"queued":0,"emails_found":0,"skipped":0,"progress":0,"pages":[],"errors":[]}
    asyncio.create_task(execute(jid,req)); return {"id":jid,"status":"queued"}
@app.get("/api/crawls")
async def list_jobs(): return {"items":[{k:v for k,v in j.items() if k not in ("pages","errors","emails","social_profiles")} for j in list(JOBS.values())[-100:][::-1]]}
@app.get("/api/crawls/{jid}")
async def job_detail(jid:str):
    if jid not in JOBS: raise HTTPException(404,"Crawl job not found.")
    return JOBS[jid]
@app.get("/api/crawls/{jid}/export")
async def export(jid:str,format:str=Query("json",pattern="^(json|csv|markdown)$")):
    j=JOBS.get(jid)
    if not j: raise HTTPException(404,"Crawl job not found.")
    if j["status"]!="completed": raise HTTPException(409,"Crawl is not complete.")
    if format=="json": return JSONResponse(j,headers={"Content-Disposition":f'attachment; filename="crawl-{jid}.json"'})
    if format=="csv":
        out=io.StringIO(); cols=["url","status","title","description","word_count","emails","phone_candidates","canonical_url","content_type"]
        w=csv.DictWriter(out,fieldnames=cols); w.writeheader()
        for p in j["pages"]:
            row={k:p.get(k,"") for k in cols}; row["emails"]=";".join(p["emails"]); row["phone_candidates"]=";".join(p["phone_candidates"]); w.writerow(row)
        return Response(out.getvalue(),media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="crawl-{jid}.csv"'})
    lines=[f"# Crawl report: {j.get('root_url',j['url'])}",f"Pages: {len(j['pages'])}",""]
    for p in j["pages"]: lines += [f"## {p['title'] or p['url']}",f"URL: {p['url']}",f"HTTP: {p['status']}",f"Description: {p['description']}","",p["text"][:4000],""]
    return Response("\n".join(lines),media_type="text/markdown",headers={"Content-Disposition":f'attachment; filename="crawl-{jid}.md"'})


# Recovery and diagnostics endpoints are kept in a separate module for maintainability.
from recovery import router as recovery_router
app.include_router(recovery_router)
