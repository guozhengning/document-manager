from pathlib import Path

from src.utils.exceptions import AIError
from src.utils.models import ParseResult

def load_prompt_template(prompt_file: Path) -> str:
    """
        读取 Prompt 模板文件。暂不缓存

    Args:
        prompt_file (Path): Prompt 模板文件的路径。

    Returns:
        str: Prompt 模板的内容。

    Raises:
        AIError: 如果无法读取 Prompt 模板文件，则抛出异常。
    """
    try:
        with prompt_file.open("r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise AIError(f"无法读取 Prompt 模板文件: {e}") from e
    
    
def build_ai_input(parse_result: ParseResult, prompt_template: str) -> str:
    """
        构建 AI 输入字符串，将解析结果和 Prompt 模板结合起来。

        包含文件名、路径、清洗后文本，不直接拼接无关元数据

    Args:
        parse_result (ParseResult): 解析结果对象，包含文件的原始文本和清洁文本等信息。
        prompt_template (str): Prompt 模板字符串，包含占位符。

    Returns:
        str: 构建好的 AI 提示词文本。
    """
    prompt = f"""
{prompt_template}

-------------

文件名: {parse_result.file_name}
文件扩展名: {parse_result.extension}
文件路径: {parse_result.file_path}

-------------

清洗后文本:
{parse_result.clean_text}"""
    return prompt







