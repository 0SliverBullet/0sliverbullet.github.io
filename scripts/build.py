"""Build the static publications site using only Python's standard library."""
from pathlib import Path
from html import escape
from datetime import date
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://0sliverbullet.github.io'
SCHOLAR = 'https://scholar.google.com/citations?user=k6_BkxIAAAAJ&hl=en'
PUBS = json.loads((ROOT / 'publications.json').read_text(encoding='utf-8'))
e = lambda s: escape(str(s), quote=True)

def html_head(title, description, path, extra=''):
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<meta name="robots" content="index,follow">
<link rel="canonical" href="{BASE}{path}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{BASE}{path}">
<meta property="og:type" content="website">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/style.css">
{extra}</head><body>
<a class="skip-link" href="#main">Skip to content</a>'''

def authors(names):
    return ', '.join('<strong>Zubin Zheng</strong>' if n == 'Zubin Zheng' else e(n) for n in names)

def links(p, detail=False):
    parts=[]
    path=f'/publications/{p["slug"]}/'
    if not detail:
        parts.append(f'<a class="local" href="{path}">Abstract</a>')
    pdf=p.get('local_pdf') or p.get('pdf_url')
    if pdf:
        pdf_url=path+pdf if p.get('local_pdf') else pdf
        parts.append(f'<a href="{e(pdf_url)}">PDF</a>')
    parts.append(f'<a href="{e(p["url"])}">{e(p.get("source_label","Paper"))}</a>')
    if p.get('code_url'):
        parts.append(f'<a href="{e(p["code_url"])}">{e(p.get("code_label","Code"))}</a>')
    parts.append(f'<a href="{path}citation.bib">BibTeX</a>')
    return '<div class="resource-links">'+''.join(parts)+'</div>'

def bibtex(p):
    fields={'title': '{'+p.get('title_latex',p['title'])+'}', 'author': ' and '.join('{'+a+'}' if a.endswith('Team') else a for a in p['authors']), 'year': p['date'][:4]}
    kind=p.get('bibtype','article')
    if p.get('arxiv'):
        fields.update(eprint=p['arxiv'],archivePrefix='arXiv')
    if p.get('journal'): fields['journal']=p['journal']
    if p.get('booktitle'): fields['booktitle']=p['booktitle']
    for key in ['volume','number','pages','doi']:
        if p.get(key): fields[key]=p[key]
    fields['url']=p['url']
    body=',\n'.join(f'  {k} = {{{v}}}' for k,v in fields.items())
    return '@'+kind+'{'+p['bibkey']+',\n'+body+'\n}\n'

def paper(p):
    path=f'/publications/{p["slug"]}/'
    folder=ROOT/path.strip('/')
    folder.mkdir(parents=True,exist_ok=True)
    tags=[('citation_title',p['title']),('citation_publication_date',p['date'].replace('-','/'))]
    tags += [('citation_author',a) for a in p['authors']]
    for key in ['journal_title','conference_title','volume','issue','firstpage','lastpage','doi','arxiv_id','technical_report_institution']:
        value=p.get('citation_'+key)
        if value: tags.append(('citation_'+key,value))
    if p.get('doi') and not p.get('citation_doi'): tags.append(('citation_doi',p['doi']))
    if p.get('arxiv') and not p.get('citation_arxiv_id'): tags.append(('citation_arxiv_id',p['arxiv']))
    if p.get('local_pdf'): tags.append(('citation_pdf_url',BASE+path+p['local_pdf']))
    metadata='\n'.join(f'<meta name="{k}" content="{e(v)}">' for k,v in tags)
    schema={'@context':'https://schema.org','@type':'ScholarlyArticle','headline':p['title'],
            'name':p['title'],'datePublished':p['date'],'url':BASE+path,'abstract':p['abstract'],
            'author':[{'@type':'Organization' if a.endswith('Team') else 'Person','name':a} for a in p['authors']]}
    if p.get('local_pdf'): schema['encoding']={'@type':'MediaObject','encodingFormat':'application/pdf','contentUrl':BASE+path+p['local_pdf']}
    if p.get('doi'): schema['identifier']='https://doi.org/'+p['doi']
    metadata += '\n<script type="application/ld+json">'+json.dumps(schema,ensure_ascii=False).replace('<','\\u003c')+'</script>'
    content=html_head(p['title']+' | Zubin Zheng',p['abstract'][:190],path,metadata)
    content+='''<div class="wrap paper-wrap"><header class="paper-header"><a class="paper-brand" href="/">Zubin Zheng</a><nav aria-label="Main"><a href="/#publications">\u2190 Publications</a></nav></header><main id="main" class="paper-content">'''
    content+=f'<p class="paper-meta">{e(p["venue"])} <span aria-hidden="true">\u00b7</span> <time datetime="{e(p["date"])}">{e(p["date"])}</time></p>'
    content+=f'<h1>{e(p["title"])}</h1>'
    visible=p['authors'][:1] if len(p['authors'])>12 else p['authors']
    content+=f'<p class="paper-authors">{authors(visible)}</p>'+links(p,True)
    content+='<section class="abstract" aria-labelledby="abstract"><h2 id="abstract">Abstract</h2>'
    content+=''.join(f'<p>{e(para)}</p>' for para in p['abstract'].split('\n\n'))+'</section>'
    if len(p['authors'])>12:
        content+='<section class="paper-section" aria-labelledby="authors"><h2 id="authors">Authors</h2><p class="full-authors">'+authors(p['authors'])+'</p></section>'
    bib=bibtex(p)
    content+='<section class="paper-section"><details><summary class="citation-summary">Cite this paper</summary><pre class="bibtex">'+e(bib)+'</pre></details></section>'
    content+='</main><footer class="page-footer"><a href="/#publications">All publications</a></footer></div></body></html>\n'
    (folder/'index.html').write_text(content,encoding='utf-8')
    (folder/'citation.bib').write_text(bib,encoding='utf-8')

content=html_head('Zubin Zheng | Publications','Publications by Zubin Zheng, Southern University of Science and Technology.','/')
content+=f'''<div class="wrap"><header class="identity"><div><h1>Zubin Zheng</h1><p class="affiliation">Southern University of Science and Technology</p><div class="profile-links"><a href="{e(SCHOLAR)}">Google Scholar</a><a href="https://github.com/0SliverBullet">GitHub</a><a href="mailto:zhengzb2021@mail.sustech.edu.cn">Email</a></div></div><nav aria-label="Main"><a href="#publications" aria-current="page">Publications</a></nav></header><main id="main"><section id="publications" aria-labelledby="publications-title"><div class="section-heading"><h2 id="publications-title">Publications</h2><span>{len(PUBS)} papers</span></div><ol class="publication-list">'''
for p in PUBS:
    paper(p)
    names=authors(p['authors']) if len(p['authors'])<=12 else 'DeepCybo Team, including <strong>Zubin Zheng</strong>'
    content+=f'''<li class="publication-row"><div class="publication-year">{e(p['date'][:4])}</div><article><h3><a href="/publications/{p['slug']}/">{e(p['title'])}</a></h3><p class="authors">{names}</p><p class="venue"><span class="venue-label">{e(p['venue'])}</span>{e(' · '+p['venue_detail']) if p.get('venue_detail') else ''}</p>{links(p)}</article></li>'''
content+='</ol></section></main><footer class="page-footer">Zubin Zheng</footer></div></body></html>\n'
(ROOT/'index.html').write_text(content,encoding='utf-8')
urls=[BASE+'/']+[BASE+'/publications/'+p['slug']+'/' for p in PUBS]
(ROOT/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+''.join(f'  <url><loc>{e(url)}</loc></url>\n' for url in urls)+'</urlset>\n',encoding='utf-8')
(ROOT/'robots.txt').write_text('User-agent: *\nAllow: /\n\nSitemap: '+BASE+'/sitemap.xml\n',encoding='utf-8')
(ROOT/'404.html').write_text(html_head('Page not found | Zubin Zheng','Return to Zubin Zheng\u2019s publications.','/404.html')+'<main id="main" class="wrap error-page"><h1>Page not found</h1><p><a href="/">Return to publications \u2192</a></p></main></body></html>',encoding='utf-8')
print(f'Built homepage and {len(PUBS)} publication pages.')
