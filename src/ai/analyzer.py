from pathlib import Path
import jieba
import re
from collections import Counter



from src.utils.models import ParseResult, AIResult, AppSettings
from src.ai.prompting import load_prompt_template, build_ai_input
from src.utils.exceptions import AIError



def analyze_document(parse_result: ParseResult, settings: AppSettings) -> AIResult:
    """对解析结果做分类与摘要。
    
    Args:
        parse_result (ParseResult): 解析结果对象，包含文件的原始文本和清洁文本等信息。
        settings (AppSettings): 应用设置对象，包含各种路径和配置。

    Returns:
        AIResult: 包含分析结果的对象，包括文档类型、摘要、关键词等信息。

    Raises:
        AIError: 如果在分析过程中发生错误，则抛出异常。
    """   
    try:
        # 加载 Prompt 模板
        prompt_template = load_prompt_template(settings.prompt_file)

        # 构建 AI 输入
        ai_input = build_ai_input(parse_result, prompt_template)

        # 调用 AI 模型进行分析
        return mock_analyze_document(parse_result, ai_input)  

    except Exception as e:
        raise AIError(f"分析文档时发生错误: {e}") from e

def mock_analyze_document(parse_result: ParseResult, ai_input: str) -> AIResult:
    """第一版的占位实现，用关键词和截断文本生成结果。

    Args:
        parse_result (ParseResult): 解析结果对象，包含文件的原始文本和清洁文本等信息。
        ai_input (str): 传递给 AI 模型的输入文本。

    Returns:
        AIResult: 包含分析结果的对象，包括文档类型、摘要、关键词等信息。
    """

    if "合同" in parse_result.clean_text or "协议" in parse_result.clean_text:
        type_hint = "合同"
    elif "发票" in parse_result.clean_text or "税额" in parse_result.clean_text:
        type_hint = "发票"
    else:
        type_hint = "待确认"

    summary = parse_result.clean_text[:100] + "..." if len(parse_result.clean_text) > 100 else parse_result.clean_text

    text_cleaned = re.sub(r'[^\w\s]', '', parse_result.clean_text)

    stopwords_file = Path(__file__).with_name("cn_stopwords.txt")
    with stopwords_file.open("r", encoding="utf-8") as f:
        stopwords = set(f.read().splitlines())

    words = jieba.lcut(text_cleaned)
    word_list = []
    for word in words:
        if word not in stopwords :
            word_list.append(word)

    word_freq = Counter(word_list)
    keywords = [word for word, freq in word_freq.most_common(10)]
       

    return AIResult(
        file_name=parse_result.file_name,
        file_path=parse_result.file_path,
        doc_type=type_hint,
        summary=summary,
        keywords=keywords,
        suggested_folder=type_hint,
        suggested_name=f"{Path(parse_result.file_path).stem}_summary",
        confidence=0.9
    )   
