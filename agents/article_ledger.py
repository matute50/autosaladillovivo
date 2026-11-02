from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
from difflib import SequenceMatcher
import unicodedata


DECISION_NEW = "new"
DECISION_DUPLICATE = "duplicate"
DECISION_UPDATE = "update"

SPANISH_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "a", "al", "en", "con",
    "por", "para", "y", "o", "u", "que", "se", "su", "sus", "es", "son", "fue", "fueron", "era",
    "este", "esta", "estos", "estas", "lo", "como", "mas", "pero", "sin", "sobre", "tras", "durante",
    "hacia", "hasta", "desde", "entre", "ante", "bajo", "segun", "muy", "ya", "no", "si",
}

GENERIC_NEWS_TERMS = {
    "saladillo", "saladillense", "local", "ciudad", "partido", "provincia", "buenos", "aires",
    "argentina", "diario", "digital", "noticias", "info", "com", "portal", "hoy", "ayer", "ahora",
    "dia", "ano", "mes", "general", "municipio", "municipalidad", "vecinos", "barrio",
}

TERMINAL_STATUSES = {
    "draft",
    "processed",
    "ai_processed",
    "published",
    "duplicate",
    "suppressed",
}


def normalize_text(text):
    if not text:
        return ""
    text = str(text).lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def source_identity(article_data):
    url = (article_data.get("source_url") or "").strip().lower()
    if not url:
        return ""
    url = url.split("#", 1)[0].split("?", 1)[0]
    return url.rstrip("/")


def _first_body_text(article_data, max_chars=800):
    body = article_data.get("original_text") or article_data.get("text") or ""
    return str(body)[:max_chars]


def _title_text(article_data):
    return article_data.get("original_title") or article_data.get("title") or ""


def _ratio(left, right):
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _keywords(text):
    normalized = normalize_text(text)
    return {
        word
        for word in normalized.split()
        if len(word) > 2 and word not in SPANISH_STOPWORDS and word not in GENERIC_NEWS_TERMS
    }


def _jaccard(left, right):
    if not left or not right:
        return 0.0
    union = left.union(right)
    if not union:
        return 0.0
    return len(left.intersection(right)) / len(union)


def content_fingerprint(article_data):
    title = normalize_text(_title_text(article_data))
    body = normalize_text(article_data.get("original_text") or article_data.get("text") or "")
    payload = f"{title}\n{body}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def make_record_from_article(article_data, status=None, db_id=None):
    identity = source_identity(article_data)
    body = article_data.get("original_text") or article_data.get("text") or ""
    record = {
        "source_identity": identity,
        "source_url": article_data.get("source_url") or "",
        "title": _title_text(article_data),
        "title_norm": normalize_text(_title_text(article_data)),
        "body_length": len(body),
        "content_hash": content_fingerprint(article_data),
        "db_id": db_id if db_id is not None else article_data.get("db_id") or article_data.get("id"),
        "status": status or article_data.get("db_status") or article_data.get("status"),
        "allow_retry": False,
    }
    return record


def legacy_history_to_state(history_items, now_iso=None):
    now = parse_iso(now_iso) or datetime.now()
    state = {}

    for item in history_items or []:
        identity = source_identity(item)
        if not identity or identity in state:
            continue

        db_id = item.get("db_id") or item.get("id")
        status = item.get("db_status") or item.get("status")
        scraped_at = parse_iso(item.get("scraped_at") or item.get("created_at"))
        recent = bool(scraped_at and now - scraped_at <= timedelta(hours=48))

        if db_id or status in TERMINAL_STATUSES:
            allow_retry = False
        else:
            allow_retry = recent

        state[identity] = make_record_from_article(item, status=status, db_id=db_id)
        state[identity]["allow_retry"] = allow_retry

    return state


def retryable_source_identities(state_records):
    return [
        record.get("source_identity")
        for record in state_records
        if record.get("allow_retry")
    ]


def is_retryable_record(record):
    return bool(record and record.get("allow_retry"))


def _is_significant_update(record, article_data):
    new_title_norm = normalize_text(_title_text(article_data))
    old_title_norm = record.get("title_norm") or normalize_text(record.get("title", ""))
    title_ratio = _ratio(new_title_norm, old_title_norm)

    new_body = article_data.get("original_text") or article_data.get("text") or ""
    old_length = int(record.get("body_length") or 0)
    new_length = len(new_body)
    length_delta = abs(new_length - old_length)

    if title_ratio < 0.97:
        return True

    if old_length == 0 and new_length > 0:
        return True

    return length_delta >= 80 or length_delta >= max(80, int(old_length * 0.18))


def is_same_event(candidate, reference):
    candidate_title_norm = normalize_text(_title_text(candidate))
    reference_title_norm = normalize_text(_title_text(reference))

    if candidate_title_norm and candidate_title_norm == reference_title_norm:
        return True

    title_similarity = _ratio(candidate_title_norm, reference_title_norm)
    candidate_body_keywords = _keywords(_first_body_text(candidate))
    reference_body_keywords = _keywords(_first_body_text(reference))
    body_similarity = _jaccard(candidate_body_keywords, reference_body_keywords)
    shared_body_terms = len(candidate_body_keywords.intersection(reference_body_keywords))

    if title_similarity >= 0.88:
        return True

    if body_similarity >= 0.70:
        return True

    if title_similarity >= 0.45 and body_similarity >= 0.35 and shared_body_terms >= 4:
        return True

    if shared_body_terms >= 7 and body_similarity >= 0.25:
        return True

    return False


def classify_candidates(candidates, processed_by_url=None, recent_published=None):
    """Classify scraped candidates against local state and recently published notes."""
    processed_by_url = dict(processed_by_url or {})
    recent_published = list(recent_published or [])

    accepted = []
    duplicates = []
    results = []

    for candidate in candidates:
        result = classify_candidate(candidate, processed_by_url, recent_published + accepted)
        enriched = dict(candidate)
        enriched["source_identity"] = result["source_identity"]
        enriched["dedup_decision"] = result["decision"]
        enriched["dedup_reason"] = result["reason"]
        results.append(result)

        if result["decision"] in (DECISION_NEW, DECISION_UPDATE):
            if result["decision"] == DECISION_UPDATE and result.get("existing_db_id"):
                enriched["id"] = result["existing_db_id"]
                enriched["db_id"] = result["existing_db_id"]
                enriched["db_status"] = "update"
            accepted.append(enriched)
            if result["source_identity"]:
                processed_by_url[result["source_identity"]] = result["record"]
        else:
            if result.get("existing_db_id"):
                enriched["db_id"] = result["existing_db_id"]
            duplicates.append(enriched)
            if result["source_identity"]:
                processed_by_url[result["source_identity"]] = {
                    **result["record"],
                    "status": DECISION_DUPLICATE,
                    "db_id": result.get("existing_db_id") or result["record"].get("db_id"),
                }

    return accepted, duplicates, results


def classify_candidate(candidate, processed_by_url=None, recent_published=None):
    processed_by_url = processed_by_url or {}
    recent_published = recent_published or []

    identity = source_identity(candidate)
    record = make_record_from_article(candidate)
    result = {
        "decision": DECISION_NEW,
        "reason": "new_source_url",
        "source_identity": identity,
        "existing_db_id": None,
        "record": record,
    }

    if not identity:
        result["reason"] = "missing_source_url"
        return result

    known_record = processed_by_url.get(identity)
    if known_record:
        if is_retryable_record(known_record):
            result["reason"] = "retryable_history_entry"
            return result

        if known_record.get("content_hash") == record["content_hash"]:
            result["decision"] = DECISION_DUPLICATE
            result["reason"] = "unchanged_source_url"
            result["existing_db_id"] = known_record.get("db_id")
            result["record"] = {**known_record, **record}
            return result

        if _is_significant_update(known_record, candidate):
            result["decision"] = DECISION_UPDATE
            result["reason"] = "content_changed"
            result["existing_db_id"] = known_record.get("db_id")
            result["record"] = {**known_record, **record}
            return result

        result["decision"] = DECISION_DUPLICATE
        result["reason"] = "minor_change"
        result["existing_db_id"] = known_record.get("db_id")
        result["record"] = {**known_record, **record}
        return result

    for published in recent_published:
        if is_same_event(candidate, published):
            result["decision"] = DECISION_DUPLICATE
            result["reason"] = "same_event_already_treated"
            result["existing_db_id"] = published.get("db_id") or published.get("id")
            return result

    return result


def known_source_identities(state_records):
    """Return source identities that should block immediate rescraping."""
    return [
        record.get("source_identity")
        for record in state_records
        if record.get("source_identity") and not record.get("allow_retry")
    ]


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _write_json(path, payload):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp_path, path)


def load_article_state(data_dir, now_iso=None):
    """Load canonical article ledger, seeding it with legacy history when needed."""
    ledger_path = os.path.join(data_dir, "article_ledger.json")
    ledger = _read_json(ledger_path)
    state = {}

    if isinstance(ledger, dict):
        for key, value in ledger.items():
            if isinstance(value, dict):
                record = dict(value)
                record.setdefault("source_identity", key)
                state[record["source_identity"]] = record

    now = parse_iso(now_iso) or datetime.now()
    for filename in ("modified_articles.json", "scraped_articles.json"):
        legacy = _read_json(os.path.join(data_dir, filename))
        if not legacy:
            continue
        legacy_state = legacy_history_to_state(legacy, now_iso=now.isoformat())
        for identity, record in legacy_state.items():
            if identity not in state:
                state[identity] = record

    return state


def save_article_state(data_dir, state, processed_articles=None, duplicate_articles=None, status="draft"):
    """Persist processed and duplicate article state to ``article_ledger.json``."""
    next_state = dict(state or {})
    ledger_path = os.path.join(data_dir, "article_ledger.json")

    for article in processed_articles or []:
        identity = article.get("source_identity") or source_identity(article)
        if not identity:
            continue
        record = next_state.get(identity) or make_record_from_article(article)
        db_id = article.get("db_id") or article.get("id") or record.get("db_id")
        record_status = article.get("db_status") or status
        if record_status == "update":
            record_status = "processed"
        record = {
            **record,
            **make_record_from_article(article, status=record_status, db_id=db_id),
        }
        record["source_identity"] = identity
        record["allow_retry"] = False
        next_state[identity] = record

    for article in duplicate_articles or []:
        identity = article.get("source_identity") or source_identity(article)
        if not identity:
            continue
        record = next_state.get(identity) or make_record_from_article(article)
        record = {
            **record,
            **make_record_from_article(
                article,
                status=DECISION_DUPLICATE,
                db_id=article.get("db_id") or article.get("existing_db_id") or record.get("db_id"),
            ),
        }
        record["source_identity"] = identity
        record["allow_retry"] = False
        next_state[identity] = record

    _write_json(ledger_path, next_state)
    Path(ledger_path).touch()
    return next_state
