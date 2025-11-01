"""
Knowledge Base Loader Utility

This module provides utilities for loading, searching, and managing knowledge base content
including playbooks, categories, and keyword matching functionality.
"""

import asyncio
import json
import re
from typing import Dict, List, Optional, Union, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging

# Try to import structlog, fall back to standard logging if not available
try:
    import structlog
    # Configure structured logger
    logger = structlog.get_logger(__name__)
except ImportError:
    # Fallback to standard logging if structlog is not available
    logger = logging.getLogger(__name__)


class KBFormat(Enum):
    """Supported knowledge base formats."""
    JSON = "json"
    YAML = "yaml"
    MARKDOWN = "markdown"
    TEXT = "text"


@dataclass
class KnowledgeBase:
    """Represents a knowledge base with metadata."""
    name: str
    version: str
    description: str
    categories: Dict[str, "Category"] = field(default_factory=dict)
    playbooks: Dict[str, "Playbook"] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_updated: Optional[str] = None
    source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert knowledge base to dictionary representation."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "categories": {k: v.to_dict() for k, v in self.categories.items()},
            "playbooks": {k: v.to_dict() for k, v in self.playbooks.items()},
            "metadata": self.metadata,
            "last_updated": self.last_updated,
            "source": self.source,
        }


@dataclass
class Category:
    """Represents a knowledge base category."""
    name: str
    description: str
    keywords: List[str] = field(default_factory=list)
    parent_category: Optional[str] = None
    subcategories: List[str] = field(default_factory=list)
    playbook_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert category to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "keywords": self.keywords,
            "parent_category": self.parent_category,
            "subcategories": self.subcategories,
            "playbook_ids": self.playbook_ids,
            "metadata": self.metadata,
        }


@dataclass
class Playbook:
    """Represents a knowledge base playbook."""
    id: str
    title: str
    description: str
    content: str
    category_ids: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    priority: int = 0
    version: str = "1.0"
    author: Optional[str] = None
    last_updated: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert playbook to dictionary representation."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "category_ids": self.category_ids,
            "keywords": self.keywords,
            "tags": self.tags,
            "priority": self.priority,
            "version": self.version,
            "author": self.author,
            "last_updated": self.last_updated,
            "metadata": self.metadata,
        }


class KBLoader:
    """
    Knowledge Base Loader class for loading and managing knowledge base content.
    
    Supports multiple formats (JSON, YAML, Markdown, Text) and provides
    both synchronous and asynchronous loading capabilities.
    """

    # Common keyword matching patterns
    KEYWORD_PATTERNS = {
        "exact": r'\b{keyword}\b',
        "partial": r'{keyword}',
        "case_insensitive": r'\b{keyword}\b',
        "fuzzy": None,  # Requires special handling
    }

    def __init__(self, strict_mode: bool = False, cache_enabled: bool = True):
        """
        Initialize the KB Loader.

        Args:
            strict_mode (bool): If True, raise exceptions on loading errors.
                               If False, log warnings and continue.
            cache_enabled (bool): If True, cache loaded knowledge bases.
        """
        self.strict_mode = strict_mode
        self.cache_enabled = cache_enabled
        self._cache: Dict[str, KnowledgeBase] = {}
        self._keyword_index: Dict[str, Set[str]] = {}  # keyword -> playbook_ids
        
        logger.info(
            "Initialized KBLoader",
            strict_mode=strict_mode,
            cache_enabled=cache_enabled
        )

    async def load_kb(
        self,
        source: Union[str, Path, Dict[str, Any]],
        kb_format: Optional[KBFormat] = None,
        kb_name: Optional[str] = None,
        use_cache: bool = True
    ) -> KnowledgeBase:
        """
        Asynchronously load a knowledge base from various sources.

        Args:
            source (Union[str, Path, Dict]): Source to load from
            kb_format (Optional[KBFormat]): Format of the knowledge base
            kb_name (Optional[str]): Name identifier for the knowledge base
            use_cache (bool): Whether to use cached version if available

        Returns:
            KnowledgeBase: Loaded knowledge base object

        Raises:
            ValueError: If source format is invalid or loading fails
        """
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(source, kb_name)
            
            # Check cache first
            if use_cache and self.cache_enabled and cache_key in self._cache:
                logger.info("Loaded knowledge base from cache", cache_key=cache_key)
                return self._cache[cache_key]

            # Load knowledge base based on source type
            if isinstance(source, dict):
                kb_data = source
            elif isinstance(source, (str, Path)):
                kb_data = await self._load_from_file(source, kb_format)
            else:
                error_msg = f"Unsupported source type: {type(source)}"
                logger.error(error_msg)
                if self.strict_mode:
                    raise ValueError(error_msg)
                raise ValueError(error_msg)

            # Parse and validate knowledge base
            kb = self._parse_kb_data(kb_data, kb_name or "unknown")

            # Build indexes
            self._build_keyword_index(kb)

            # Cache if enabled
            if self.cache_enabled:
                self._cache[cache_key] = kb
                logger.info("Cached knowledge base", cache_key=cache_key)

            logger.info(
                "Successfully loaded knowledge base",
                kb_name=kb.name,
                version=kb.version,
                category_count=len(kb.categories),
                playbook_count=len(kb.playbooks)
            )

            return kb

        except Exception as e:
            error_msg = f"Failed to load knowledge base: {e}"
            logger.error(error_msg, exc_info=True)
            if self.strict_mode:
                raise
            raise

    def load_kb_sync(
        self,
        source: Union[str, Path, Dict[str, Any]],
        kb_format: Optional[KBFormat] = None,
        kb_name: Optional[str] = None,
        use_cache: bool = True
    ) -> KnowledgeBase:
        """
        Synchronously load a knowledge base from various sources.

        Args:
            source (Union[str, Path, Dict]): Source to load from
            kb_format (Optional[KBFormat]): Format of the knowledge base
            kb_name (Optional[str]): Name identifier for the knowledge base
            use_cache (bool): Whether to use cached version if available

        Returns:
            KnowledgeBase: Loaded knowledge base object

        Raises:
            ValueError: If source format is invalid or loading fails
        """
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(source, kb_name)
            
            # Check cache first
            if use_cache and self.cache_enabled and cache_key in self._cache:
                logger.info("Loaded knowledge base from cache", cache_key=cache_key)
                return self._cache[cache_key]

            # Load knowledge base based on source type
            if isinstance(source, dict):
                kb_data = source
            elif isinstance(source, (str, Path)):
                kb_data = self._load_from_file_sync(source, kb_format)
            else:
                error_msg = f"Unsupported source type: {type(source)}"
                logger.error(error_msg)
                if self.strict_mode:
                    raise ValueError(error_msg)
                raise ValueError(error_msg)

            # Parse and validate knowledge base
            kb = self._parse_kb_data(kb_data, kb_name or "unknown")

            # Build indexes
            self._build_keyword_index(kb)

            # Cache if enabled
            if self.cache_enabled:
                self._cache[cache_key] = kb
                logger.info("Cached knowledge base", cache_key=cache_key)

            logger.info(
                "Successfully loaded knowledge base",
                kb_name=kb.name,
                version=kb.version,
                category_count=len(kb.categories),
                playbook_count=len(kb.playbooks)
            )

            return kb

        except Exception as e:
            error_msg = f"Failed to load knowledge base: {e}"
            logger.error(error_msg, exc_info=True)
            if self.strict_mode:
                raise
            raise

    async def _load_from_file(self, file_path: Union[str, Path], kb_format: Optional[KBFormat]) -> Dict[str, Any]:
        """Asynchronously load knowledge base from file."""
        path = Path(file_path)
        
        if not path.exists():
            error_msg = f"File not found: {path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        # Detect format if not provided
        if kb_format is None:
            kb_format = self._detect_format(path)

        # Read file content
        content = await self._read_file_async(path)
        
        # Parse based on format
        return self._parse_content(content, kb_format)

    def _load_from_file_sync(self, file_path: Union[str, Path], kb_format: Optional[KBFormat]) -> Dict[str, Any]:
        """Synchronously load knowledge base from file."""
        path = Path(file_path)
        
        if not path.exists():
            error_msg = f"File not found: {path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        # Detect format if not provided
        if kb_format is None:
            kb_format = self._detect_format(path)

        # Read file content
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse based on format
        return self._parse_content(content, kb_format)

    def _detect_format(self, file_path: Path) -> KBFormat:
        """Detect file format based on extension."""
        extension = file_path.suffix.lower()
        
        format_map = {
            '.json': KBFormat.JSON,
            '.yaml': KBFormat.YAML,
            '.yml': KBFormat.YAML,
            '.md': KBFormat.MARKDOWN,
            '.txt': KBFormat.TEXT,
        }
        
        detected_format = format_map.get(extension)
        if detected_format:
            logger.debug("Detected file format", file_path=file_path, format=detected_format.value)
            return detected_format
        
        # Default to JSON if unknown extension
        logger.warning(f"Unknown file extension, defaulting to JSON: {file_path}")
        return KBFormat.JSON

    async def _read_file_async(self, file_path: Path) -> str:
        """Asynchronously read file content."""
        # In a real async implementation, this would use aiofiles
        # For now, using sync version in async context
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._read_file_sync, file_path)

    def _read_file_sync(self, file_path: Path) -> str:
        """Synchronously read file content."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _parse_content(self, content: str, kb_format: KBFormat) -> Dict[str, Any]:
        """Parse content based on format."""
        try:
            if kb_format == KBFormat.JSON:
                return json.loads(content)
            elif kb_format == KBFormat.YAML:
                # Would use yaml library in real implementation
                raise NotImplementedError("YAML parsing not implemented")
            elif kb_format == KBFormat.MARKDOWN:
                return self._parse_markdown(content)
            elif kb_format == KBFormat.TEXT:
                return self._parse_text(content)
            else:
                error_msg = f"Unsupported format: {kb_format}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Failed to parse content as {kb_format.value}: {e}"
            logger.error(error_msg, exc_info=True)
            raise

    def _parse_markdown(self, content: str) -> Dict[str, Any]:
        """Parse markdown content into knowledge base structure."""
        # Simple markdown parsing - extract headers and content
        lines = content.split('\n')
        kb_data = {
            "name": "Markdown KB",
            "version": "1.0",
            "description": "Knowledge base loaded from markdown",
            "categories": {},
            "playbooks": {}
        }
        
        current_category = None
        current_playbook = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Category header (##)
            if line.startswith('## '):
                category_name = line[3:].strip()
                current_category = category_name
                kb_data["categories"][category_name] = {
                    "name": category_name,
                    "description": "",
                    "keywords": [],
                    "playbook_ids": []
                }
            
            # Playbook header (###)
            elif line.startswith('### '):
                playbook_title = line[4:].strip()
                playbook_id = playbook_title.lower().replace(' ', '_')
                current_playbook = playbook_id
                
                kb_data["playbooks"][playbook_id] = {
                    "id": playbook_id,
                    "title": playbook_title,
                    "description": "",
                    "content": "",
                    "category_ids": [current_category] if current_category else [],
                    "keywords": [],
                    "tags": []
                }
                
                if current_category:
                    kb_data["categories"][current_category]["playbook_ids"].append(playbook_id)
            
            # Content line
            elif current_playbook and line:
                if not kb_data["playbooks"][current_playbook]["content"]:
                    kb_data["playbooks"][current_playbook]["description"] = line
                kb_data["playbooks"][current_playbook]["content"] += line + "\n"
        
        return kb_data

    def _parse_text(self, content: str) -> Dict[str, Any]:
        """Parse plain text content into knowledge base structure."""
        # Simple text parsing - split by empty lines
        sections = content.split('\n\n')
        
        kb_data = {
            "name": "Text KB",
            "version": "1.0",
            "description": "Knowledge base loaded from text",
            "categories": {},
            "playbooks": {}
        }
        
        for i, section in enumerate(sections):
            if not section.strip():
                continue
            
            lines = section.strip().split('\n')
            title = lines[0].strip()
            
            playbook_id = f"playbook_{i}"
            kb_data["playbooks"][playbook_id] = {
                "id": playbook_id,
                "title": title,
                "description": lines[1].strip() if len(lines) > 1 else "",
                "content": section,
                "category_ids": [],
                "keywords": [],
                "tags": []
            }
        
        return kb_data

    def _parse_kb_data(self, kb_data: Dict[str, Any], kb_name: str) -> KnowledgeBase:
        """Parse knowledge base data into KnowledgeBase object."""
        try:
            # Extract metadata
            name = kb_data.get("name", kb_name)
            version = kb_data.get("version", "1.0")
            description = kb_data.get("description", "")
            last_updated = kb_data.get("last_updated")
            source = kb_data.get("source")
            metadata = kb_data.get("metadata", {})

            # Parse categories
            categories = {}
            for cat_id, cat_data in kb_data.get("categories", {}).items():
                categories[cat_id] = Category(
                    name=cat_data.get("name", cat_id),
                    description=cat_data.get("description", ""),
                    keywords=cat_data.get("keywords", []),
                    parent_category=cat_data.get("parent_category"),
                    subcategories=cat_data.get("subcategories", []),
                    playbook_ids=cat_data.get("playbook_ids", []),
                    metadata=cat_data.get("metadata", {})
                )

            # Parse playbooks
            playbooks = {}
            for pb_id, pb_data in kb_data.get("playbooks", {}).items():
                playbooks[pb_id] = Playbook(
                    id=pb_data.get("id", pb_id),
                    title=pb_data.get("title", pb_id),
                    description=pb_data.get("description", ""),
                    content=pb_data.get("content", ""),
                    category_ids=pb_data.get("category_ids", []),
                    keywords=pb_data.get("keywords", []),
                    tags=pb_data.get("tags", []),
                    priority=pb_data.get("priority", 0),
                    version=pb_data.get("version", "1.0"),
                    author=pb_data.get("author"),
                    last_updated=pb_data.get("last_updated"),
                    metadata=pb_data.get("metadata", {})
                )

            kb = KnowledgeBase(
                name=name,
                version=version,
                description=description,
                categories=categories,
                playbooks=playbooks,
                metadata=metadata,
                last_updated=last_updated,
                source=source
            )

            logger.debug("Parsed knowledge base data", kb_name=name, category_count=len(categories))
            return kb

        except Exception as e:
            error_msg = f"Failed to parse knowledge base data: {e}"
            logger.error(error_msg, exc_info=True)
            raise ValueError(error_msg)

    def _build_keyword_index(self, kb: KnowledgeBase) -> None:
        """Build keyword index for faster searching."""
        for playbook_id, playbook in kb.playbooks.items():
            # Index playbook keywords
            for keyword in playbook.keywords:
                keyword_lower = keyword.lower()
                if keyword_lower not in self._keyword_index:
                    self._keyword_index[keyword_lower] = set()
                self._keyword_index[keyword_lower].add(playbook_id)
            
            # Index title words
            for word in playbook.title.lower().split():
                if word not in self._keyword_index:
                    self._keyword_index[word] = set()
                self._keyword_index[word].add(playbook_id)
            
            # Index tag words
            for tag in playbook.tags:
                tag_lower = tag.lower()
                if tag_lower not in self._keyword_index:
                    self._keyword_index[tag_lower] = set()
                self._keyword_index[tag_lower].add(playbook_id)
            
            # Index description words
            for word in playbook.description.lower().split():
                if len(word) > 3:  # Only index words longer than 3 characters
                    if word not in self._keyword_index:
                        self._keyword_index[word] = set()
                    self._keyword_index[word].add(playbook_id)
        
        logger.debug("Built keyword index", index_size=len(self._keyword_index))

    def _generate_cache_key(self, source: Union[str, Path, Dict], kb_name: Optional[str]) -> str:
        """Generate cache key for source."""
        if isinstance(source, dict):
            return f"dict_{hash(json.dumps(source, sort_keys=True))}"
        elif isinstance(source, (str, Path)):
            return f"{kb_name or 'kb'}_{str(source)}"
        else:
            return f"{kb_name or 'kb'}_{type(source).__name__}"

    async def find_category(
        self,
        kb: KnowledgeBase,
        query: str,
        match_type: str = "keywords",
        threshold: float = 0.5
    ) -> List[Category]:
        """
        Asynchronously find categories matching a query.

        Args:
            kb (KnowledgeBase): Knowledge base to search in
            query (str): Search query
            match_type (str): Type of matching ("keywords", "fuzzy", "exact")
            threshold (float): Similarity threshold for fuzzy matching

        Returns:
            List[Category]: List of matching categories
        """
        try:
            logger.debug("Finding categories", query=query, match_type=match_type)
            
            matching_categories = []
            query_lower = query.lower()
            
            for category in kb.categories.values():
                score = self._calculate_category_match_score(category, query_lower, match_type)
                
                if score >= threshold:
                    # Add score to metadata for sorting
                    category.metadata = {**category.metadata, "match_score": score}
                    matching_categories.append(category)
            
            # Sort by match score (descending)
            matching_categories.sort(key=lambda c: c.metadata.get("match_score", 0), reverse=True)
            
            logger.info(
                "Found categories",
                query=query,
                match_count=len(matching_categories),
                match_type=match_type
            )
            
            return matching_categories

        except Exception as e:
            error_msg = f"Failed to find categories: {e}"
            logger.error(error_msg, exc_info=True)
            if self.strict_mode:
                raise
            raise

    def find_category_sync(
        self,
        kb: KnowledgeBase,
        query: str,
        match_type: str = "keywords",
        threshold: float = 0.5
    ) -> List[Category]:
        """
        Synchronously find categories matching a query.

        Args:
            kb (KnowledgeBase): Knowledge base to search in
            query (str): Search query
            match_type (str): Type of matching ("keywords", "fuzzy", "exact")
            threshold (float): Similarity threshold for fuzzy matching

        Returns:
            List[Category]: List of matching categories
        """
        try:
            logger.debug("Finding categories", query=query, match_type=match_type)
            
            matching_categories = []
            query_lower = query.lower()
            
            for category in kb.categories.values():
                score = self._calculate_category_match_score(category, query_lower, match_type)
                
                if score >= threshold:
                    # Add score to metadata for sorting
                    category.metadata = {**category.metadata, "match_score": score}
                    matching_categories.append(category)
            
            # Sort by match score (descending)
            matching_categories.sort(key=lambda c: c.metadata.get("match_score", 0), reverse=True)
            
            logger.info(
                "Found categories",
                query=query,
                match_count=len(matching_categories),
                match_type=match_type
            )
            
            return matching_categories

        except Exception as e:
            error_msg = f"Failed to find categories: {e}"
            logger.error(error_msg, exc_info=True)
            if self.strict_mode:
                raise
            raise

    def _calculate_category_match_score(self, category: Category, query: str, match_type: str) -> float:
        """Calculate match score between category and query."""
        try:
            if match_type == "exact":
                # Exact match on name or description
                if query in category.name.lower() or query in category.description.lower():
                    return 1.0
                return 0.0
            
            elif match_type == "keywords":
                # Check keyword matches
                score = 0.0
                max_score = len(category.keywords) + 2  # +2 for name and description
                
                if query in category.name.lower():
                    score += 2
                
                if query in category.description.lower():
                    score += 1
                
                for keyword in category.keywords:
                    if query in keyword.lower():
                        score += 1
                
                return min(score / max_score, 1.0) if max_score > 0 else 0.0
            
            elif match_type == "fuzzy":
                # Simple fuzzy matching (can be enhanced with libraries like fuzzywuzzy)
                query_words = set(query.split())
                
                name_words = set(category.name.lower().split())
                desc_words = set(category.description.lower().split())
                keyword_words = set(k.lower() for k in category.keywords)
                
                all_words = name_words | desc_words | keyword_words
                
                if not all_words:
                    return 0.0
                
                # Calculate Jaccard similarity
                intersection = query_words & all_words
                union = query_words | all_words
                
                return len(intersection) / len(union) if union else 0.0
            
            else:
                logger.warning(f"Unknown match type: {match_type}")
                return 0.0
                
        except Exception as e:
            logger.error(f"Failed to calculate match score: {e}")
            return 0.0

    async def get_playbook(
        self,
        kb: KnowledgeBase,
        playbook_id: Optional[str] = None,
        query: Optional[str] = None,
        category_id: Optional[str] = None,
        max_results: int = 10
    ) -> Union[Optional[Playbook], List[Playbook]]:
        """
        Asynchronously get playbook(s) from knowledge base.

        Args:
            kb (KnowledgeBase): Knowledge base to search in
            playbook_id (Optional[str]): Specific playbook ID to retrieve
            query (Optional[str]): Search query to find playbooks
            category_id (Optional[str]): Filter by category ID
            max_results (int): Maximum number of results to return

        Returns:
            Union[Optional[Playbook], List[Playbook]]: Single playbook or list of playbooks
        """
        try:
            # If playbook_id is provided, return specific playbook
            if playbook_id:
                playbook = kb.playbooks.get(playbook_id)
                if playbook:
                    logger.debug("Retrieved playbook by ID", playbook_id=playbook_id)
                    return playbook
                else:
                    logger.warning("Playbook not found", playbook_id=playbook_id)
                    return None

            # Otherwise, search based on query and/or category
            matching_playbooks = []
            
            for playbook in kb.playbooks.values():
                # Filter by category if specified
                if category_id and category_id not in playbook.category_ids:
                    continue
                
                # Filter by query if specified
                if query:
                    score = self._calculate_playbook_match_score(playbook, query.lower())
                    if score < 0.3:  # Minimum threshold
                        continue
                    playbook.metadata = {**playbook.metadata, "match_score": score}
                
                matching_playbooks.append(playbook)
            
            # Sort by priority and match score if query provided
            if query:
                matching_playbooks.sort(
                    key=lambda p: (p.priority, p.metadata.get("match_score", 0)),
                    reverse=True
                )
            else:
                matching_playbooks.sort(key=lambda p: p.priority, reverse=True)
            
            # Limit results
            result = matching_playbooks[:max_results]
            
            logger.info(
                "Retrieved playbooks",
                playbook_id=playbook_id,
                query=query,
                category_id=category_id,
                result_count=len(result)
            )
            
            return result if not playbook_id else (result[0] if result else None)

        except Exception as e:
            error_msg = f"Failed to get playbook: {e}"
            logger.error(error_msg, exc_info=True)
            if self.strict_mode:
                raise
            raise

    def get_playbook_sync(
        self,
        kb: KnowledgeBase,
        playbook_id: Optional[str] = None,
        query: Optional[str] = None,
        category_id: Optional[str] = None,
        max_results: int = 10
    ) -> Union[Optional[Playbook], List[Playbook]]:
        """
        Synchronously get playbook(s) from knowledge base.

        Args:
            kb (KnowledgeBase): Knowledge base to search in
            playbook_id (Optional[str]): Specific playbook ID to retrieve
            query (Optional[str]): Search query to find playbooks
            category_id (Optional[str]): Filter by category ID
            max_results (int): Maximum number of results to return

        Returns:
            Union[Optional[Playbook], List[Playbook]]: Single playbook or list of playbooks
        """
        try:
            # If playbook_id is provided, return specific playbook
            if playbook_id:
                playbook = kb.playbooks.get(playbook_id)
                if playbook:
                    logger.debug("Retrieved playbook by ID", playbook_id=playbook_id)
                    return playbook
                else:
                    logger.warning("Playbook not found", playbook_id=playbook_id)
                    return None

            # Otherwise, search based on query and/or category
            matching_playbooks = []
            
            for playbook in kb.playbooks.values():
                # Filter by category if specified
                if category_id and category_id not in playbook.category_ids:
                    continue
                
                # Filter by query if specified
                if query:
                    score = self._calculate_playbook_match_score(playbook, query.lower())
                    if score < 0.3:  # Minimum threshold
                        continue
                    playbook.metadata = {**playbook.metadata, "match_score": score}
                
                matching_playbooks.append(playbook)
            
            # Sort by priority and match score if query provided
            if query:
                matching_playbooks.sort(
                    key=lambda p: (p.priority, p.metadata.get("match_score", 0)),
                    reverse=True
                )
            else:
                matching_playbooks.sort(key=lambda p: p.priority, reverse=True)
            
            # Limit results
            result = matching_playbooks[:max_results]
            
            logger.info(
                "Retrieved playbooks",
                playbook_id=playbook_id,
                query=query,
                category_id=category_id,
                result_count=len(result)
            )
            
            return result if not playbook_id else (result[0] if result else None)

        except Exception as e:
            error_msg = f"Failed to get playbook: {e}"
            logger.error(error_msg, exc_info=True)
            if self.strict_mode:
                raise
            raise

    def _calculate_playbook_match_score(self, playbook: Playbook, query: str) -> float:
        """Calculate match score between playbook and query."""
        try:
            query_words = set(query.split())
            
            # Check title
            title_words = set(playbook.title.lower().split())
            title_score = len(query_words & title_words) / len(query_words) if query_words else 0
            
            # Check keywords
            keyword_score = 0
            for keyword in playbook.keywords:
                if query in keyword.lower():
                    keyword_score += 1
            keyword_score = min(keyword_score / len(playbook.keywords), 1.0) if playbook.keywords else 0
            
            # Check tags
            tag_score = 0
            for tag in playbook.tags:
                if query in tag.lower():
                    tag_score += 1
            tag_score = min(tag_score / len(playbook.tags), 1.0) if playbook.tags else 0
            
            # Check description
            desc_words = set(playbook.description.lower().split())
            desc_score = len(query_words & desc_words) / len(query_words) if query_words else 0
            
            # Weighted average
            total_score = (
                title_score * 0.4 +
                keyword_score * 0.3 +
                tag_score * 0.2 +
                desc_score * 0.1
            )
            
            return total_score
            
        except Exception as e:
            logger.error(f"Failed to calculate playbook match score: {e}")
            return 0.0

    async def match_keywords(
        self,
        kb: KnowledgeBase,
        keywords: Union[str, List[str]],
        match_type: str = "any",
        use_index: bool = True,
        threshold: float = 0.0
    ) -> List[Tuple[Playbook, float]]:
        """
        Asynchronously match keywords against playbooks.

        Args:
            kb (KnowledgeBase): Knowledge base to search in
            keywords (Union[str, List[str]]): Keywords to match
            match_type (str): Type of matching ("any", "all", "exact")
            use_index (bool): Whether to use keyword index for faster search
            threshold (float): Minimum match score threshold

        Returns:
            List[Tuple[Playbook, float]]: List of (playbook, score) tuples
        """
        try:
            # Normalize keywords
            if isinstance(keywords, str):
                keyword_list = [keywords]
            else:
                keyword_list = keywords
            
            logger.debug(
                "Matching keywords",
                keywords=keyword_list,
                match_type=match_type,
                use_index=use_index
            )
            
            matched_playbooks = []
            
            if use_index and self._keyword_index:
                # Use keyword index for faster search
                matched_ids = set()
                
                for keyword in keyword_list:
                    keyword_lower = keyword.lower()
                    keyword_ids = self._keyword_index.get(keyword_lower, set())
                    
                    if match_type == "any":
                        matched_ids |= keyword_ids
                    elif match_type == "all":
                        if not matched_ids:
                            matched_ids = keyword_ids
                        else:
                            matched_ids &= keyword_ids
                    elif match_type == "exact":
                        # For exact match, only consider if all keywords match
                        if keyword_lower in [k.lower() for k in kb.playbooks[list(keyword_ids)[0]].keywords] if keyword_ids else False:
                            matched_ids |= keyword_ids
                
                # Get playbooks for matched IDs
                for playbook_id in matched_ids:
                    playbook = kb.playbooks.get(playbook_id)
                    if playbook:
                        # Calculate actual match score
                        score = self._calculate_keyword_match_score(playbook, keyword_list)
                        if score >= threshold:
                            matched_playbooks.append((playbook, score))
            
            else:
                # Fallback to sequential search
                for playbook in kb.playbooks.values():
                    score = self._calculate_keyword_match_score(playbook, keyword_list)
                    if score >= threshold:
                        matched_playbooks.append((playbook, score))
            
            # Sort by score (descending)
            matched_playbooks.sort(key=lambda x: x[1], reverse=True)
            
            logger.info(
                "Matched keywords",
                keywords=keyword_list,
                match_count=len(matched_playbooks),
                match_type=match_type
            )
            
            return matched_playbooks

        except Exception as e:
            error_msg = f"Failed to match keywords: {e}"
            logger.error(error_msg, exc_info=True)
            if self.strict_mode:
                raise
            raise

    def match_keywords_sync(
        self,
        kb: KnowledgeBase,
        keywords: Union[str, List[str]],
        match_type: str = "any",
        use_index: bool = True,
        threshold: float = 0.0
    ) -> List[Tuple[Playbook, float]]:
        """
        Synchronously match keywords against playbooks.

        Args:
            kb (KnowledgeBase): Knowledge base to search in
            keywords (Union[str, List[str]]): Keywords to match
            match_type (str): Type of matching ("any", "all", "exact")
            use_index (bool): Whether to use keyword index for faster search
            threshold (float): Minimum match score threshold

        Returns:
            List[Tuple[Playbook, float]]: List of (playbook, score) tuples
        """
        try:
            # Normalize keywords
            if isinstance(keywords, str):
                keyword_list = [keywords]
            else:
                keyword_list = keywords
            
            logger.debug(
                "Matching keywords",
                keywords=keyword_list,
                match_type=match_type,
                use_index=use_index
            )
            
            matched_playbooks = []
            
            if use_index and self._keyword_index:
                # Use keyword index for faster search
                matched_ids = set()
                
                for keyword in keyword_list:
                    keyword_lower = keyword.lower()
                    keyword_ids = self._keyword_index.get(keyword_lower, set())
                    
                    if match_type == "any":
                        matched_ids |= keyword_ids
                    elif match_type == "all":
                        if not matched_ids:
                            matched_ids = keyword_ids
                        else:
                            matched_ids &= keyword_ids
                    elif match_type == "exact":
                        # For exact match, only consider if all keywords match
                        if keyword_lower in [k.lower() for k in kb.playbooks[list(keyword_ids)[0]].keywords] if keyword_ids else False:
                            matched_ids |= keyword_ids
                
                # Get playbooks for matched IDs
                for playbook_id in matched_ids:
                    playbook = kb.playbooks.get(playbook_id)
                    if playbook:
                        # Calculate actual match score
                        score = self._calculate_keyword_match_score(playbook, keyword_list)
                        if score >= threshold:
                            matched_playbooks.append((playbook, score))
            
            else:
                # Fallback to sequential search
                for playbook in kb.playbooks.values():
                    score = self._calculate_keyword_match_score(playbook, keyword_list)
                    if score >= threshold:
                        matched_playbooks.append((playbook, score))
            
            # Sort by score (descending)
            matched_playbooks.sort(key=lambda x: x[1], reverse=True)
            
            logger.info(
                "Matched keywords",
                keywords=keyword_list,
                match_count=len(matched_playbooks),
                match_type=match_type
            )
            
            return matched_playbooks

        except Exception as e:
            error_msg = f"Failed to match keywords: {e}"
            logger.error(error_msg, exc_info=True)
            if self.strict_mode:
                raise
            raise

    def _calculate_keyword_match_score(self, playbook: Playbook, keywords: List[str]) -> float:
        """Calculate keyword match score for a playbook."""
        try:
            keyword_lower = [k.lower() for k in keywords]
            
            # Check title matches
            title_lower = playbook.title.lower()
            title_matches = sum(1 for k in keyword_lower if k in title_lower)
            
            # Check keyword matches
            playbook_keywords_lower = [k.lower() for k in playbook.keywords]
            keyword_matches = sum(1 for k in keyword_lower if k in playbook_keywords_lower)
            
            # Check tag matches
            playbook_tags_lower = [t.lower() for t in playbook.tags]
            tag_matches = sum(1 for k in keyword_lower if k in playbook_tags_lower)
            
            # Calculate weighted score
            max_matches = len(keyword_lower)
            if max_matches == 0:
                return 0.0
            
            score = (
                title_matches * 0.5 +
                keyword_matches * 0.3 +
                tag_matches * 0.2
            ) / max_matches
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Failed to calculate keyword match score: {e}")
            return 0.0

    def clear_cache(self) -> None:
        """Clear the knowledge base cache."""
        self._cache.clear()
        logger.info("Cleared knowledge base cache")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "keyword_index_size": len(self._keyword_index),
            "cached_kb_names": list(self._cache.keys())
        }


# Convenience functions for common use cases
async def load_kb(
    source: Union[str, Path, Dict[str, Any]],
    kb_format: Optional[KBFormat] = None,
    kb_name: Optional[str] = None
) -> KnowledgeBase:
    """
    Convenience function to asynchronously load a knowledge base.

    Args:
        source (Union[str, Path, Dict]): Source to load from
        kb_format (Optional[KBFormat]): Format of the knowledge base
        kb_name (Optional[str]): Name identifier for the knowledge base

    Returns:
        KnowledgeBase: Loaded knowledge base object
    """
    loader = KBLoader()
    return await loader.load_kb(source, kb_format, kb_name)


def load_kb_sync(
    source: Union[str, Path, Dict[str, Any]],
    kb_format: Optional[KBFormat] = None,
    kb_name: Optional[str] = None
) -> KnowledgeBase:
    """
    Convenience function to synchronously load a knowledge base.

    Args:
        source (Union[str, Path, Dict]): Source to load from
        kb_format (Optional[KBFormat]): Format of the knowledge base
        kb_name (Optional[str]): Name identifier for the knowledge base

    Returns:
        KnowledgeBase: Loaded knowledge base object
    """
    loader = KBLoader()
    return loader.load_kb_sync(source, kb_format, kb_name)


async def find_category(
    kb: KnowledgeBase,
    query: str,
    match_type: str = "keywords",
    threshold: float = 0.5
) -> List[Category]:
    """
    Convenience function to asynchronously find categories.

    Args:
        kb (KnowledgeBase): Knowledge base to search in
        query (str): Search query
        match_type (str): Type of matching
        threshold (float): Similarity threshold

    Returns:
        List[Category]: List of matching categories
    """
    loader = KBLoader()
    return await loader.find_category(kb, query, match_type, threshold)


def find_category_sync(
    kb: KnowledgeBase,
    query: str,
    match_type: str = "keywords",
    threshold: float = 0.5
) -> List[Category]:
    """
    Convenience function to synchronously find categories.

    Args:
        kb (KnowledgeBase): Knowledge base to search in
        query (str): Search query
        match_type (str): Type of matching
        threshold (float): Similarity threshold

    Returns:
        List[Category]: List of matching categories
    """
    loader = KBLoader()
    return loader.find_category_sync(kb, query, match_type, threshold)


async def get_playbook(
    kb: KnowledgeBase,
    playbook_id: Optional[str] = None,
    query: Optional[str] = None,
    category_id: Optional[str] = None,
    max_results: int = 10
) -> Union[Optional[Playbook], List[Playbook]]:
    """
    Convenience function to asynchronously get playbook(s).

    Args:
        kb (KnowledgeBase): Knowledge base to search in
        playbook_id (Optional[str]): Specific playbook ID to retrieve
        query (Optional[str]): Search query to find playbooks
        category_id (Optional[str]): Filter by category ID
        max_results (int): Maximum number of results to return

    Returns:
        Union[Optional[Playbook], List[Playbook]]: Single playbook or list of playbooks
    """
    loader = KBLoader()
    return await loader.get_playbook(kb, playbook_id, query, category_id, max_results)


def get_playbook_sync(
    kb: KnowledgeBase,
    playbook_id: Optional[str] = None,
    query: Optional[str] = None,
    category_id: Optional[str] = None,
    max_results: int = 10
) -> Union[Optional[Playbook], List[Playbook]]:
    """
    Convenience function to synchronously get playbook(s).

    Args:
        kb (KnowledgeBase): Knowledge base to search in
        playbook_id (Optional[str]): Specific playbook ID to retrieve
        query (Optional[str]): Search query to find playbooks
        category_id (Optional[str]): Filter by category ID
        max_results (int): Maximum number of results to return

    Returns:
        Union[Optional[Playbook], List[Playbook]]: Single playbook or list of playbooks
    """
    loader = KBLoader()
    return loader.get_playbook_sync(kb, playbook_id, query, category_id, max_results)


async def match_keywords(
    kb: KnowledgeBase,
    keywords: Union[str, List[str]],
    match_type: str = "any",
    use_index: bool = True,
    threshold: float = 0.0
) -> List[Tuple[Playbook, float]]:
    """
    Convenience function to asynchronously match keywords.

    Args:
        kb (KnowledgeBase): Knowledge base to search in
        keywords (Union[str, List[str]]): Keywords to match
        match_type (str): Type of matching
        use_index (bool): Whether to use keyword index
        threshold (float): Minimum match score threshold

    Returns:
        List[Tuple[Playbook, float]]: List of (playbook, score) tuples
    """
    loader = KBLoader()
    return await loader.match_keywords(kb, keywords, match_type, use_index, threshold)


def match_keywords_sync(
    kb: KnowledgeBase,
    keywords: Union[str, List[str]],
    match_type: str = "any",
    use_index: bool = True,
    threshold: float = 0.0
) -> List[Tuple[Playbook, float]]:
    """
    Convenience function to synchronously match keywords.

    Args:
        kb (KnowledgeBase): Knowledge base to search in
        keywords (Union[str, List[str]]): Keywords to match
        match_type (str): Type of matching
        use_index (bool): Whether to use keyword index
        threshold (float): Minimum match score threshold

    Returns:
        List[Tuple[Playbook, float]]: List of (playbook, score) tuples
    """
    loader = KBLoader()
    return loader.match_keywords_sync(kb, keywords, match_type, use_index, threshold)


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
    async def example_async():
        """Example of async usage."""
        # Create sample knowledge base data
        kb_data = {
            "name": "Example KB",
            "version": "1.0",
            "description": "Example knowledge base",
            "categories": {
                "security": {
                    "name": "Security",
                    "description": "Security-related playbooks",
                    "keywords": ["security", "protection", "threat"],
                    "playbook_ids": ["firewall_config", "incident_response"]
                }
            },
            "playbooks": {
                "firewall_config": {
                    "id": "firewall_config",
                    "title": "Firewall Configuration",
                    "description": "Configure firewall settings",
                    "content": "Step-by-step firewall configuration guide...",
                    "category_ids": ["security"],
                    "keywords": ["firewall", "network", "security"],
                    "tags": ["network", "security"],
                    "priority": 10
                },
                "incident_response": {
                    "id": "incident_response",
                    "title": "Incident Response",
                    "description": "Handle security incidents",
                    "content": "Incident response procedures...",
                    "category_ids": ["security"],
                    "keywords": ["incident", "response", "security"],
                    "tags": ["security", "response"],
                    "priority": 5
                }
            }
        }
        
        # Load knowledge base
        loader = KBLoader()
        kb = await loader.load_kb(kb_data, kb_name="example")
        
        print(f"Loaded KB: {kb.name}")
        print(f"Categories: {list(kb.categories.keys())}")
        print(f"Playbooks: {list(kb.playbooks.keys())}")
        
        # Find categories
        categories = await loader.find_category(kb, "security")
        print(f"\nFound {len(categories)} categories for 'security'")
        
        # Get playbooks
        playbooks = await loader.get_playbook(kb, query="firewall")
        print(f"\nFound {len(playbooks)} playbooks for 'firewall'")
        if playbooks:
            print(f"Top result: {playbooks[0].title}")
        
        # Match keywords
        matches = await loader.match_keywords(kb, "security incident")
        print(f"\nMatched {len(matches)} playbooks for keywords")
        
        return kb
    
    def example_sync():
        """Example of sync usage."""
        # Create sample knowledge base data
        kb_data = {
            "name": "Example KB Sync",
            "version": "1.0",
            "description": "Example knowledge base",
            "categories": {
                "network": {
                    "name": "Network",
                    "description": "Network-related playbooks",
                    "keywords": ["network", "tcp", "ip"],
                    "playbook_ids": ["network_troubleshooting"]
                }
            },
            "playbooks": {
                "network_troubleshooting": {
                    "id": "network_troubleshooting",
                    "title": "Network Troubleshooting",
                    "description": "Troubleshoot network issues",
                    "content": "Network troubleshooting guide...",
                    "category_ids": ["network"],
                    "keywords": ["network", "troubleshooting", "connectivity"],
                    "tags": ["network"],
                    "priority": 8
                }
            }
        }
        
        # Load knowledge base
        loader = KBLoader()
        kb = loader.load_kb_sync(kb_data, kb_name="example_sync")
        
        print(f"Loaded KB: {kb.name}")
        print(f"Categories: {list(kb.categories.keys())}")
        print(f"Playbooks: {list(kb.playbooks.keys())}")
        
        # Find categories
        categories = loader.find_category_sync(kb, "network")
        print(f"\nFound {len(categories)} categories for 'network'")
        
        # Get playbooks
        playbooks = loader.get_playbook_sync(kb, query="troubleshooting")
        print(f"\nFound {len(playbooks)} playbooks for 'troubleshooting'")
        if playbooks:
            print(f"Top result: {playbooks[0].title}")
        
        # Match keywords
        matches = loader.match_keywords_sync(kb, "network connectivity")
        print(f"\nMatched {len(matches)} playbooks for keywords")
        
        return kb
    
    # Run examples
    print("=== Async Example ===")
    asyncio.run(example_async())
    
    print("\n=== Sync Example ===")
    example_sync()
