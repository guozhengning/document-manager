from pathlib import Path

from src.parser.common import build_parse_result, clean_extracted_text
from src.utils.exceptions import ParseError
from src.utils.models import ParseResult


COMMON_TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "gb18030", "gbk")



def parse_txt(file_path: Path) -> ParseResult:
    """
        读取文本文件并构造标准解析结果。

        读取时按常见编码顺序依次尝试：utf-8、utf-8-sig、gb18030、gbk。
        原始文本保留在 raw_text，清洗后的文本通过 build_parse_result()
        写入 clean_text。若文件读取失败、编码均无法解析，或清洗结果为空，
        则抛出 ParseError。
    """
    raw_text: str | None = None
    last_decode_error: UnicodeDecodeError | None = None
    encoding = None
    for e in COMMON_TEXT_ENCODINGS:
        try:
            raw_text = file_path.read_text(encoding=e)
            encoding = e
            break
        except UnicodeDecodeError as e:
            last_decode_error = e
        except OSError as e:
            raise ParseError(f"读取失败：{e}") from e

    if raw_text is None:
        if last_decode_error is not None:
            raise ParseError(f"编码解析失败：{file_path}") from last_decode_error
        raise ParseError(f"读取失败：{file_path}")

    cleaned_text = clean_extracted_text(raw_text)
    parser = "txt"
    return build_parse_result(
        file_path=file_path,
        raw_text=raw_text,
        clean_text=cleaned_text,
        metadata={
            "encoding": encoding,
            "parser": parser,
        },
    )
