from pathlib import Path

from src.parser.txt_parser import parse_txt
from src.utils.exceptions import UnsupportedFileError
from src.utils.models import ParseResult

def detect_file_extension(file_path: Path) -> str:
    """
        提取并规范化文件扩展名。

        Args:
            file_path (Path): 待检测文件路径。

        Returns:
            str: 小写扩展名，且始终以 "." 开头，例如 ".txt"。

        Raises:
            UnsupportedFileError: 文件没有扩展名时抛出。
    """

    extension = file_path.suffix.lower()
    if not extension:
        raise UnsupportedFileError(f"文件 {file_path} 没有扩展名，无法处理。")

    return extension



def parse_document(file_path: Path) -> ParseResult:
    """
        根据扩展名分发到具体解析器。

        第一版仅支持 ".txt"。其他格式直接失败，不做兜底解析。

        Args:
            file_path (Path): 要解析的文件路径。
        
        Returns:
            ParseResult: 包含解析结果的对象。

        Raises:
            UnsupportedFileError: 如果文件类型不受支持。    
    """
    extension = detect_file_extension(file_path)
    match extension:
        case ".txt":
            return parse_txt(file_path)
        case _: raise UnsupportedFileError(f"不支持的文件类型：{extension}，文件 {file_path} 无法解析。")
