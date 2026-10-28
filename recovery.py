import ipaddress
import re
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse, quote

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()
UA = "Webscrapperzz-Recovery/1.0 (public-site diagnostics)"
TIMEOUT = httpx.Timeout(12.0, connect=5.0)


class RecoveryRequest(BaseModel):
    url: str = Field(min_length=4, max_length=2048)
    inspect_sitemaps: bool = True
    archive_lookup: bool = True


def parse_target(raw: str):
    raw = raw.strip()
    if "://" not in raw:
        raw = "https://" + raw
    p = urlparse(raw)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise ValueError("Enter a valid HTTP or HTTPS website URL.")
    if p.hostname.lower() == "localhost" or p.hostname.lower().endswith((".local", ".localhost")):
        raise ValueError("Local network targets are not allowed.")
    return urlunparse((p.scheme, p.netloc.lower(), p.path or "/", "", p.query, ""))


def public_addresses(host, port):
    records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses = sorted(set(item[4][0].split("%")[0] for item in records))
    for address in addresses:
        if not ipaddress.ip_address(address).is_global:
            raise ValueError("Target resolves to a non-public address; outbound request blocked.")
    return addresses


async def archive_lookup(client, target):
    result = {"available": False, "snapshot_url": None, "timestamp": None, "snapshots": []}
    try:
        endpoint = "https://archive.org/wayback/available?url=" + quote(target, safe=":/?")
        response = await client.get(endpoint)
        if response.status_code == 200:
            closest = response.json().get("archived_snapshots", {}).get("closest", {})
            if closest.get("available"):
                result.update(available=True, snapshot_url=closest.get("url"), timestamp=closest.get("timestamp"))
        host_path = urlparse(target).netloc + "/*"
        cdx_url = "https://web.archive.org/cdx/search/cdx?url=" + quote(host_path, safe="/*") + "&output=json&filter=statuscode:200&filter=mimetype:text/html&fl=timestamp,original,statuscode,digest&collapse=urlkey&limit=100"
        cdx = await client.get(cdx_url)
        if cdx.status_code == 200:
            rows = cdx.json()
            if rows and len(rows) > 1:
                result["snapshots"] = [
                    {"timestamp": row[0], "original_url": row[1], "status": row[2], "digest": row[3],
                     "archive_url": "https://web.archive.org/web/" + row[0] + "/" + row[1]}
                    for row in rows[1:] if len(row) >= 4
                ]
                if not result["snapshot_url"] and result["snapshots"]:
                    result.update(available=True, snapshot_url=result["snapshots"][0]["archive_url"],
                                  timestamp=result["snapshots"][0]["timestamp"])
    except Exception as exc:
        result["lookup_error"] = str(exc)[:180]
    return result


@router.post("/api/recover")
async def recover_site(request: RecoveryRequest):
    try:
        target = parse_target(request.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    parsed = urlparse(target)
    report = {
        "url": target, "host": parsed.hostname,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "dns": {"resolved": False, "addresses": []},
        "live_checks": [], "sitemaps": [], "archive": None,
        "interpretation": [],
        "limitations": [
            "A dead server cannot provide current live content. Archive snapshots are historical and may be incomplete.",
            "This tool does not bypass logins, paywalls, CAPTCHAs, or other access controls.",
            "A failed request is not proof that a website is permanently offline."
        ]
    }
    try:
        addresses = public_addresses(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        report["dns"] = {"resolved": True, "addresses": addresses}
    except socket.gaierror as exc:
        report["dns"] = {"resolved": False, "error": str(exc)[:180]}
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        report["dns"] = {"resolved": False, "error": str(exc)[:180]}

    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": UA}, follow_redirects=False) as client:
        # Do not make requests to an unresolved hostname or follow its redirects.
        if report["dns"]["resolved"]:
            schemes = list(dict.fromkeys([parsed.scheme, "https" if parsed.scheme == "http" else "http"]))
            for scheme in schemes:
                url = urlunparse((scheme, parsed.netloc, parsed.path or "/", "", parsed.query, ""))
                try:
                    response = await client.get(url)
                    report["live_checks"].append({
                        "url": url, "status": response.status_code,
                        "redirect_location": response.headers.get("location"),
                        "content_type": response.headers.get("content-type"),
                        "server": response.headers.get("server"),
                        "last_modified": response.headers.get("last-modified"),
                        "bytes": len(response.content)
                    })
                except Exception as exc:
                    report["live_checks"].append({"url": url, "error": str(exc)[:200]})
            if request.inspect_sitemaps:
                for path in ("/robots.txt", "/sitemap.xml", "/sitemap_index.xml"):
                    url = parsed.scheme + "://" + parsed.netloc + path
                    try:
                        response = await client.get(url)
                        entry = {"url": url, "status": response.status_code,
                                 "content_type": response.headers.get("content-type")}
                        if path == "/robots.txt" and response.status_code == 200:
                            entry["sitemap_urls"] = re.findall(r"(?im)^\s*Sitemap:\s*(\S+)", response.text)[:20]
                        if "sitemap" in path and response.status_code == 200:
                            xml = BeautifulSoup(response.text[:1000000], "xml")
                            entry["urls"] = [node.get_text(strip=True) for node in xml.find_all("loc")[:100]]
                        report["sitemaps"].append(entry)
                    except Exception as exc:
                        report["sitemaps"].append({"url": url, "error": str(exc)[:160]})
        if request.archive_lookup:
            report["archive"] = await archive_lookup(client, target)

    live_ok = any(item.get("status", 0) < 500 for item in report["live_checks"])
    if not report["dns"]["resolved"]:
        report["interpretation"].append("The hostname did not resolve during this check; archive lookup may still find historical copies.")
    elif not live_ok:
        report["interpretation"].append("Live HTTP checks failed or returned server errors. Check DNS, hosting, TLS, and redirects.")
    if report.get("archive", {}).get("available"):
        report["interpretation"].append("Historical snapshots were found. Open the snapshot URL to inspect archived content.")
    else:
        report["interpretation"].append("No usable snapshot was surfaced by the archive lookup; other archives or backups may still exist.")
    return report
