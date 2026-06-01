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
    """Comprueba si alguna de las palabras clave aparece en el texto"""
    if not text:
        return False
    text_lower = text.lower()
    # Divide las keywords por comas y comprueba cada una
    keyword_list = [kw.strip().lower() for kw in keywords.split(",")]
    for kw in keyword_list:
        if kw and kw in text_lower:
            return True
    return False


def is_relevant(article, keywords):
    """Devuelve True si el artículo tiene las keywords en título o abstract"""
    title = article.get("title", "")
    abstract = article.get("abstract", "")
    in_title = contains_keywords(title, keywords)
    in_abstract = contains_keywords(abstract, keywords)
    if in_title:
        print(f"✅ Relevante (título): {title[:60]}")
    elif in_abstract:
        print(f"✅ Relevante (abstract): {title[:60]}")
    else:
        print(f"❌ Descartado (no contiene keywords): {title[:60]}")
    return in_title or in_abstract


def get_open_access_pdf(doi, email):
    """Busca PDF gratuito usando Unpaywall"""
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


def search_pubmed(keywords, year_start, year_end):
    results = []
    try:
        # Búsqueda específica en título y abstract
        query = f"{keywords}[Title/Abstract] AND {year_start}:{year_end}[pdat]"
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
                abstract = str(art.get("Abstract", {}).get("AbstractText", [""])[0])
                year = str(med.get("DateCompleted", {}).get("Year", year_start))
                pmid = str(med["PMID"])

                doi = None
                id_list = art.get("ELocationID", [])
                for loc in id_list:
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

                # Solo añadir si contiene las keywords en título o abstract
                if is_relevant(candidate, keywords):
                    results.append(candidate)

            except Exception as e:
                continue

    except Exception as e:
        print(f"Error PubMed: {e}")
    return results


def search_scopus(keywords, year_start, year_end):
    results = []
    try:
        url = "https://api.elsevier.com/content/search/scopus"
        headers = {"X-ELS-APIKey": ELSEVIER_API_KEY, "Accept": "application/json"}
        params = {
            # Búsqueda específica en título y abstract
            "query": f"TITLE-ABS({keywords}) AND PUBYEAR > {int(year_start)-1} AND PUBYEAR < {int(year_end)+1}",
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
            abstract = entry.get("dc:description", "No disponible")
            doi = entry.get("prism:doi", "")

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

            # Solo añadir si contiene las keywords en título o abstract
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
        params = {
            "query": keywords,
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
            abstract = entry.get("dc:description", "No disponible")
            doi = entry.get("prism:doi", "")

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

            # Solo añadir si contiene las keywords en título o abstract
            if is_relevant(candidate, keywords):
                results.append(candidate)

    except Exception as e:
        print(f"Error ScienceDirect: {e}")
    return results


def search_all_databases(keywords, year_start, year_end):
    print(f"\nBuscando: '{keywords}' ({year_start}-{year_end})")
    print("=" * 50)
    results = []
    results += search_pubmed(keywords, year_start, year_end)
    results += search_scopus(keywords, year_start, year_end)
    results += search_sciencedirect(keywords, year_start, year_end)
    print(f"\nTotal artículos relevantes encontrados: {len(results)}")
    print("=" * 50)
    return results