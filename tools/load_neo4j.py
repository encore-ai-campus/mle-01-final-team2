"""Load the internal IBK regulations into Neo4j (idempotent, T1 scope).

Usage:
    .venv/Scripts/python.exe tools/load_neo4j.py

This first stage loads regulation documents, chapters, articles, numbered
paragraphs (clauses), internal references, and citation stubs. It deliberately
does not load all 275 laws or unreviewed obligation/exception candidates.
"""

from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv
from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "ibk_converted" / "parsed"
BATCH_SIZE = 500


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"\([^)]*\)", "", value)
    return re.sub(r"[\s·ㆍ,，'\"“”‘’]", "", value)


def batched(values: list[dict[str, Any]], size: int = BATCH_SIZE) -> Iterable[list[dict[str, Any]]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def run_batches(session, query: str, rows: list[dict[str, Any]]) -> None:
    for batch in batched(rows):
        session.run(query, rows=batch).consume()


def authority_rank(doc: dict[str, Any]) -> int:
    title = doc.get("title", "")
    doc_type = doc.get("doc_type") or ""
    if title.replace(" ", "") == "정관":
        return 6
    if any(token in doc_type or token in title for token in ("세칙", "지침", "운용기준", "기준", "운영기준")):
        return 8
    return 7


def load_documents() -> list[dict[str, Any]]:
    if not SOURCE_DIR.is_dir():
        raise FileNotFoundError(f"Regulation JSON directory not found: {SOURCE_DIR}")
    result = []
    for path in sorted(SOURCE_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        doc = payload["doc"]
        doc_id = doc["id"]
        result.append({"path": path, "payload": payload, "doc": doc, "doc_id": doc_id})
    if not result:
        raise RuntimeError(f"No JSON files found under {SOURCE_DIR}")
    return result


def build_rows(documents: list[dict[str, Any]]):
    docs: list[dict[str, Any]] = []
    chapters: list[dict[str, Any]] = []
    articles: list[dict[str, Any]] = []
    clauses: list[dict[str, Any]] = []
    internal_refs: list[dict[str, Any]] = []
    external_refs: list[dict[str, Any]] = []
    chapter_articles: list[dict[str, Any]] = []
    document_articles: list[dict[str, Any]] = []
    title_to_doc: dict[str, str] = {}

    for entry in documents:
        doc = entry["doc"]
        title_to_doc[normalize_name(doc["title"])] = entry["doc_id"]

    for entry in documents:
        payload, doc, doc_id = entry["payload"], entry["doc"], entry["doc_id"]
        docs.append({
            "doc_id": doc_id,
            "title": doc.get("title") or doc_id,
            "source_kind": "internal",
            "doc_type": doc.get("doc_type"),
            "authority_rank": authority_rank(doc),
            "effective_date": doc.get("date"),
            "date_missing": not bool(doc.get("date")),
            "action": doc.get("action"),
            "source": doc.get("source"),
            "file": doc.get("file") or entry["path"].name,
            "format": doc.get("format"),
        })

        chapter_ids: dict[tuple[str | None, str | None], str] = {}
        chapter_occurrences: dict[str, int] = defaultdict(int)
        for chapter_index, chapter in enumerate(payload.get("chapters", [])):
            no, part = chapter.get("no"), chapter.get("part")
            base_id = f"{doc_id}#{part + '-' if part else ''}{no or 'chapter-' + str(len(chapter_ids) + 1)}"
            chapter_occurrences[base_id] += 1
            occurrence = chapter_occurrences[base_id]
            chapter_id = base_id if occurrence == 1 else f"{base_id}~{occurrence}"
            chapter_ids[(no, part)] = chapter_id
            chapters.append({
                "id": chapter_id,
                "doc_id": doc_id,
                "no": no,
                "title": chapter.get("title"),
                "kind": chapter.get("kind"),
                "part": part,
                "source_index": chapter_index,
                "duplicate_no_occurrence": occurrence,
            })

        for article in payload.get("articles", []):
            article_id = article["id"]
            chapter_id = chapter_ids.get((article.get("chapter"), article.get("part")))
            articles.append({
                "id": article_id,
                "doc_id": doc_id,
                "no": article.get("no"),
                "title": article.get("title"),
                "text": article.get("text") or "",
                "head_text": article.get("head_text"),
                "deleted": bool(article.get("deleted", False)),
                "part": article.get("part"),
                "chapter_no": article.get("chapter"),
                "chapter_id": chapter_id,
                "source_kind": "internal",
                "authority_rank": authority_rank(doc),
            })
            if chapter_id:
                chapter_articles.append({"chapter_id": chapter_id, "article_id": article_id})
            else:
                document_articles.append({"doc_id": doc_id, "article_id": article_id})
            ordinal = 0
            clause_occurrences: dict[int, int] = defaultdict(int)
            for paragraph in article.get("paragraphs", []):
                no = paragraph.get("no")
                if no is None:
                    continue
                ordinal += 1
                # The graph key uses Arabic numerals for standard circled numbers.
                numeral = ord(no) - ord("①") + 1 if len(no) == 1 and "①" <= no <= "⑳" else ordinal
                clause_occurrences[numeral] += 1
                occurrence = clause_occurrences[numeral]
                clause_id = f"{article_id}#{numeral}" if occurrence == 1 else f"{article_id}#{numeral}~{occurrence}"
                clause_text = paragraph.get("text") or ""
                if not clause_text and paragraph.get("items"):
                    clause_text = "\n".join(item.get("text", "") for item in paragraph["items"])
                clauses.append({
                    "id": clause_id,
                    "article_id": article_id,
                    "no": no,
                    "text": clause_text,
                    "ordinal": ordinal,
                    "duplicate_no_occurrence": occurrence,
                })

        for ref in payload.get("internal_refs", []):
            source, target = ref.get("from"), ref.get("to")
            if source and target:
                internal_refs.append({
                    "claim_id": f"{source}|REFERS_TO|{target}",
                    "source_id": source,
                    "target_id": target,
                    "paragraph": ref.get("paragraph"),
                    "item": ref.get("item"),
                    "cross_doc": source.split("#", 1)[0] != target.split("#", 1)[0],
                    "resolution": "parser_internal_ref",
                })

        for ref in payload.get("external_refs", []):
            source, target_name = ref.get("from"), ref.get("target_name")
            if not source or not target_name:
                continue
            norm_name = normalize_name(target_name)
            target_doc = title_to_doc.get(norm_name)
            external_refs.append({
                "claim_id": f"{source}|CITES|{target_doc or 'ext:' + norm_name}",
                "source_id": source,
                "target_doc_id": target_doc,
                "external_id": None if target_doc else f"ext:{norm_name}",
                "target_name": target_name,
                "norm_name": norm_name,
            })

    external_names = {}
    for ref in external_refs:
        if ref["external_id"]:
            external_names[ref["external_id"]] = {
                "id": ref["external_id"],
                "name": ref["target_name"],
                "norm_name": ref["norm_name"],
                "kind": "미분류",
                "resolved": False,
            }

    return docs, chapters, articles, clauses, chapter_articles, document_articles, internal_refs, external_refs, list(external_names.values())


def ensure_constraints(session) -> None:
    constraints = [
        "CREATE CONSTRAINT document_doc_id IF NOT EXISTS FOR (n:Document) REQUIRE n.doc_id IS UNIQUE",
        "CREATE CONSTRAINT chapter_id IF NOT EXISTS FOR (n:Chapter) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT article_id IF NOT EXISTS FOR (n:Article) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT clause_id IF NOT EXISTS FOR (n:Clause) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT external_law_id IF NOT EXISTS FOR (n:ExternalLaw) REQUIRE n.id IS UNIQUE",
    ]
    for query in constraints:
        session.run(query).consume()


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    required = ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing required environment variable(s): " + ", ".join(missing))

    entries = load_documents()
    docs, chapters, articles, clauses, chapter_articles, document_articles, internal_refs, external_refs, external_laws = build_rows(entries)
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    print(
        "Prepared T1 internal-regulations batch: "
        f"documents={len(docs)}, chapters={len(chapters)}, articles={len(articles)}, "
        f"clauses={len(clauses)}, internal_refs={len(internal_refs)}, "
        f"citations={len(external_refs)}, external_law_stubs={len(external_laws)}"
    )

    with GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
        connection_timeout=15,
    ) as driver:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            before = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            print(f"Connected. Existing node count: {before}")
            ensure_constraints(session)

            run_batches(session, """
                UNWIND $rows AS row
                MERGE (d:Document {doc_id: row.doc_id})
                SET d += row
            """, docs)
            run_batches(session, """
                UNWIND $rows AS row
                MERGE (c:Chapter {id: row.id})
                SET c += row
                WITH c, row
                MATCH (d:Document {doc_id: row.doc_id})
                MERGE (d)-[:HAS_CHAPTER]->(c)
            """, chapters)
            run_batches(session, """
                UNWIND $rows AS row
                MERGE (a:Article {id: row.id})
                SET a += row
            """, articles)
            run_batches(session, """
                UNWIND $rows AS row
                MATCH (c:Chapter {id: row.chapter_id})
                MATCH (a:Article {id: row.article_id})
                MERGE (c)-[:HAS_ARTICLE]->(a)
            """, chapter_articles)
            run_batches(session, """
                UNWIND $rows AS row
                MATCH (d:Document {doc_id: row.doc_id})
                MATCH (a:Article {id: row.article_id})
                MERGE (d)-[:HAS_ARTICLE]->(a)
            """, document_articles)
            run_batches(session, """
                UNWIND $rows AS row
                MERGE (c:Clause {id: row.id})
                SET c += row
                WITH c, row
                MATCH (a:Article {id: row.article_id})
                MERGE (a)-[:HAS_CLAUSE]->(c)
            """, clauses)
            run_batches(session, """
                UNWIND $rows AS row
                MATCH (source:Article {id: row.source_id})
                MATCH (target:Article {id: row.target_id})
                MERGE (source)-[r:REFERS_TO {claim_id: row.claim_id}]->(target)
                SET r.paragraph = row.paragraph, r.item = row.item,
                    r.cross_doc = row.cross_doc, r.resolution = row.resolution
            """, internal_refs)
            run_batches(session, """
                UNWIND $rows AS row
                MERGE (x:ExternalLaw {id: row.id})
                SET x += row
            """, external_laws)
            run_batches(session, """
                UNWIND $rows AS row
                MATCH (source:Article {id: row.source_id})
                OPTIONAL MATCH (target:Document {doc_id: row.target_doc_id})
                OPTIONAL MATCH (external:ExternalLaw {id: row.external_id})
                WITH source, row, coalesce(target, external) AS target
                WHERE target IS NOT NULL
                MERGE (source)-[r:CITES {claim_id: row.claim_id}]->(target)
                SET r.target_name = row.target_name
            """, external_refs)

            counts = session.run("""
                OPTIONAL MATCH (d:Document) WITH count(d) AS docs
                OPTIONAL MATCH (c:Chapter) WITH docs, count(c) AS chapters
                OPTIONAL MATCH (a:Article) WITH docs, chapters, count(a) AS articles
                OPTIONAL MATCH (cl:Clause) WITH docs, chapters, articles, count(cl) AS clauses
                OPTIONAL MATCH ()-[r:REFERS_TO]->() WITH docs, chapters, articles, clauses, count(r) AS refs
                OPTIONAL MATCH ()-[c:CITES]->() RETURN docs, chapters, articles, clauses, refs, count(c) AS citations
            """).single()
            print("Post-load counts:", dict(counts))
            after = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            print(f"Node delta: {after - before}; total nodes: {after}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"Load failed: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
