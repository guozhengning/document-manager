from pathlib import Path
import re
from typing import Any

from src.utils.exceptions import ParseError
from src.utils.models import ParseResult


def clean_extracted_text(text: str) -> str:
    """
        清洗提取文本，压缩行内空白并合并连续空行。

        该函数会统一换行符，折叠多余空格/制表符，并保留单个空行
        作为段落边界。
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned_lines: list[str] = []
    previous_blank = False

    for line in normalized.split("\n"):
        cleaned_line = re.sub(r"[ \t\f\v]+", " ", line).strip()

        if not cleaned_line:
            if cleaned_lines and not previous_blank:
                cleaned_lines.append("")
            previous_blank = True
            continue

        cleaned_lines.append(cleaned_line)
        previous_blank = False

    return "\n".join(cleaned_lines).strip()


def build_parse_result(file_path: Path, raw_text: str, metadata: dict[str, Any] | None = None) -> ParseResult:
    """
        统一构造 ParseResult。

        当 metadata 中包含 "cleaned" 时，会以该值作为 clean_text，并在
        清洗结果为空时抛出 ParseError。metadata 为空时自动回落为空字典。
    """
    if metadata and "cleaned" in metadata and not metadata["cleaned"].strip():
        raise ParseError(f"文件 {file_path} 清洗后文本内容为空")

    return ParseResult(
        file_name=file_path.name,
        file_path=str(file_path),
        extension=file_path.suffix.lower(),
        raw_text=raw_text,
        clean_text=metadata.get("cleaned", "") if metadata else "",
        metadata=metadata or {},
    )
