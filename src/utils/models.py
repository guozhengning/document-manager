from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AppSettings:
    watch_directory: Path
    result_directory: Path
    archive_directory: Path
    temp_directory: Path
    log_directory: Path
    prompt_file: Path
    supported_extensions: set[str]
    overwrite_existing: bool
    log_level: str
    ai_provider: str
    ai_model: str


@dataclass(slots=True)
class FileJob:
    job_id: str
    file_path: Path
    file_name: str
    extension: str
    status: str = "pending"


@dataclass(slots=True)
class ParseResult:
    file_name: str
    file_path: str
    extension: str
    raw_text: str
    clean_text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AIResult:
    file_name: str
    file_path: str
    doc_type: str
    summary: str
    keywords: list[str]
    suggested_folder: str
    suggested_name: str
    confidence: float


@dataclass(slots=True)
class FinalRecord:
    job_id: str
    source_file: str
    status: str
    doc_type: str
    summary: str
    keywords: list[str]
    suggested_folder: str
    suggested_name: str
    confidence: float
    result_file: str | None
    archive_file: str | None
    error_message: str | None


@dataclass(slots=True)
class DocTypeRule:
    name: str
    keywords: list[str]


@dataclass(slots=True)
class ArchiveRule:
    doc_type: str
    target_folder: str