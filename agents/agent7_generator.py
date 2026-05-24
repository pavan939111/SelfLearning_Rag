from google import genai
from google.genai import types
import re
from dataclasses import dataclass, field
from config import get_config
from utils.logger import get_logger
from utils.llm_utils import get_gemini_key
import json
from utils.thought_logger import ThoughtLogger

from agents.models import (
    ClaimProvenance, GeneratedResponse
)

class Agent7Generator:
    """
    Agent 7: Conversational Response Generator.
    Takes verified chunks from the Quality Gate or Repair Cycle and generates
    a natural, grounded, conversational response with inline citations.
    """
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger(__name__)

    def _extract_author_year(self, chunk) -> str:
        """Heuristically extracts an Author Year string for citations."""
        authors = getattr(chunk, 'authors', []) if not isinstance(chunk, dict) else chunk.get('authors', [])
        year = getattr(chunk, 'year', 0) if not isinstance(chunk, dict) else chunk.get('year', 0)
        
        if isinstance(authors, list) and authors:
            # Extract last name from "LastName, Initials" format
            first_author = authors[0].split(',')[0].split()[-1]
            if len(authors) > 2:
                first_author += " et al."
            elif len(authors) == 2:
                second_author = authors[1].split(',')[0].split()[-1]
                first_author += f" and {second_author}"
        elif isinstance(authors, str) and authors:
            first_author = authors.split(',')[0].split()[-1]
            if " et al" in authors:
                first_author += " et al."
        else:
            first_author = "Unknown"
            
        return f"{first_author} {year}"

    def _detect_output_format(self, query: str, classification) -> str:
        query_lower = query.lower()
        entities = getattr(classification, 'entities', [])
        query_type = getattr(classification, 'query_type', '')
        
        # Table — comparative queries with 2+ entities
        if query_type == 'comparative':
            if len(entities) >= 2:
                return 'table'
            # Also check query words
            compare_words = [
                'compare', 'versus', 'vs', 'difference between',
                'contrast', 'which is better', 'similarities'
            ]
            if any(w in query_lower for w in compare_words):
                return 'table'
        
        # List — explicit list requests
        list_words = [
            'list', 'what are the', 'enumerate',
            'give me all', 'name the', 'types of',
            'examples of', 'which drugs', 'what drugs',
            'side effects', 'adverse effects',
            'what are', 'how many'
        ]
        if any(w in query_lower for w in list_words):
            return 'list'
        
        # Summary — overview requests
        summary_words = [
            'summarize', 'summary', 'overview',
            'brief', 'outline', 'describe overall',
            'what is known about', 'explain'
        ]
        if any(w in query_lower for w in summary_words):
            return 'summary'
        
        return 'prose'

    def _build_format_instructions(self, output_format: str, entities: list[str]) -> str:
        if output_format == 'table':
            entity_headers = ' | '.join(entities[:3]) if entities else 'Option A | Option B'
            
            return f"""
Format your response as a markdown comparison table.

Use this exact structure:
| Feature | {entity_headers} |
|---------|{'|'.join(['---'] * min(len(entities), 3))}|
| Mechanism | ... | ... |
| Efficacy | ... | ... |
| Side Effects | ... | ... |
| Patient Population | ... | ... |
| Evidence Level | ... | ... |
| Key Citation | ... | ... |

Rules:
- Fill every cell with specific data from the evidence
- Use (Author Year) inline for citations in cells
- After the table write ONE paragraph summary
- If data unavailable for a cell write: "Limited evidence"
"""
        elif output_format == 'list':
            return """
Format your response as a numbered list.

Use this exact structure:
1. [Specific fact or item] (Author Year)
2. [Specific fact or item] (Author Year)
3. [Specific fact or item] (Author Year)

Rules:
- Each item is ONE clear specific fact
- Every item must have an inline citation
- Maximum 8 items
- After the list write ONE sentence summary
"""
        elif output_format == 'summary':
            return """
Format your response as a structured summary.

Use this exact structure:
**KEY FINDING:** [One sentence — the most important finding]

**EVIDENCE:** 
- [Supporting point 1 with citation]
- [Supporting point 2 with citation]
- [Supporting point 3 with citation]

**LIMITATIONS:**
[What is not well-covered or uncertain]

**CONFIDENCE:** [High/Medium/Low — based on evidence quality]
"""
        else:  # prose
            return """
Write a clear conversational response.
Use natural paragraph format.
Embed citations inline as (Author Year).
"""

    def _extract_claim_provenance(self, answer: str, chunks: list) -> list[ClaimProvenance]:
        try:
            chunks_text = ""
            chunk_map = {}
            for i, c in enumerate(chunks):
                cid = getattr(c, 'chunk_id', f"chunk_{i}") if not isinstance(c, dict) else c.get('chunk_id', f"chunk_{i}")
                text = getattr(c, 'text', '') if not isinstance(c, dict) else c.get('text', '')
                paper_id = getattr(c, 'paper_id', 'unknown') if not isinstance(c, dict) else c.get('paper_id', 'unknown')
                year = getattr(c, 'year', 0) if not isinstance(c, dict) else c.get('year', 0)
                journal = getattr(c, 'journal', 'Unknown') if not isinstance(c, dict) else c.get('journal', 'Unknown')
                
                chunks_text += f"[{cid}]: {text}\n\n"
                chunk_map[cid] = {
                    "paper_id": paper_id,
                    "year": year,
                    "journal": journal
                }

            prompt = f"""Given this answer and the source chunks it was generated from, identify each specific factual claim in the answer and link it to the chunk that supports it.
            
Answer:
{answer}

Source chunks:
{chunks_text}

Return JSON array only:
[
  {{
    "claim": "specific factual claim text",
    "chunk_id": "which chunk supports this",
    "confidence": 0.0 to 1.0,
    "quote": "relevant excerpt from chunk"
  }}
]"""
            client = genai.Client(api_key=get_gemini_key())
            res = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1
                )
            )
            
            raw_text = res.text.strip()
            # simple json extraction
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].strip()
                
            data = json.loads(raw_text)
            provenance = []
            for item in data:
                cid = item.get("chunk_id")
                meta = chunk_map.get(cid, {})
                provenance.append(ClaimProvenance(
                    claim=item.get("claim", ""),
                    chunk_id=cid,
                    paper_id=meta.get("paper_id", "unknown"),
                    paper_year=meta.get("year", 0),
                    journal=meta.get("journal", "Unknown"),
                    confidence=float(item.get("confidence", 0.0)),
                    quote=item.get("quote", "")
                ))
            return provenance
        except Exception as e:
            self.logger.warning(f"Claim provenance extraction failed: {e}")
            return []

    def _generate_query_suggestions(self, query: str, agent2_result, coverage_gaps: list) -> list[str]:
        if agent2_result and getattr(agent2_result, 'all_passed', False):
            return []
            
        if not coverage_gaps:
            return []
            
        try:
            gap_topics = [g if isinstance(g, str) else g.get('topic', '') for g in coverage_gaps[:3]]
            
            prompt = f"""The user asked: {query}
             
The system could not fully answer because these aspects are not well-covered in our knowledge base:
{gap_topics}
             
Suggest 2-3 RELATED questions that:
1. The user might also be interested in
2. ARE likely to be well-covered in a biomedical corpus about immunotherapy, drug interactions, and genomics
3. Are genuinely useful follow-ups
             
Return JSON array of question strings only.
No explanation."""

            client = genai.Client(api_key=get_gemini_key())
            res = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3
                )
            )
            
            raw_text = res.text.strip()
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].strip()
                
            suggestions = json.loads(raw_text)
            if isinstance(suggestions, list):
                return [str(s) for s in suggestions[:3]]
            return []
        except Exception as e:
            self.logger.warning(f"Failed to generate query suggestions: {e}")
            return []

    def generate(self, query: str, classification, agent2_result, cycle_result, conversation_history: list[dict], proactive_contradiction_note: str = "") -> GeneratedResponse:
        self.logger.info("Starting Agent 7 Generation...")
        
        # Step 1: Prepare context from verified chunks
        try:
            tl = ThoughtLogger(session_id='', agent='agent7')
        except Exception:
            tl = None
            
        chunks = []
        if cycle_result and hasattr(cycle_result, 'final_chunks') and cycle_result.final_chunks:
            chunks = cycle_result.final_chunks
        elif agent2_result and hasattr(agent2_result, 'retrieval_results'):
            chunks = agent2_result.retrieval_results
            
        if not chunks:
            self.logger.warning("No verified chunks provided to Agent 7.")
            return GeneratedResponse(
                answer="I was unable to generate a response because no verified evidence was retrieved. Please try again.",
                confidence=0.0
            )
            
        try:
            evidence_text = ""
            paper_metadata_map = {}
            for i, c in enumerate(chunks, 1):
                text = getattr(c, 'text', '') if not isinstance(c, dict) else c.get('text', '')
                journal = getattr(c, 'journal', 'Unknown Journal') if not isinstance(c, dict) else c.get('journal', 'Unknown Journal')
                topic = getattr(c, 'topic_cluster', 'default') if not isinstance(c, dict) else c.get('topic_cluster', 'default')
                paper_id = getattr(c, 'paper_id', 'unknown') if not isinstance(c, dict) else c.get('paper_id', 'unknown')
                year = getattr(c, 'year', 0) if not isinstance(c, dict) else c.get('year', 0)
                
                cite_key = self._extract_author_year(c)
                
                evidence_text += f"[{i}] ({cite_key}, {journal}, {topic})\n{text}\n\n"
                
                # Map citation key to metadata dictionary
                if cite_key not in paper_metadata_map:
                    paper_metadata_map[cite_key] = {
                        "citation": cite_key,
                        "paper_id": paper_id,
                        "journal": journal,
                        "year": year
                    }

            try:
                if tl:
                    tl.trace(
                        step='prepare_context',
                        obs=f"Received {len(chunks)} verified chunks. "
                            f"Mapped {len(paper_metadata_map)} distinct citations.",
                        thk="Evidence is ready. Formatting prompt context for generation.",
                        act="Compile evidence text with inline citation keys.",
                        out=f"Context prepared: {len(evidence_text)} characters.",
                        confidence=1.0
                    )
            except Exception: pass

            # Step 2: Build conversation context
            conv_text = ""
            if conversation_history:
                last_6 = conversation_history[-6:]
                for turn in last_6:
                    role = turn.get("role", "user")
                    content = turn.get("content", "")
                    conv_text += f"{role.capitalize()}: {content}\n"
                    
            confidence = getattr(agent2_result, 'calibrated_confidence', 0.0) if agent2_result else 0.0
            has_contradiction = getattr(agent2_result, 'contradiction_found', False) if agent2_result else False
            coverage_gaps = getattr(agent2_result, 'coverage_gaps', []) if agent2_result else []
            
            output_format = self._detect_output_format(
                query, classification
            )
            format_instructions = self._build_format_instructions(
                output_format,
                getattr(classification, 'entities', [])
            )
            
            contra_note = ""
            if has_contradiction:
                contra_note = "\n- Note that sources disagree on certain points based on the evidence."
                
            gap_note = ""
            if coverage_gaps:
                gap_note = "\n- Acknowledge these gaps honestly: " + ", ".join(coverage_gaps)
                
            full_prompt = f"""
You are a biomedical research assistant.
Answer ONLY from the provided evidence.

{format_instructions}

Current question: {query}

Conversation context:
{conv_text}

Evidence (use ONLY these sources):
{evidence_text}

Calibrated confidence level: {confidence:.0%}
{contra_note}
{gap_note}

Answer:"""
            
            system_instruction = (
                "You are a biomedical research assistant. Answer questions based ONLY on the provided evidence. "
                "Cite sources inline as (AuthorYear) format. Be conversational and clear. "
                "If evidence is limited say so honestly."
            )
            
            if proactive_contradiction_note:
                system_instruction += (
                    "\nIMPORTANT: This topic has known contradictions. "
                    "Present both sides explicitly. Do not pick one side. "
                    "Format: 'Study A found X while Study B found Y...'"
                )

            try:
                if tl:
                    tl.trace(
                        step='formatting',
                        obs=f"Output format detected: {output_format}. "
                            f"Contradiction flag: {has_contradiction}.",
                        thk=f"Using {output_format} template. "
                            f"{'Adding contradiction guardrails.' if has_contradiction else 'No guardrails needed.'}",
                        act="Generate response using Gemini Flash with injected system instructions.",
                        out="Generating...",
                        confidence=confidence
                    )
            except Exception: pass

            # Step 4: Generate with Gemini Flash
            client = genai.Client(api_key=get_gemini_key())
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction
                )
            )
            answer_text = response.text.strip()
            
            # Step 5: Extract citations
            citations_list = []
            seen_cite_keys = set()
            
            potential_citations = re.findall(r'\(([^)]+)\)', answer_text)
            for pc in potential_citations:
                for cite_key, meta in paper_metadata_map.items():
                    if cite_key in pc and cite_key not in seen_cite_keys:
                        citations_list.append(meta)
                        seen_cite_keys.add(cite_key)
            
            # Step 6: Extract claims
            provenance = None
            if chunks:
                provenance = self._extract_claim_provenance(answer_text, chunks)

            try:
                if tl:
                    tl.trace(
                        step='extract_citations',
                        obs=f"Generation complete. "
                            f"Length: {len(answer_text)} chars. "
                            f"Found {len(citations_list)} explicit citations.",
                        thk="Need to map generated claims back to source chunks for provenance tracking.",
                        act="Extract citations and execute claim provenance extraction.",
                        out=f"Extracted {len(provenance) if provenance else 0} verified claims.",
                        confidence=confidence
                    )
            except Exception: pass

            # Step 7: Build Final Response
            gap_ack = ""
            if coverage_gaps:
                gap_ack = "While this covers the primary aspects of your query, please note that information regarding " + ", ".join(coverage_gaps) + " was limited in the retrieved literature."
                
            contra_note = "There appears to be conflicting evidence on this topic in the retrieved literature." if has_contradiction else ""
            query_type = getattr(classification, 'query_type', 'unknown') if classification else 'unknown'
            
            suggestions = self._generate_query_suggestions(query, agent2_result, coverage_gaps)
            
            conf_lower = getattr(agent2_result, 'confidence_lower', confidence) if agent2_result else confidence
            conf_upper = getattr(agent2_result, 'confidence_upper', confidence) if agent2_result else confidence
            
            res = GeneratedResponse(
                answer=answer_text,
                citations=citations_list,
                confidence=confidence,
                confidence_lower=conf_lower,
                confidence_upper=conf_upper,
                has_gaps=len(coverage_gaps) > 0,
                gap_acknowledgment=gap_ack,
                has_contradiction=has_contradiction,
                contradiction_note=contra_note,
                query_type=query_type,
                chunks_used=len(chunks),
                output_format=output_format,
                claim_provenance=provenance or [],
                query_suggestions=suggestions
            )
            
            if tl:
                res.thought_traces = tl.get_traces()
                
            return res

        except Exception as e:
            self.logger.error(f"Agent 7 Generation failed: {e}")
            return GeneratedResponse(
                answer="I was unable to generate a response at this time. Please try again.",
                confidence=0.0
            )
