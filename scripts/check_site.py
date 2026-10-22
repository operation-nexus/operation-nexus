#!/usr/bin/env python3
"""Check the static site in apps/site against docs/specs/PUBLIC-SITE.md (PS-1..PS-9).

Fails on: scripts, inline handlers, iframes, forms (PS-1, PS-3); a URL on a resource, a stylesheet url() or an
@import that leaves the site (PS-2); an outbound link that is not the Discord invite or a registered handle,
or a registered handle with no link (PS-4); an email other than one on hiveplex.live (PS-5); missing lang,
viewport, title, alt text or link-preview tags (PS-6, PS-7); missing AI-placeholder credit or privacy note
(PS-8, PS-9). Stdlib only. Usage: python3 scripts/check_site.py
"""
import os
import re
import sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "apps", "site")
REGISTRY = os.path.join(ROOT, "docs", "planning", "BRAND-ACCOUNTS.md")

DISCORD = "https://discord.gg/mSaAD3GGHh"
# Platform -> (handle, host the link must be on). The handle must also appear in BRAND-ACCOUNTS (PS-4).
PLATFORMS = {
    "YouTube": ("@hiveplex", "www.youtube.com"),
    "Twitch": ("hiveplextv", "www.twitch.tv"),
    "Bluesky": ("hiveplex.bsky.social", "bsky.app"),
    "Reddit": ("u/hiveplex", "www.reddit.com"),
    "Instagram": ("project_hiveplex", "www.instagram.com"),
    "TikTok": ("@project_hiveplex", "www.tiktok.com"),
}
REQUIRED_META = ("description", "og:title", "og:description", "og:url", "og:image", "og:type", "twitter:card")
ASSET_EXT = (".html", ".css", ".svg", ".png", ".txt", ".md")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _urls(handle, host):
    """The one profile URL accepted for a registered handle."""
    if host == "bsky.app":
        return {f"https://{host}/profile/{handle}"}
    if handle.startswith("u/"):
        return {f"https://{host}/user/{handle[2:]}"}
    return {f"https://{host}/{handle}"}


class _Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []  # (tag, attrs dict)
        self.text = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, {k: (v or "") for k, v in attrs}))

    handle_startendtag = handle_starttag

    def handle_data(self, data):
        self.text.append(data)


def page_problems(html, registry):
    """Return a list of problems for one HTML page. `registry` is the text of BRAND-ACCOUNTS.md."""
    p = _Page()
    p.feed(html)
    out = []
    names = [t for t, _ in p.tags]
    for bad in ("script", "iframe", "form", "object", "embed", "base"):
        if bad in names:
            out.append(f"PS-1/PS-3: <{bad}> is not allowed")
    for tag, a in p.tags:
        for k in a:
            if k.startswith("on"):
                out.append(f"PS-3: inline handler {k}= on <{tag}>")
        if a.get("style") and re.search(r"url\(|@import", a["style"]):
            out.append("PS-2: url() or @import in an inline style")
        if tag == "meta" and a.get("http-equiv"):
            out.append("PS-2: <meta http-equiv> is not allowed")
        for k in ("src", "href", "srcset", "data", "action"):
            if re.match(r"\s*(javascript|data|vbscript):", a.get(k, ""), re.I):
                out.append(f"PS-3: {k}= uses a script or data URL")
        if tag == "link" and a.get("rel") not in ("canonical", "icon"):
            out.append(f"PS-2: <link rel={a.get('rel')!r}> is not allowed")
        for k in ("src", "srcset", "data"):
            if k in a and re.match(r"(?i)(https?:)?//", a[k]):
                out.append(f"PS-2: {k}= points off the site: {a[k]}")
        if tag == "link" and a.get("rel") == "icon" and re.match(r"(?i)(https?:)?//", a.get("href", "")):
            out.append("PS-2: icon points off the site")
        if tag == "img" and "alt" not in a:
            out.append("PS-6: <img> without alt")
    for css in re.findall(r"<style[^>]*>(.*?)</style>", html, re.S | re.I):
        if re.search(r"@import|url\(\s*['\"]?(https?:)?//", css, re.I):
            out.append("PS-2: @import or off-site url() in a stylesheet")
    root = next((a for t, a in p.tags if t == "html"), {})
    if not root.get("lang"):
        out.append("PS-6: <html> has no lang")
    if not any(t == "meta" and a.get("name") == "viewport" for t, a in p.tags):
        out.append("PS-6: no viewport meta")
    if not "".join(p.text).strip() or "title" not in names:
        out.append("PS-6: no <title>")
    if "h1" not in names:
        out.append("PS-6: no <h1>")
    have = {a.get("name") or a.get("property") for t, a in p.tags if t == "meta"}
    out += [f"PS-7: missing meta {m}" for m in REQUIRED_META if m not in have]
    # Outbound links (PS-4): the Discord invite and one link per registered handle, nothing else.
    hrefs = [a["href"] for t, a in p.tags if t == "a" and a.get("href")]
    seen = set()
    for h in hrefs:
        if h == DISCORD:
            seen.add("Discord")
            continue
        match = [n for n, (hd, host) in PLATFORMS.items() if h in _urls(hd, host)]
        if match:
            seen.add(match[0])
        elif h.startswith("mailto:"):
            continue  # judged by the PS-5 check below
        else:
            out.append(f"PS-4: outbound link is not the Discord invite or a registered handle: {h}")
    for n, (hd, _) in PLATFORMS.items():
        if hd not in registry:
            out.append(f"PS-4: handle {hd} for {n} is not in BRAND-ACCOUNTS")
        if n not in seen:
            out.append(f"PS-4: no link for {n}")
    if "Discord" not in seen:
        out.append("PS-4: no Discord invite link")
    for e in set(EMAIL.findall(html)):
        if not e.lower().endswith("@hiveplex.live"):
            out.append(f"PS-5: email address {e} is not on hiveplex.live")
    text = " ".join("".join(p.text).split()).lower()
    if "ai-made" not in text:
        out.append("PS-8: no AI-made credit")
    if "collects nothing" not in text:
        out.append("PS-9: no privacy note")
    return out


def site_problems(site=SITE, registry_path=REGISTRY):
    out = []
    with open(registry_path, encoding="utf-8") as f:
        registry = f.read()
    for dirpath, _, files in os.walk(site):
        for name in sorted(files):
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, site)
            if name.endswith((".js", ".mjs", ".woff", ".woff2", ".ttf", ".otf")):
                out.append(f"{rel}: PS-1/PS-2/PS-3: script or font file")
            elif not name.endswith(ASSET_EXT):
                out.append(f"{rel}: unexpected file type")
            if name.endswith((".svg", ".css")):
                with open(path, encoding="utf-8") as f:
                    body = f.read()
                if re.search(r"<script|\son\w+\s*=|@import|javascript:|(?:url\(|href=|src=)\s*['\"]?(?:https?:)?//", body, re.I):
                    out.append(f"{rel}: PS-1/PS-2/PS-3: script, handler or off-site reference")
            if name.endswith(".html"):
                with open(path, encoding="utf-8") as f:
                    out += [f"{rel}: {m}" for m in page_problems(f.read(), registry)]
    if not os.path.exists(os.path.join(site, "index.html")):
        out.append("apps/site/index.html is missing")
    return out


def main():
    problems = site_problems()
    for m in problems:
        print(f"site check: {m}")
    if not problems:
        print("site checks passed")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
