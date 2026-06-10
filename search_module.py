import os
import urllib.parse
import requests
from Bio import Entrez
from dotenv import load_dotenv

load_dotenv()

PUBMED_API_KEY = os.getenv("PUBMED_API_KEY")
ELSEVIER_API_KEY = os.getenv("ELSEVIER_API_KEY")
YOUR_EMAIL = os.getenv("YOUR_EMAIL", "tu_email@gmail.com")

Entrez.email = YOUR_EMAIL
Entrez.api_key = PUBMED_API_KEY


def contains_keywords(text, keywords):
    if not text:
        return False
    text_lower = text.lower()
    keyword_list = [kw.strip().lower() for kw in keywords.split(",")]
    for kw in keyword_list:
        if kw and kw in text_lower:
            return True
    return False


def is_relevant(article, keywords):
    title = article.get("title", "")
    abstract = article.get("abstract", "")
    in_title = contains_keywords(title, keywords)
    in_abstract = contains_keywords(abstract, keywords)
    if in_title:
        print(f"✅ Relevante (título): {title[:60]}")
    elif in_abstract:
        print(f"✅ Relevante (abstract): {title[:60]}")
    else:
        print(f"❌ Descartado: {title[:60]}")
    return in_title or in_abstract


# ─── Fuentes de PDF ────────────────────────────────────────────────────────────

def get_pdf_unpaywall(doi, email):
    """Busca PDF via Unpaywall usando el DOI."""
    try:
        url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            best = response.json().get("best_oa_location")
            if best:
                pdf_url = best.get("url_for_pdf") or best.get("url")
                if pdf_url:
                    print(f"  Unpaywall: {pdf_url}")
                    return pdf_url
    except Exception as e:
        print(f"  Error Unpaywall: {e}")
    return None


def get_pdf_pmc(pmid):
    """Convierte PMID a PMCID y construye URL directa al PDF en PubMed Central."""
    try:
        conv_url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={pmid}&format=json"
        response = requests.get(conv_url, timeout=10)
        if response.status_code == 200:
            records = response.json().get("records", [])
            if records:
                pmcid = records[0].get("pmcid")
                if pmcid:
                    pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
                    print(f"  PubMed Central: {pdf_url}")
                    return pdf_url
    except Exception as e:
        print(f"  Error PubMed Central: {e}")
    return None


def get_pdf_europe_pmc(doi=None, pmid=None):
    """Busca PDF en Europe PMC usando DOI o PMID."""
    try:
        if doi:
            query = f"DOI:{doi}"
        elif pmid:
            query = f"EXT_ID:{pmid} AND SRC:MED"
        else:
            return None
        url = (
            f"https://www.ebi.ac.uk/europepmc/webservices/rest/search"
            f"?query={urllib.parse.quote(query)}&format=json&resultType=core"
        )
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            results = response.json().get("resultList", {}).get("result", [])
            if results:
                pmcid = results[0].get("pmcid")
                if pmcid:
                    pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf"
                    print(f"  Europe PMC: {pdf_url}")
                    return pdf_url
    except Exception as e:
        print(f"  Error Europe PMC: {e}")
    return None


def get_pdf_semantic_scholar(doi=None, title=None):
    """Busca PDF en Semantic Scholar usando DOI o título como fallback."""
    try:
        if doi:
            url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=openAccessPdf"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                oa = response.json().get("openAccessPdf")
                if oa and oa.get("url"):
                    print(f"  Semantic Scholar (DOI): {oa['url']}")
                    return oa["url"]
        if title:
            search_url = (
                f"https://api.semanticscholar.org/graph/v1/paper/search"
                f"?query={urllib.parse.quote(title)}&fields=openAccessPdf&limit=1"
            )
            response = requests.get(search_url, timeout=10)
            if response.status_code == 200:
                papers = response.json().get("data", [])
                if papers:
                    oa = papers[0].get("openAccessPdf")
                    if oa and oa.get("url"):
                        print(f"  Semantic Scholar (título): {oa['url']}")
                        return oa["url"]
    except Exception as e:
        print(f"  Error Semantic Scholar: {e}")
    return None


def find_pdf_url(doi=None, pmid=None, title=None, email=None):
    """
    Busca PDF en acceso abierto probando múltiples fuentes en cadena:
    Unpaywall → PubMed Central → Europe PMC → Semantic Scholar
    """
    print(f"  Buscando PDF — DOI: {doi or '-'} | PMID: {pmid or '-'}")

    if doi and email:
        url = get_pdf_unpaywall(doi, email)
        if url:
            return url

    if pmid:
        url = get_pdf_pmc(pmid)
        if url:
            return url

    if doi or pmid:
        url = get_pdf_europe_pmc(doi=doi, pmid=pmid)
        if url:
            return url

    if doi or title:
        url = get_pdf_semantic_scholar(doi=doi, title=title)
        if url:
            return url

    print("  Sin PDF en acceso abierto encontrado")
    return None


# ─── Elsevier abstract completo ────────────────────────────────────────────────

def get_full_abstract_elsevier(doi, api_key):
    """Obtiene el abstract completo via Elsevier Abstract Retrieval API cuando el de búsqueda viene truncado."""
    if not doi or not api_key:
        return ""
    try:
        url = f"https://api.elsevier.com/content/abstract/doi/{doi}"
        headers = {"X-ELS-APIKey": api_key, "Accept": "application/json"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            abstract = (
                response.json()
                .get("abstracts-retrieval-response", {})
                .get("coredata", {})
                .get("dc:description", "")
            )
            if abstract:
                print(f"Abstract completo obtenido ({len(abstract)} chars)")
                return abstract
    except Exception as e:
        print(f"Error obteniendo abstract Elsevier: {e}")
    return ""


# ─── Búsqueda en bases de datos ────────────────────────────────────────────────

def search_pubmed(keywords, year_start, year_end):
    results = []
    try:
        keyword_list = [kw.strip() for kw in keywords.split(",") if kw.strip()]
        term_parts = " OR ".join([f'("{kw}"[Title/Abstract])' for kw in keyword_list])
        query = f"({term_parts}) AND {year_start}:{year_end}[pdat]"
        print(f"PubMed query: {query}")

        handle = Entrez.esearch(db="pubmed", term=query, retmax=20)
        record = Entrez.read(handle)
        ids = record["IdList"]

        if not ids:
            print("PubMed: sin resultados")
            return []

        handle2 = Entrez.efetch(db="pubmed", id=",".join(ids), rettype="abstract", retmode="xml")
        records = Entrez.read(handle2)

        for article in records["PubmedArticle"]:
            try:
                med = article["MedlineCitation"]
                art = med["Article"]
                title = str(art.get("ArticleTitle", "Sin título"))
                authors_list = art.get("AuthorList", [])
                authors = ", ".join([
                    a.get("LastName", "") + " " + a.get("ForeName", "")
                    for a in authors_list[:3] if "LastName" in a
                ])
                abstract_parts = art.get("Abstract", {}).get("AbstractText", [""])
                abstract = " ".join([str(p) for p in abstract_parts])
                year = str(med.get("DateCompleted", {}).get("Year", year_start))
                pmid = str(med["PMID"])

                doi = None
                for loc in art.get("ELocationID", []):
                    if loc.attributes.get("EIdType") == "doi":
                        doi = str(loc)
                        break

                pdf_url = find_pdf_url(doi=doi, pmid=pmid, title=title, email=YOUR_EMAIL)
                fallback_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

                candidate = {
                    "title": title,
                    "authors": authors,
                    "abstract": abstract,
                    "year": year,
                    "source": "PubMed",
                    "url": pdf_url or fallback_url,
                    "doi": doi,
                    "pmid": pmid,
                    "has_pdf": pdf_url is not None
                }

                if is_relevant(candidate, keywords):
                    results.append(candidate)

            except Exception:
                continue

    except Exception as e:
        print(f"Error PubMed: {e}")
    return results


def search_scopus(keywords, year_start, year_end):
    results = []
    try:
        url = "https://api.elsevier.com/content/search/scopus"
        headers = {"X-ELS-APIKey": ELSEVIER_API_KEY, "Accept": "application/json"}

        keyword_list = [kw.strip() for kw in keywords.split(",") if kw.strip()]
        term_parts = " OR ".join([f'TITLE-ABS("{kw}")' for kw in keyword_list])
        query = f"({term_parts}) AND PUBYEAR > {int(year_start)-1} AND PUBYEAR < {int(year_end)+1}"
        print(f"Scopus query: {query}")

        params = {
            "query": query,
            "count": 20,
            "field": "dc:title,dc:creator,prism:coverDate,dc:description,prism:doi"
        }
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        entries = data.get("search-results", {}).get("entry", [])

        for entry in entries:
            title = entry.get("dc:title", "Sin título")
            author = entry.get("dc:creator", "Desconocido")
            year = entry.get("prism:coverDate", "?")[:4]
            abstract = entry.get("dc:description", "")
            doi = entry.get("prism:doi", "")

            if len(abstract) < 100 and doi:
                full = get_full_abstract_elsevier(doi, ELSEVIER_API_KEY)
                if full:
                    abstract = full

            pdf_url = find_pdf_url(doi=doi, title=title, email=YOUR_EMAIL)

            candidate = {
                "title": title,
                "authors": author,
                "abstract": abstract,
                "year": year,
                "source": "Scopus",
                "url": pdf_url or (f"https://doi.org/{doi}" if doi else ""),
                "doi": doi,
                "has_pdf": pdf_url is not None
            }

            if is_relevant(candidate, keywords):
                results.append(candidate)

    except Exception as e:
        print(f"Error Scopus: {e}")
    return results


def search_sciencedirect(keywords, year_start, year_end):
    results = []
    try:
        url = "https://api.elsevier.com/content/search/sciencedirect"
        headers = {"X-ELS-APIKey": ELSEVIER_API_KEY, "Accept": "application/json"}

        keyword_list = [kw.strip() for kw in keywords.split(",") if kw.strip()]
        term_parts = " OR ".join([f'TITLE-ABS-KEY("{kw}")' for kw in keyword_list])
        print(f"ScienceDirect query: {term_parts}")

        params = {
            "query": term_parts,
            "date": f"{year_start}-{year_end}",
            "count": 20,
            "field": "dc:title,authors,prism:coverDate,dc:description,prism:doi"
        }
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        entries = data.get("search-results", {}).get("entry", [])

        for entry in entries:
            title = entry.get("dc:title", "Sin título")
            author = entry.get("authors", "Desconocido")
            year = entry.get("prism:coverDate", "?")[:4]
            abstract = entry.get("dc:description", "")
            doi = entry.get("prism:doi", "")

            if len(abstract) < 100 and doi:
                full = get_full_abstract_elsevier(doi, ELSEVIER_API_KEY)
                if full:
                    abstract = full

            pdf_url = find_pdf_url(doi=doi, title=title, email=YOUR_EMAIL)

            candidate = {
                "title": title,
                "authors": author,
                "abstract": abstract,
                "year": year,
                "source": "ScienceDirect",
                "url": pdf_url or (f"https://doi.org/{doi}" if doi else ""),
                "doi": doi,
                "has_pdf": pdf_url is not None
            }

            if is_relevant(candidate, keywords):
                results.append(candidate)

    except Exception as e:
        print(f"Error ScienceDirect: {e}")
    return results


def search_all_databases(keywords, year_start, year_end):
    print(f"\nBuscando: '{keywords}' ({year_start}-{year_end})")
    print("=" * 50)
    all_results = []
    all_results += search_pubmed(keywords, year_start, year_end)
    all_results += search_scopus(keywords, year_start, year_end)
    all_results += search_sciencedirect(keywords, year_start, year_end)

    seen_dois = set()
    unique_results = []
    for r in all_results:
        doi = r.get("doi", "")
        if doi and doi in seen_dois:
            print(f"Duplicado eliminado: {r['title'][:60]}")
            continue
        if doi:
            seen_dois.add(doi)
        unique_results.append(r)

    duplicates = len(all_results) - len(unique_results)
    print(f"\nTotal artículos relevantes: {len(unique_results)} ({duplicates} duplicados eliminados)")
    print("=" * 50)
    return unique_results
