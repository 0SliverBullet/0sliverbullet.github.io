"""Validate the generated academic site and its locally hosted PDFs, offline.

Run from any directory with ``python scripts/validate.py``.  This uses only the
standard library and reports findings without printing possible secret values.
It checks publication data consistency, not the truth of bibliographic claims
or whether Google Scholar has indexed the deployed site.
"""

from collections import Counter, defaultdict
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
import json
import re
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
BASE = "https://0sliverbullet.github.io"
PHYSBRAIN_BYTES = 4_800_402
PHYSBRAIN_SHA256 = "a65e702d0e54ce9e77d7faa3c6d01854244d6a14e685e780110cce6eb2f610db"
VOID = set("area base br col embed hr img input link meta param source track wbr".split())
ERRORS = []
COUNTS = Counter()


def check(condition, message):
    COUNTS["checks"] += 1
    if not condition:
        ERRORS.append(message)


def normalized(value):
    return " ".join(str(value).split())


class Element:
    def __init__(self, tag, attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []

    def text(self):
        return "".join(c.text() if isinstance(c, Element) else c for c in self.children)

    def has_class(self, name):
        return name in self.attrs.get("class", "").split()


class Document(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.root = Element("document")
        self.stack = [self.root]
        self.elements = []
        self.feed(path.read_text(encoding="utf-8"))
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Element(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        self.elements.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)

    def find(self, tag=None, cls=None, **attrs):
        return [e for e in self.elements
                if (tag is None or e.tag == tag)
                and (cls is None or e.has_class(cls))
                and all(e.attrs.get(k) == v for k, v in attrs.items())]

    def meta(self):
        result = defaultdict(list)
        for e in self.find("meta"):
            if e.attrs.get("name"):
                result[e.attrs["name"]].append(e.attrs.get("content", ""))
        return result


def page_url(path):
    rel = path.relative_to(ROOT).as_posix()
    return BASE + "/" + (rel[:-10] if rel.endswith("index.html") else rel)


def local_target(url, origin):
    parsed = urlsplit(urljoin(origin, url))
    if parsed.scheme not in ("http", "https") or parsed.netloc != urlsplit(BASE).netloc:
        return None
    target = (ROOT / unquote(parsed.path).lstrip("/")).resolve()
    if not target.is_relative_to(ROOT):
        return None
    if parsed.path.endswith("/") or target.is_dir():
        target /= "index.html"
    return target, unquote(parsed.fragment)


def validate_publication(p, documents):
    slug = p["slug"]
    path = ROOT / "publications" / slug / "index.html"
    check(path.is_file(), f"{slug}: missing publication page")
    if path not in documents:
        return
    doc = documents[path]
    meta = doc.meta()
    url = BASE + "/publications/" + slug + "/"
    check([normalized(e.text()) for e in doc.find("h1")] == [p["title"]],
          f"{slug}: visible title differs from publication data")
    check(meta["citation_title"] == [p["title"]], f"{slug}: citation_title mismatch")
    check(meta["citation_author"] == p["authors"], f"{slug}: citation_author order/list mismatch")
    check(meta["citation_publication_date"] == [p["date"].replace("-", "/")],
          f"{slug}: citation publication date mismatch")
    check([e.attrs.get("datetime") for e in doc.find("time")] == [p["date"]],
          f"{slug}: visible publication date mismatch")
    check([e.attrs.get("href") for e in doc.find("link", rel="canonical")] == [url],
          f"{slug}: canonical URL mismatch")
    abstract_nodes = doc.find("section", cls="abstract")
    check(len(abstract_nodes) == 1, f"{slug}: needs exactly one abstract section")
    if abstract_nodes:
        section = abstract_nodes[0]
        paragraphs = [e for e in section.children if isinstance(e, Element) and e.tag == "p"]
        actual = normalized(" ".join(e.text() for e in paragraphs))
        check(actual == normalized(p["abstract"]), f"{slug}: visible abstract is incomplete or changed")
        ancestors = []
        current = section
        while current:
            ancestors.append(current)
            current = current.parent
        check(not any("hidden" in e.attrs or e.tag == "details"
                      or e.attrs.get("aria-hidden") == "true"
                      or re.search(r"display\s*:\s*none", e.attrs.get("style", ""))
                      for e in ancestors), f"{slug}: abstract is hidden or requires expansion")
    author_nodes = doc.find("p", cls="full-authors") or doc.find("p", cls="paper-authors")
    check(any(normalized(e.text()) == normalized(", ".join(p["authors"])) for e in author_nodes),
          f"{slug}: complete author list is not visible")
    for key, value in p.items():
        if key.startswith("citation_"):
            check(meta[key] == [str(value)], f"{slug}: {key} mismatch")
    if p.get("doi"):
        check(meta["citation_doi"] == [p["doi"]], f"{slug}: DOI mismatch")
    if p.get("arxiv"):
        check(meta["citation_arxiv_id"] == [p["arxiv"]], f"{slug}: arXiv ID mismatch")
    schemas = doc.find("script", type="application/ld+json")
    check(len(schemas) == 1, f"{slug}: expected one JSON-LD object")
    try:
        schema = json.loads(schemas[0].text()) if schemas else {}
    except (json.JSONDecodeError, IndexError):
        schema = {}
        check(False, f"{slug}: malformed JSON-LD")
    expected = {"@context": "https://schema.org", "@type": "ScholarlyArticle",
                "headline": p["title"], "name": p["title"], "datePublished": p["date"],
                "url": url, "abstract": p["abstract"]}
    for key, value in expected.items():
        check(schema.get(key) == value, f"{slug}: JSON-LD {key} mismatch")
    check(schema.get("author") == [
        {"@type": "Organization" if a.endswith("Team") else "Person", "name": a}
        for a in p["authors"]], f"{slug}: JSON-LD author order/list mismatch")
    if p.get("local_pdf"):
        pdf_path = path.parent / p["local_pdf"]
        pdf_url = url + p["local_pdf"]
        check(meta["citation_pdf_url"] == [pdf_url], f"{slug}: citation_pdf_url mismatch")
        check(urlsplit(pdf_url).path.rsplit("/", 1)[0] == urlsplit(url).path.rstrip("/"),
              f"{slug}: PDF and abstract are not in the same directory")
        check(schema.get("encoding") == {"@type": "MediaObject", "encodingFormat": "application/pdf",
                                         "contentUrl": pdf_url}, f"{slug}: JSON-LD PDF encoding mismatch")
        check(pdf_path.is_file(), f"{slug}: local PDF missing")
        if pdf_path.is_file():
            data = pdf_path.read_bytes()
            digest = sha256(data).hexdigest()
            check(data.startswith(b"%PDF-"), f"{slug}: local PDF is not a PDF file")
            check(b"%%EOF" in data[-1024:], f"{slug}: PDF end marker missing")
            check(len(data) < 5_000_000, f"{slug}: PDF exceeds strict 5 MB limit")
            check(len(data) == p.get("pdf_bytes"), f"{slug}: PDF byte count mismatch")
            check(digest == p.get("pdf_sha256"), f"{slug}: PDF SHA-256 mismatch")
            if slug == "physbrain-1.5":
                check(len(data) == PHYSBRAIN_BYTES and digest == PHYSBRAIN_SHA256,
                      "physbrain-1.5: PDF differs from the verified compressed deliverable")
            COUNTS["pdfs"] += 1
            print(f"PDF {slug}: {len(data):,} bytes; SHA-256 {digest}")
    else:
        check(not meta["citation_pdf_url"], f"{slug}: cross-host PDF must not use local citation_pdf_url")
    COUNTS["publications"] += 1


def main():
    pubs = json.loads((ROOT / "publications.json").read_text(encoding="utf-8"))
    check(len(pubs) == 5, "Expected exactly five publications")
    check(len({p["slug"] for p in pubs}) == len(pubs), "Duplicate publication slugs")
    documents = {p: Document(p) for p in ROOT.rglob("*.html") if ".git" not in p.parts}
    home = documents[ROOT / "index.html"]
    check([e.attrs.get("id") for e in home.find("section")] == ["publications"],
          "Homepage must have only the Publications content section")
    check(len(home.find("article")) == 5, "Homepage must contain five publication entries")
    check([normalized(e.text()) for e in home.find("h3")] == [p["title"] for p in pubs],
          "Homepage publication order/titles differ from data")
    for p in pubs:
        validate_publication(p, documents)
    check(COUNTS["pdfs"] == 4, "Expected four locally hosted PDFs")
    declared = {ROOT / "publications" / p["slug"] / p["local_pdf"] for p in pubs if p.get("local_pdf")}
    check(set(ROOT.rglob("*.pdf")) == declared, "Unexpected or missing PDF files")
    for path, doc in documents.items():
        rel = path.relative_to(ROOT).as_posix()
        ids = [e.attrs["id"] for e in doc.elements if "id" in e.attrs]
        check(len(ids) == len(set(ids)), f"{rel}: duplicate element IDs")
        check(not any("noindex" in m.lower() or "nofollow" in m.lower()
                      for m in doc.meta().get("robots", [])), f"{rel}: indexing is disabled")
        check(all(e.attrs.get("type") == "application/ld+json" for e in doc.find("script")),
              f"{rel}: unexpected executable JavaScript")
        for e in doc.elements:
            for attribute in ("href", "src"):
                value = e.attrs.get(attribute)
                if value is None:
                    continue
                parsed = urlsplit(value)
                check(not parsed.username and not parsed.password,
                      f"{rel}: URL includes credential/userinfo")
                target = local_target(value, page_url(path))
                if target is None:
                    continue
                file_path, fragment = target
                check(file_path.is_file(), f"{rel}: broken local {attribute}: {value}")
                if fragment and file_path in documents:
                    target_ids = {n.attrs.get("id") for n in documents[file_path].elements}
                    check(fragment in target_ids, f"{rel}: missing anchor: {value}")
                COUNTS["local_links"] += 1
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    sitemap = ET.parse(ROOT / "sitemap.xml")
    locations = [e.text for e in sitemap.findall("s:url/s:loc", ns)]
    expected_urls = [BASE + "/"] + [BASE + "/publications/" + p["slug"] + "/" for p in pubs]
    check(sorted(locations) == sorted(expected_urls), "Sitemap must list homepage and all publication pages exactly once")
    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    check(re.search(r"(?im)^User-agent:\s*\*\s*$", robots) is not None, "robots.txt lacks wildcard user agent")
    check(re.search(r"(?im)^Allow:\s*/\s*$", robots) is not None, "robots.txt does not allow crawling")
    check(re.search(r"(?im)^Disallow:\s*\S", robots) is None, "robots.txt has a nonempty disallow rule")
    check("Sitemap: " + BASE + "/sitemap.xml" in robots, "robots.txt sitemap URL mismatch")
    check((ROOT / ".nojekyll").is_file(), "Missing .nojekyll")
    patterns = {
        "private key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "GitHub token": r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b",
        "AWS access key": r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
        "API secret": r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b",
        "local Windows path": r"(?i)\b[A-Z]:[\\/](?:Users|zubin_zheng|Program Files)[\\/]",
        "local home path": r"/(?:Users|home)/[^\s\"'<>]+|file:///",
    }
    suffixes = {".html", ".css", ".svg", ".json", ".xml", ".txt", ".md", ".bib", ".py", ".yml", ".yaml"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.resolve() == Path(__file__).resolve():
            continue
        if path.suffix not in suffixes:
            continue
        content = path.read_text(encoding="utf-8")
        for label, pattern in patterns.items():
            check(re.search(pattern, content) is None,
                  f"{path.relative_to(ROOT).as_posix()}: possible {label} disclosure")
    if ERRORS:
        print("\nVALIDATION FAILED")
        for error in ERRORS:
            print("- " + error)
        return 1
    print(f"\nPASS: {COUNTS['checks']} checks; {COUNTS['publications']} publications; "
          f"{COUNTS['pdfs']} PDFs; {COUNTS['local_links']} local references.")
    print("Offline content/metadata checks passed. Deployment, external URLs, visual layout and Scholar indexing are separate checks.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, ET.ParseError) as exc:
        print(f"VALIDATION ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
