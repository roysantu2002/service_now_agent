import os
import time
import json
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

import openai

from .compliance import ComplianceFilter
from .log_parser import LogEntry
from .rag_search import LangChainRAG  # updated class name


@dataclass
class AIResponse:
    response_text: str
    confidence_score: float
    compliance_safe: bool
    redacted_input: str
    redaction_log: Dict
    processing_time: float
    model_used: str
    tokens_used: int


class SecureAIIntegration:
    """Secure AI wrapper for log analysis with optional RAG integration."""

    def __init__(self, api_key: Optional[str] = None, rag_engine: Optional[LangChainRAG] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = openai.OpenAI(api_key=self.api_key) if self.api_key else None
        self.rag_engine = rag_engine
        self.compliance_filter = ComplianceFilter()

        self.model_config = {
            "model": "gpt-4o-mini",
            "temperature": 0.3,
            "max_tokens": 1000,
            "top_p": 0.9,
        }

        self.system_prompts = {
            "error_analysis": (
                "You are a senior DevOps engineer specializing in log analysis "
                "for financial institutions. Provide actionable, compliant recommendations."
            ),
            "pattern_analysis": (
                "You are an expert in identifying patterns in system logs "
                "for financial services. Identify root causes, vulnerabilities, and monitoring improvements."
            ),
            "security_analysis": (
                "You are a cybersecurity expert for financial institutions. "
                "Provide threat assessment, containment, and compliance steps."
            ),
            "performance_analysis": (
                "You are a performance optimization specialist for financial systems. "
                "Identify bottlenecks and optimization strategies."
            ),
        }

    # ------------------------------
    # Private utility methods
    # ------------------------------
    def _prepare_safe_input(self, text: str, redaction_level: str = "FULL") -> Tuple[str, Dict]:
        """Redact sensitive information and check compliance."""
        is_safe, safety_report = self.compliance_filter.is_safe_for_llm(text)
        if is_safe:
            return text, {"redacted": False, "safety_report": safety_report, "redaction_log": {"redactions": [], "redaction_count": 0}}
        redacted_text, redaction_log = self.compliance_filter.redact_sensitive_data(text, redaction_level)
        return redacted_text, {"redacted": True, "safety_report": safety_report, "redaction_log": redaction_log}

    def _call_ai(self, prompt: str, system_role: str, temperature: float = 0.3, max_tokens: Optional[int] = None) -> Tuple[str, int]:
        """Generic AI call wrapper using OpenAI Chat API."""
        if not self.client:
            raise RuntimeError("OpenAI client not initialized")
        max_tokens = max_tokens or self.model_config["max_tokens"]
        response = self.client.chat.completions.create(
            model=self.model_config["model"],
            messages=[
                {"role": "system", "content": system_role},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=self.model_config["top_p"],
        )
        return response.choices[0].message.content, response.usage.total_tokens

    def _truncate_context(self, text: str, max_chars: int = 3000) -> str:
        """Truncate context to avoid exceeding token limits."""
        return text[-max_chars:]

    def _build_response(self, text, confidence, compliance_info, prompt, tokens_used, start_time) -> AIResponse:
        return AIResponse(
            response_text=text,
            confidence_score=confidence,
            compliance_safe=not compliance_info["redacted"],
            redacted_input=prompt if compliance_info["redacted"] else "",
            redaction_log=compliance_info["redaction_log"],
            processing_time=round(time.time() - start_time, 3),
            model_used=self.model_config["model"],
            tokens_used=tokens_used,
        )

    def _ai_unavailable_response(self, feature_name: str) -> AIResponse:
        return AIResponse(
            response_text=f"{feature_name} unavailable: No OpenAI API key configured",
            confidence_score=0.0,
            compliance_safe=True,
            redacted_input="",
            redaction_log={},
            processing_time=0.0,
            model_used="none",
            tokens_used=0,
        )

    def _ai_error_response(self, exception: Exception, start_time) -> AIResponse:
        return AIResponse(
            response_text=f"Error during AI processing: {str(exception)}",
            confidence_score=0.0,
            compliance_safe=True,
            redacted_input="",
            redaction_log={},
            processing_time=round(time.time() - start_time, 3),
            model_used="error",
            tokens_used=0,
        )

    # ------------------------------
    # Public methods
    # ------------------------------
    def analyze_error(self, error_entry: LogEntry, context_entries: Optional[List[LogEntry]] = None) -> AIResponse:
        start_time = time.time()
        if not self.client:
            return self._ai_unavailable_response("Error Analysis")

        context_text = ""
        if context_entries:
            context_text = "\n".join([f"[{e.level}] {e.message}" for e in context_entries[-5:]])
            context_text = self._truncate_context(context_text)

        prompt = f"""
Primary Error:
- Level: {error_entry.level}
- Category: {error_entry.category}
- Message: {error_entry.message}
- Timestamp: {error_entry.timestamp}
- Severity Score: {error_entry.severity_score}/5

Recent Log Context:
{context_text}

Please provide:
1. Root cause analysis
2. Immediate resolution steps
3. Long-term prevention measures
4. Compliance considerations
5. Monitoring recommendations
"""
        safe_prompt, compliance_info = self._prepare_safe_input(prompt)
        try:
            text, tokens_used = self._call_ai(safe_prompt, self.system_prompts["error_analysis"])
            return self._build_response(text, 0.85, compliance_info, safe_prompt, tokens_used, start_time)
        except Exception as e:
            return self._ai_error_response(e, start_time)

    def analyze_patterns(self, pattern_analysis: Dict) -> AIResponse:
        start_time = time.time()
        if not self.client:
            return self._ai_unavailable_response("Pattern Analysis")

        patterns_text = ""
        for i, p in enumerate(pattern_analysis.get("patterns", [])[:5]):
            patterns_text += f"""
Pattern {i + 1}:
- Occurrences: {p['count']}
- Category: {p['category']}
- Severity: {p['severity']}/5
- Sample Message: {p['sample_message']}
- Time Range: Lines {p['first_occurrence']} to {p['last_occurrence']}
"""
        prompt = f"""
Log Pattern Analysis Request:
Summary:
- Total Errors: {pattern_analysis.get('total_errors', 0)}
- Unique Patterns: {pattern_analysis.get('unique_patterns', 0)}
- Recurring Patterns: {pattern_analysis.get('recurring_patterns', 0)}

Top Error Patterns:
{patterns_text}

Provide:
1. System health assessment
2. Critical patterns
3. Root causes
4. Systemic issues
5. Monitoring and alerting improvements
6. Compliance and security implications
"""
        safe_prompt, compliance_info = self._prepare_safe_input(prompt)
        try:
            text, tokens_used = self._call_ai(safe_prompt, self.system_prompts["pattern_analysis"])
            return self._build_response(text, 0.8, compliance_info, safe_prompt, tokens_used, start_time)
        except Exception as e:
            return self._ai_error_response(e, start_time)

    def security_analysis(self, entries: List[LogEntry]) -> AIResponse:
        start_time = time.time()
        if not self.client:
            return self._ai_unavailable_response("Security Analysis")

        security_logs = [e for e in entries if any(k in e.message.lower() for k in ["security", "breach", "attack", "unauthorized", "suspicious", "malicious", "intrusion"])]
        if not security_logs:
            return AIResponse(
                response_text="No security-related logs found",
                confidence_score=1.0,
                compliance_safe=True,
                redacted_input="",
                redaction_log={},
                processing_time=time.time() - start_time,
                model_used="none",
                tokens_used=0,
            )

        logs_text = "\n".join([f"- {e.timestamp} [{e.level}] {e.category}: {e.message}" for e in security_logs[:10]])
        prompt = f"""
Security Log Analysis:
Security Entries ({len(security_logs)} total):
{logs_text}

Provide:
1. Threat level
2. Attack vectors
3. Containment steps
4. Investigation steps
5. Long-term security improvements
6. Regulatory reporting
7. Incident response recommendations
"""
        safe_prompt, compliance_info = self._prepare_safe_input(prompt)
        try:
            text, tokens_used = self._call_ai(safe_prompt, self.system_prompts["security_analysis"], temperature=0.2, max_tokens=1200)
            return self._build_response(text, 0.9, compliance_info, safe_prompt, tokens_used, start_time)
        except Exception as e:
            return self._ai_error_response(e, start_time)

    def natural_language_query(self, query: str, log_entries: List[LogEntry]) -> AIResponse:
        start_time = time.time()
        if not self.client:
            return self._ai_unavailable_response("Natural Language Query")

        relevant_entries = log_entries[:10]
        if self.rag_engine:
            search_results = self.rag_engine.hybrid_search(query, log_entries)
            relevant_entries = [r.entry for r in search_results]

        context_text = "\n".join([f"- {e.timestamp} [{e.level}] {e.category}: {e.message}" for e in relevant_entries])
        prompt = f"""
User Query: {query}

Relevant Log Context:
{context_text}

Provide:
1. Direct answer
2. Evidence from logs
3. Additional insights
4. Compliance considerations
"""
        safe_prompt, compliance_info = self._prepare_safe_input(prompt)
        try:
            text, tokens_used = self._call_ai(safe_prompt, "You are a helpful log analysis assistant for financial institutions.")
            return self._build_response(text, 0.75, compliance_info, safe_prompt, tokens_used, start_time)
        except Exception as e:
            return self._ai_error_response(e, start_time)

    def generate_summary_report(self, analysis_data: Dict) -> AIResponse:
        start_time = time.time()
        if not self.client:
            return self._ai_unavailable_response("Summary Report")

        prompt = f"""
Executive Summary:
System Overview:
- Total Log Entries: {analysis_data.get('total_entries',0):,}
- Error Count: {analysis_data.get('error_count',0):,}
- Error Rate: {(analysis_data.get('error_count',0)/max(analysis_data.get('total_entries',1),1)*100):.2f}%

Top Error Categories:
{json.dumps(analysis_data.get('category_distribution', {}), indent=2)}

Level Distribution:
{json.dumps(analysis_data.get('level_distribution', {}), indent=2)}

Provide:
1. System health status
2. Key findings and concerns
3. Business impact
4. Priority recommendations
5. Compliance status
6. Next steps for leadership
"""
        safe_prompt, compliance_info = self._prepare_safe_input(prompt)
        try:
            text, tokens_used = self._call_ai(
                safe_prompt,
                "You are a senior IT consultant preparing executive reports for financial institutions.",
                temperature=0.4,
                max_tokens=1500,
            )
            return self._build_response(text, 0.85, compliance_info, safe_prompt, tokens_used, start_time)
        except Exception as e:
            return self._ai_error_response(e, start_time)
