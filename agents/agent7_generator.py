from google import genai
from google.genai import types
import re
from dataclasses import dataclass, field
from config import get_config
from utils.logger import get_logger
from utils.llm_utils import get_gemini_key

@dataclass
class GeneratedResponse:
    answer: str
    citations: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    has_gaps: bool = False
    gap_acknowledgment: str = ""
    has_contradiction: bool = False
    contradiction_note: str = ""
    query_type: str = ""
    chunks_used: int = 0

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

    def generate(self, query: str, classification, agent2_result, cycle_result, conversation_history: list[dict]) -> GeneratedResponse:
        self.logger.info("Starting Agent 7 Generation...")
        
        # Step 1: Prepare context from verified chunks
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

            # Step 2: Build conversation context
            conv_text = ""
            if conversation_history:
                last_6 = conversation_history[-6:]
                for turn in last_6:
                    role = turn.get("role", "user")
                    content = turn.get("content", "")
                    conv_text += f"{role.capitalize()}: {content}\n"
                    
            # Step 3: Build Generation Prompt
            confidence = getattr(agent2_result, 'calibrated_confidence', 0.0) if agent2_result else 0.0
            has_contradiction = getattr(agent2_result, 'contradiction_found', False) if agent2_result else False
            coverage_gaps = getattr(agent2_result, 'coverage_gaps', []) if agent2_result else []
            
            prompt_parts = []
            if conv_text:
                prompt_parts.append(f"Conversation so far:\n{conv_text}\n")
                
            prompt_parts.append(f"Current question: {query}\n\nEvidence (use ONLY these sources):\n{evidence_text}")
            
            prompt_parts.append("Instructions:\n- Answer conversationally as if explaining to a researcher.")
            prompt_parts.append("- Cite each fact inline: (AuthorYear) using the exact keys from the evidence brackets.")
            prompt_parts.append("- If evidence only partially answers the question say so honestly.")
            prompt_parts.append(f"- Confidence level for this answer: {confidence:.2f}")
            
            if has_contradiction:
                prompt_parts.append("- Note that sources disagree on certain points based on the evidence.")
            if coverage_gaps:
                prompt_parts.append("- Acknowledge these gaps honestly: " + ", ".join(coverage_gaps))
                
            prompt_parts.append("\nAnswer:")
            full_prompt = "\n".join(prompt_parts)
            
            system_instruction = (
                "You are a biomedical research assistant. Answer questions based ONLY on the provided evidence. "
                "Cite sources inline as (AuthorYear) format. Be conversational and clear. "
                "If evidence is limited say so honestly."
            )

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
            
            # Step 6: Build Final Response
            gap_ack = ""
            if coverage_gaps:
                gap_ack = "While this covers the primary aspects of your query, please note that information regarding " + ", ".join(coverage_gaps) + " was limited in the retrieved literature."
                
            contra_note = "There appears to be conflicting evidence on this topic in the retrieved literature." if has_contradiction else ""
            query_type = getattr(classification, 'query_type', 'unknown') if classification else 'unknown'
            
            return GeneratedResponse(
                answer=answer_text,
                citations=citations_list,
                confidence=confidence,
                has_gaps=len(coverage_gaps) > 0,
                gap_acknowledgment=gap_ack,
                has_contradiction=has_contradiction,
                contradiction_note=contra_note,
                query_type=query_type,
                chunks_used=len(chunks)
            )

        except Exception as e:
            self.logger.error(f"Agent 7 Generation failed: {e}")
            return GeneratedResponse(
                answer="I was unable to generate a response at this time. Please try again.",
                confidence=0.0
            )
