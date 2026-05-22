import re
import json
import time
from google import genai
from dataclasses import dataclass
from enum import Enum
from utils.logger import get_logger
from utils.llm_utils import get_gemini_key
from ingestion.fetcher import PaperRecord
from config import get_config

class ChunkLevel(Enum):
    DOCUMENT    = "document"      # Level 1 — whole paper
    SECTION     = "section"       # Level 2 — IMRAD section
    SEMANTIC    = "semantic"      # Level 3A — semantic chunk
    PROPOSITION = "proposition"   # Level 3B — single claim

@dataclass
class Chunk:
    # Identity
    chunk_id: str
    paper_id: str
    level: ChunkLevel

    # Content
    text: str

    # Hierarchy
    parent_chunk_id: str
    section_type: str

    # Metadata copied from PaperRecord
    topic_cluster: str
    year: int
    journal: str
    evidence_level: str
    ingestion_date: str
    freshness_score: float
    contradiction_flag: bool

    # Chunk-specific
    char_count: int
    chunk_index: int

    def to_dict(self) -> dict:
        d = {
            "chunk_id": self.chunk_id,
            "paper_id": self.paper_id,
            "level": self.level.value,
            "text": self.text,
            "parent_chunk_id": self.parent_chunk_id,
            "section_type": self.section_type,
            "topic_cluster": self.topic_cluster,
            "year": self.year,
            "journal": self.journal,
            "evidence_level": self.evidence_level,
            "ingestion_date": self.ingestion_date,
            "freshness_score": self.freshness_score,
            "contradiction_flag": self.contradiction_flag,
            "char_count": self.char_count,
            "chunk_index": self.chunk_index,
        }
        return d

def make_chunk_id(paper_id: str,
                  level: ChunkLevel,
                  index: int,
                  parent_index: int = 0) -> str:
    return f"{paper_id}_{level.value}_{parent_index}_{index}"

class HierarchicalChunker:

    SECTION_PATTERNS = [
        (r"BACKGROUND[:\s]", "background"),
        (r"INTRODUCTION[:\s]", "introduction"),
        (r"OBJECTIVE[S]?[:\s]", "objective"),
        (r"PURPOSE[:\s]", "purpose"),
        (r"AIM[S]?[:\s]", "aims"),
        (r"METHODS?[:\s]", "methods"),
        (r"DESIGN[:\s]", "design"),
        (r"SETTING[:\s]", "setting"),
        (r"PATIENTS?[:\s]", "patients"),
        (r"PARTICIPANTS?[:\s]", "participants"),
        (r"INTERVENTION[S]?[:\s]", "intervention"),
        (r"RESULTS?[:\s]", "results"),
        (r"FINDINGS?[:\s]", "findings"),
        (r"OUTCOMES?[:\s]", "outcomes"),
        (r"CONCLUSION[S]?[:\s]", "conclusion"),
        (r"DISCUSSION[:\s]", "discussion"),
        (r"SIGNIFICANCE[:\s]", "significance"),
        (r"SUMMARY[:\s]", "summary"),
    ]

    def __init__(self):
        self.logger = get_logger(__name__)

    def create_document_chunk(self, paper: PaperRecord) -> Chunk:
        text = f"{paper.title}. {paper.abstract}"
        chunk_id = make_chunk_id(paper.paper_id, ChunkLevel.DOCUMENT, 0)
        return Chunk(
            chunk_id=chunk_id,
            paper_id=paper.paper_id,
            level=ChunkLevel.DOCUMENT,
            text=text,
            parent_chunk_id="",
            section_type="full",
            topic_cluster=paper.topic_cluster,
            year=paper.year,
            journal=paper.journal,
            evidence_level=paper.evidence_level,
            ingestion_date=paper.ingestion_date,
            freshness_score=paper.freshness_score,
            contradiction_flag=paper.contradiction_flag,
            char_count=len(text),
            chunk_index=0,
        )

    def create_section_chunks(self,
                               paper: PaperRecord,
                               doc_chunk_id: str) -> list[Chunk]:

        abstract = paper.abstract.strip()
        sections_found = []

        # Try to detect structured abstract sections
        # Build a combined pattern to find all section headers
        combined = "|".join(
            f"({pat})" for pat, _ in self.SECTION_PATTERNS
        )
        
        # Find all header positions
        matches = list(re.finditer(combined, abstract, re.IGNORECASE))

        if len(matches) >= 2:
            # Structured abstract — split at each header
            for i, match in enumerate(matches):
                start = match.start()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(abstract)
                section_text = abstract[start:end].strip()

                if not section_text:
                    continue

                # Identify which section type matched
                section_type = "other"
                for pat, name in self.SECTION_PATTERNS:
                    if re.match(pat, section_text, re.IGNORECASE):
                        section_type = name
                        break

                sections_found.append((section_type, section_text))
        else:
            # Unstructured abstract — split by length
            if len(abstract) > 500:
                mid = len(abstract) // 2
                # Find nearest sentence boundary to midpoint
                boundary = abstract.find(". ", mid - 50, mid + 50)
                if boundary == -1:
                    boundary = mid
                else:
                    boundary += 2  # include the period and space

                part1 = abstract[:boundary].strip()
                part2 = abstract[boundary:].strip()

                if part1:
                    sections_found.append(("abstract_part1", part1))
                if part2:
                    sections_found.append(("abstract_part2", part2))
            else:
                sections_found.append(("abstract", abstract))

        # Build Chunk objects
        chunks = []
        for idx, (section_type, text) in enumerate(sections_found):
            if not text.strip():
                continue
            chunk_id = make_chunk_id(
                paper.paper_id, ChunkLevel.SECTION, idx
            )
            chunks.append(Chunk(
                chunk_id=chunk_id,
                paper_id=paper.paper_id,
                level=ChunkLevel.SECTION,
                text=text,
                parent_chunk_id=doc_chunk_id,
                section_type=section_type,
                topic_cluster=paper.topic_cluster,
                year=paper.year,
                journal=paper.journal,
                evidence_level=paper.evidence_level,
                ingestion_date=paper.ingestion_date,
                freshness_score=paper.freshness_score,
                contradiction_flag=paper.contradiction_flag,
                char_count=len(text),
                chunk_index=idx,
            ))

        # Safety — always return at least one chunk
        if not chunks:
            chunk_id = make_chunk_id(
                paper.paper_id, ChunkLevel.SECTION, 0
            )
            chunks.append(Chunk(
                chunk_id=chunk_id,
                paper_id=paper.paper_id,
                level=ChunkLevel.SECTION,
                text=abstract,
                parent_chunk_id=doc_chunk_id,
                section_type="abstract",
                topic_cluster=paper.topic_cluster,
                year=paper.year,
                journal=paper.journal,
                evidence_level=paper.evidence_level,
                ingestion_date=paper.ingestion_date,
                freshness_score=paper.freshness_score,
                contradiction_flag=paper.contradiction_flag,
                char_count=len(abstract),
                chunk_index=0,
            ))

        return chunks

    def create_semantic_chunks(self,
                                section_chunk: Chunk,
                                paper: PaperRecord) -> list[Chunk]:

        text = section_chunk.text.strip()

        # Short sections — return as single semantic chunk
        if len(text) <= 200:
            chunk_id = make_chunk_id(
                paper.paper_id,
                ChunkLevel.SEMANTIC,
                0,
                section_chunk.chunk_index
            )
            return [Chunk(
                chunk_id=chunk_id,
                paper_id=paper.paper_id,
                level=ChunkLevel.SEMANTIC,
                text=text,
                parent_chunk_id=section_chunk.chunk_id,
                section_type=section_chunk.section_type,
                topic_cluster=paper.topic_cluster,
                year=paper.year,
                journal=paper.journal,
                evidence_level=paper.evidence_level,
                ingestion_date=paper.ingestion_date,
                freshness_score=paper.freshness_score,
                contradiction_flag=paper.contradiction_flag,
                char_count=len(text),
                chunk_index=0,
            )]

        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Group sentences into chunks targeting 150-250 chars
        raw_chunks = []
        current = ""

        for sentence in sentences:
            if not current:
                current = sentence
            elif len(current) + 1 + len(sentence) <= 250:
                current += " " + sentence
            else:
                raw_chunks.append(current.strip())
                current = sentence

        if current.strip():
            raw_chunks.append(current.strip())

        # Safety — if grouping produced nothing use whole text
        if not raw_chunks:
            raw_chunks = [text]

        # Build Chunk objects
        chunks = []
        for idx, chunk_text in enumerate(raw_chunks):
            if not chunk_text.strip():
                continue
            chunk_id = make_chunk_id(
                paper.paper_id,
                ChunkLevel.SEMANTIC,
                idx,
                section_chunk.chunk_index
            )
            chunks.append(Chunk(
                chunk_id=chunk_id,
                paper_id=paper.paper_id,
                level=ChunkLevel.SEMANTIC,
                text=chunk_text,
                parent_chunk_id=section_chunk.chunk_id,
                section_type=section_chunk.section_type,
                topic_cluster=paper.topic_cluster,
                year=paper.year,
                journal=paper.journal,
                evidence_level=paper.evidence_level,
                ingestion_date=paper.ingestion_date,
                freshness_score=paper.freshness_score,
                contradiction_flag=paper.contradiction_flag,
                char_count=len(chunk_text),
                chunk_index=idx,
            ))

        return chunks if chunks else [Chunk(
            chunk_id=make_chunk_id(
                paper.paper_id, ChunkLevel.SEMANTIC, 0,
                section_chunk.chunk_index
            ),
            paper_id=paper.paper_id,
            level=ChunkLevel.SEMANTIC,
            text=text,
            parent_chunk_id=section_chunk.chunk_id,
            section_type=section_chunk.section_type,
            topic_cluster=paper.topic_cluster,
            year=paper.year,
            journal=paper.journal,
            evidence_level=paper.evidence_level,
            ingestion_date=paper.ingestion_date,
            freshness_score=paper.freshness_score,
            contradiction_flag=paper.contradiction_flag,
            char_count=len(text),
            chunk_index=0,
        )]

    def create_proposition_chunks(self,
                                   semantic_chunk: Chunk,
                                   paper: PaperRecord) -> list[Chunk]:

        # Configure Gemini using round-robin key management
        client = genai.Client(api_key=get_gemini_key())

        prompt = (
            "Extract individual factual propositions from this "
            "biomedical text. Each proposition must be:\n"
            "- A single complete verifiable claim\n"
            "- Self-contained with enough context to understand alone\n"
            "- Preserving specific numbers, drug names, and statistics\n\n"
            "Return ONLY a JSON array of strings. "
            "No explanation. No markdown. No code blocks.\n"
            "Example: [\"Drug X showed 67% response rate in NSCLC\","
            "\"Treatment was given every 3 weeks\"]\n\n"
            f"Text:\n{semantic_chunk.text}"
        )

        propositions = []

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            raw = response.text.strip()

            # Strip markdown code blocks if present
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1])

            parsed = json.loads(raw)

            if isinstance(parsed, list):
                propositions = [
                    str(p).strip()
                    for p in parsed
                    if str(p).strip() and len(str(p).strip()) >= 20
                ]

        except json.JSONDecodeError:
            self.logger.warning(
                f"JSON parse failed for chunk {semantic_chunk.chunk_id}"
                f" — using full text as fallback"
            )
            propositions = []

        except Exception as e:
            self.logger.error(
                f"Gemini call failed for chunk "
                f"{semantic_chunk.chunk_id}: {e}"
            )
            propositions = []

        # Fallback — use whole semantic chunk text as one proposition
        if not propositions:
            propositions = [semantic_chunk.text]

        # Cap at 10 propositions per semantic chunk
        propositions = propositions[:10]

        # Rate limiting — Gemini Flash
        time.sleep(0.5)

        # Build Chunk objects
        chunks = []
        for idx, prop_text in enumerate(propositions):
            chunk_id = make_chunk_id(
                paper.paper_id,
                ChunkLevel.PROPOSITION,
                idx,
                semantic_chunk.chunk_index
            )
            chunks.append(Chunk(
                chunk_id=chunk_id,
                paper_id=paper.paper_id,
                level=ChunkLevel.PROPOSITION,
                text=prop_text,
                parent_chunk_id=semantic_chunk.chunk_id,
                section_type=semantic_chunk.section_type,
                topic_cluster=paper.topic_cluster,
                year=paper.year,
                journal=paper.journal,
                evidence_level=paper.evidence_level,
                ingestion_date=paper.ingestion_date,
                freshness_score=paper.freshness_score,
                contradiction_flag=paper.contradiction_flag,
                char_count=len(prop_text),
                chunk_index=idx,
            ))

        self.logger.debug(
            f"Propositions for {semantic_chunk.chunk_id}: "
            f"{len(chunks)} extracted"
        )

        return chunks

    def chunk_paper(self,
                    paper: PaperRecord) -> dict[str, list[Chunk]]:

        # Level 1 — document
        doc_chunk = self.create_document_chunk(paper)

        # Level 2 — sections
        section_chunks = self.create_section_chunks(
            paper, doc_chunk.chunk_id
        )

        # Level 3A — semantic
        semantic_chunks = []
        for sec in section_chunks:
            semantic_chunks.extend(
                self.create_semantic_chunks(sec, paper)
            )

        # Level 3B — propositions
        proposition_chunks = []
        for sem in semantic_chunks:
            proposition_chunks.extend(
                self.create_proposition_chunks(sem, paper)
            )

        self.logger.info(
            f"Chunked {paper.paper_id}: "
            f"1 doc | {len(section_chunks)} sections | "
            f"{len(semantic_chunks)} semantic | "
            f"{len(proposition_chunks)} propositions"
        )

        return {
            "document": [doc_chunk],
            "sections": section_chunks,
            "semantic": semantic_chunks,
            "propositions": proposition_chunks,
        }
