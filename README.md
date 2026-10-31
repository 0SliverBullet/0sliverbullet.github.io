# Zubin Zheng — Publications

Personal academic homepage: https://0sliverbullet.github.io/

The homepage contains one Publications section and all five papers from the author's Google Scholar profile. Each paper has a static HTML page with its complete abstract, authors, publication information, source links, and BibTeX.

## Updating the site

Edit `publications.json`, then regenerate the HTML, BibTeX, sitemap and robots file:

```sh
python scripts/build.py
python scripts/validate.py
```

Commit the generated files and push to `main`. GitHub Pages serves the repository root; `.nojekyll` disables Jekyll processing. The site has no JavaScript runtime, analytics or external font dependency.

## Paper files and attribution

Paper authors retain their rights; no blanket license is applied to publication text or PDFs. Publication records retain source and license information. The IEEE paper's linked/hosted PDF is the author accepted manuscript, not the publisher's version of record. Other papers link to their original arXiv, PMLR or OpenReview records.

PhysBrain 1.5 is hosted at `/publications/physbrain-1.5/paper.pdf`. This is the user-supplied, compressed 37-page version: 4,800,402 bytes, SHA-256 `a65e702d0e54ce9e77d7faa3c6d01854244d6a14e685e780110cce6eb2f610db`. Its searchable text, bookmarks and links were preserved during image compression.

## Scholar discoverability

The publication pages provide visible abstracts and `citation_title`, one `citation_author` per author, and `citation_publication_date`. Locally hosted PDF files are linked through absolute `citation_pdf_url` metadata and live in the same directory as their abstract page. The homepage uses ordinary HTML links, and the site includes a sitemap and permissive robots file.

These choices follow [Google Scholar's inclusion guidelines](https://scholar.google.com/intl/en/scholar/inclusion.html). They create an accessible indexing source but do not guarantee inclusion or a particular indexing date.
