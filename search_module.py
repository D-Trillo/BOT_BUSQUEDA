import os
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


def get_open_access_pdf(doi, email):
    if not doi:
        return None
    try:
        url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            best = data.get("best_oa_location")
            if best:
                pdf_url = best.get("url_for_pdf") or best.get("url")
                if pdf_url:
                    print(f"Unpaywall encontró PDF: {pdf_url}")
                    return pdf_url
    except Exception as e:
        print(f"Error Unpaywall: {e}")
    return None


def get_full_abstract_elsevier(doi, api_key):
    """Obtiene el abstract completo via Elsevier Abstract Retrieval API cuando el de búsqueda viene truncado."""
    if not doi or not api_key:
        return ""
    try:
        url = f"https://api.elsevier.com/content/abstract/doi/{doi}"
        headers = {"X-ELS-APIKey": api_key, "Accept": "application/json"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            abstract = (
                data.get("abstracts-retrieval-response", {})
                    .get("coredata", {})
                    .get("dc:description", "")
            )
            if abstract:
                print(f"Abstract completo obtenido ({len(abstract)} chars)")
                return abstract
    except Exception as e:
        print(f"Error obteniendo abstract Elsevier: {e}")
    return ""


def search_pubmed(keywords, year_start, year_end):
    results = []
    try:
        # Aplica [Title/Abstract] a cada keyword por separado y los une con OR
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
                # Captura todas las secciones del abstract (structured abstracts)
                abstract_parts = art.get("Abstract", {}).get("AbstractText", [""])
                abstract = " ".join([str(p) for p in abstract_parts])

                year = str(med.get("DateCompleted", {}).get("Year", year_start))
                pmid = str(med["PMID"])

                doi = None
                for loc in art.get("ELocationID", []):
                    if loc.attributes.get("EIdType") == "doi":
                        doi = str(loc)
                        break

                pdf_url = get_open_access_pdf(doi, YOUR_EMAIL) if doi else None
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

        # Aplica TITLE-ABS a cada keyword por separado y los une con OR
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

            # Si el abstract viene vacío o truncado, obtener el completo
            if len(abstract) < 100 and doi:
                full = get_full_abstract_elsevier(doi, ELSEVIER_API_KEY)
                if full:
                    abstract = full

            pdf_url = get_open_access_pdf(doi, YOUR_EMAIL) if doi else None

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

        # Aplica TITLE-ABS-KEY a cada keyword por separado y los une con OR
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

            # Si el abstract viene vacío o truncado, obtener el completo
            if len(abstract) < 100 and doi:
                full = get_full_abstract_elsevier(doi, ELSEVIER_API_KEY)
                if full:
                    abstract = full

            pdf_url = get_open_access_pdf(doi, YOUR_EMAIL) if doi else None

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

    # Deduplicación por DOI (artículos que aparecen en varias fuentes)
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
