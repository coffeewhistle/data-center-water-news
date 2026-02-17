import json
import re
import os
from bs4 import BeautifulSoup
import config
import httpx
import asyncio
from logging_utils import log_event, classify_error

class Extractor:
    def __init__(self, api_key=None):
        self.api_key = api_key or config.ABACUS_API_KEY
        self.model_name = os.getenv("ABACUS_MODEL", "gpt-4.1-mini")
        self.chat_completions_url = os.getenv("ABACUS_CHAT_COMPLETIONS_URL", "https://api.abacus.ai/v1/chat/completions")
        
    async def extract_article_data(self, article_metadata, client):
        """
        article_metadata: dict with title, url, summary, source_name, publish_datetime
        Returns: dict matching accepted schema
        """
        title = article_metadata.get('title', '')
        summary_text = article_metadata.get('summary', '')
        article_url = article_metadata.get('url')
        source_name = article_metadata.get('source_name')
        full_text = await self.fetch_article_text(article_url, client=client) if article_url else None

        default_payload = self.extract_with_heuristics(title, summary_text, full_text, source_name)

        # Optional LLM extraction when API credentials are available.
        if not self.api_key:
            return default_payload

        system_prompt = (
            "You are a data extraction assistant specialized in data center news. "
            "Return only valid JSON and no surrounding markdown."
        )
        user_prompt = f"""
        Analyze this article:
        Title: {title}
        Summary: {summary_text}
        Full text excerpt: {(full_text or "")[:8000]}
        
        Extract the following fields in JSON:
        - summary: 2-4 sentences.
        - mentions_cooling_or_water: boolean
        - cooling_water_summary: string or null
        - people: list of {{full_name, primary_title, primary_company, lead_relevance (High/Medium/Low), notes}}
        - companies: list of {{name, sector, country, notes}}
        - country: string or null
        
        Ensure valid JSON.
        """

        llm_response = await self.call_llm(system_prompt=system_prompt, user_prompt=user_prompt, client=client)
        if not llm_response:
            return default_payload

        try:
            parsed = json.loads(llm_response)
        except json.JSONDecodeError:
            parsed = self.extract_json_from_text(llm_response)

        if not isinstance(parsed, dict):
            return default_payload

        parsed["full_text"] = full_text
        confidence = self.score_extraction(parsed)
        if confidence < 0.35:
            log_event(
                "llm_extraction_low_confidence",
                level="WARNING",
                confidence=confidence,
                title=title,
                url=article_url,
            )
            return default_payload
        return self.normalize_extraction(parsed, fallback=default_payload)

    async def fetch_article_text(self, url, client):
        resp = await self._get_with_retry(
            client,
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; dc-news-bot/1.0)"},
        )
        if resp is None:
            return None

        try:
            soup = BeautifulSoup(resp.text, "html.parser")

            for noisy in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
                noisy.decompose()

            paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
            paragraphs = [p for p in paragraphs if len(p) > 40]
            if paragraphs:
                return " ".join(paragraphs[:30])

            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc and meta_desc.get("content"):
                return meta_desc["content"].strip()
        except Exception as exc:
            log_event(
                "extract_parse_error",
                level="ERROR",
                url=url,
                error_type=type(exc).__name__,
                error_kind=classify_error(exc),
                error=str(exc),
            )
            return None

        return None

    def extract_with_heuristics(self, title, summary_text, full_text, source_name):
        text = " ".join([title or "", summary_text or "", full_text or ""])
        text_lower = text.lower()
        keyword_pattern = r"\b(cooling|cooled|chiller|chillers|water|wastewater|aquifer|evaporation|evaporative|consumption|reuse|reclaimed water)\b"
        mentions_cooling = re.search(keyword_pattern, text_lower) is not None

        summary = (summary_text or "").strip()
        if not summary:
            summary = self.first_sentences(full_text or title, max_sentences=3)
        if len(summary) > 1200:
            summary = summary[:1200].rstrip() + "..."

        cooling_summary = None
        if mentions_cooling:
            cooling_summary = self.find_keyword_sentences(text, keyword_pattern, max_sentences=2)

        companies = []
        if source_name and source_name.lower() != "unknown":
            companies.append({
                "name": source_name,
                "sector": "Media",
                "country": None,
                "notes": "Article source outlet."
            })

        inferred_companies = self.extract_company_like_names(text)
        for company in inferred_companies:
            companies.append({
                "name": company,
                "sector": "Unknown",
                "country": None,
                "notes": "Inferred from article text."
            })

        deduped_companies = []
        seen_company_names = set()
        for company in companies:
            name_key = company["name"].strip().lower()
            if name_key and name_key not in seen_company_names:
                seen_company_names.add(name_key)
                deduped_companies.append(company)

        return {
            "summary": summary or title[:500],
            "mentions_cooling_or_water": mentions_cooling,
            "cooling_water_summary": cooling_summary,
            "people": [],
            "companies": deduped_companies,
            "full_text": full_text,
            "country": "US"
        }

    async def call_llm(self, system_prompt, user_prompt, client):
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        resp = await self._post_with_retry(
            client,
            self.chat_completions_url,
            payload=payload,
            headers=headers,
        )
        if resp is None:
            return None

        try:
            data = resp.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content")
        except Exception as exc:
            log_event(
                "llm_response_parse_error",
                level="ERROR",
                error_type=type(exc).__name__,
                error_kind=classify_error(exc),
                error=str(exc),
            )
            return None

    async def _get_with_retry(self, client, url, headers=None, max_attempts=3, base_delay_seconds=1):
        for attempt in range(1, max_attempts + 1):
            try:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                return resp
            except Exception as exc:
                err_kind = classify_error(exc)
                log_event(
                    "extract_http_get_error",
                    level="ERROR",
                    attempt=attempt,
                    max_attempts=max_attempts,
                    url=url,
                    error_type=type(exc).__name__,
                    error_kind=err_kind,
                    error=str(exc),
                )
                if attempt == max_attempts or not err_kind.startswith("transient"):
                    return None
                await asyncio.sleep(base_delay_seconds * (2 ** (attempt - 1)))
        return None

    async def _post_with_retry(self, client, url, payload, headers=None, max_attempts=3, base_delay_seconds=1):
        for attempt in range(1, max_attempts + 1):
            try:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                return resp
            except Exception as exc:
                err_kind = classify_error(exc)
                log_event(
                    "extract_http_post_error",
                    level="ERROR",
                    attempt=attempt,
                    max_attempts=max_attempts,
                    url=url,
                    error_type=type(exc).__name__,
                    error_kind=err_kind,
                    error=str(exc),
                )
                if attempt == max_attempts or not err_kind.startswith("transient"):
                    return None
                await asyncio.sleep(base_delay_seconds * (2 ** (attempt - 1)))
        return None

    def extract_json_from_text(self, text):
        if not text:
            return None

        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None

        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    def normalize_extraction(self, parsed, fallback):
        people = self.normalize_people(parsed.get("people"), fallback["people"])
        companies = self.normalize_companies(parsed.get("companies"), fallback["companies"])
        normalized = {
            "summary": parsed.get("summary") if isinstance(parsed.get("summary"), str) else fallback["summary"],
            "mentions_cooling_or_water": bool(parsed.get("mentions_cooling_or_water", fallback["mentions_cooling_or_water"])),
            "cooling_water_summary": parsed.get("cooling_water_summary") if isinstance(parsed.get("cooling_water_summary"), str) else fallback["cooling_water_summary"],
            "people": people,
            "companies": companies,
            "full_text": parsed.get("full_text") if isinstance(parsed.get("full_text"), str) else fallback.get("full_text"),
            "country": parsed.get("country") if isinstance(parsed.get("country"), str) else fallback.get("country"),
        }
        if not normalized["summary"]:
            normalized["summary"] = fallback["summary"]
        return normalized

    def normalize_people(self, people, fallback):
        if not isinstance(people, list):
            return fallback
        clean = []
        for person in people:
            if not isinstance(person, dict):
                continue
            full_name = person.get("full_name")
            if not isinstance(full_name, str) or not full_name.strip():
                continue
            clean.append(
                {
                    "full_name": full_name.strip(),
                    "primary_title": person.get("primary_title") if isinstance(person.get("primary_title"), str) else None,
                    "primary_company": person.get("primary_company") if isinstance(person.get("primary_company"), str) else None,
                    "lead_relevance": person.get("lead_relevance") if person.get("lead_relevance") in {"High", "Medium", "Low"} else "Low",
                    "notes": person.get("notes") if isinstance(person.get("notes"), str) else None,
                }
            )
        return clean

    def normalize_companies(self, companies, fallback):
        if not isinstance(companies, list):
            return fallback
        clean = []
        for company in companies:
            if not isinstance(company, dict):
                continue
            name = company.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            clean.append(
                {
                    "name": name.strip(),
                    "sector": company.get("sector") if isinstance(company.get("sector"), str) else None,
                    "country": company.get("country") if isinstance(company.get("country"), str) else None,
                    "notes": company.get("notes") if isinstance(company.get("notes"), str) else None,
                }
            )
        return clean

    def score_extraction(self, parsed):
        score = 0.0
        if isinstance(parsed.get("summary"), str) and len(parsed.get("summary").strip()) >= 40:
            score += 0.35
        if isinstance(parsed.get("mentions_cooling_or_water"), bool):
            score += 0.15
        if isinstance(parsed.get("people"), list):
            score += 0.2
        if isinstance(parsed.get("companies"), list):
            score += 0.2
        if isinstance(parsed.get("country"), str) and parsed.get("country").strip():
            score += 0.1
        return score

    def first_sentences(self, text, max_sentences=3):
        if not text:
            return ""
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return " ".join(sentences[:max_sentences]).strip()

    def find_keyword_sentences(self, text, keyword_pattern, max_sentences=2):
        if not text:
            return None
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        matched = []
        for sentence in sentences:
            if re.search(keyword_pattern, sentence.lower()):
                matched.append(sentence.strip())
            if len(matched) >= max_sentences:
                break
        return " ".join(matched) if matched else None

    def extract_company_like_names(self, text):
        if not text:
            return []
        pattern = re.compile(r"\b([A-Z][A-Za-z0-9&.\-]+(?:\s+[A-Z][A-Za-z0-9&.\-]+){0,3}\s+(?:Inc|Corp|Corporation|LLC|Ltd|Group|Technologies|Technology|Energy|Utilities))\b")
        return list({m.group(1).strip() for m in pattern.finditer(text)})
