from pathlib import Path

from src.utils.models import AIResult, DocTypeRule, ArchiveRule


def match_doc_type(
        text: str,
        ai_result: AIResult,
        rules: list[DocTypeRule]
) -> str:
    """
    根据规则修正最终文档类型。
    规则命中优先级高于 AI 建议,多条规则命中时按定义顺序取第一条,未命中时保留 AI 输出。

    Args: 
        text: 文本内容
        ai_result: AI结果
        rules: 规则列表

    Return: 最终doc_type
    """
    nomalized_text = text.lower()

    for rule in rules:
        for keyword in rule.keywords:
            if keyword.lower() in nomalized_text:
                return rule.name
          
    return ai_result.doc_type

def resolve_archive_folder(
        doc_type: str,
        rules: list[ArchiveRule]
) -> str:
    """
    根据文档类型决定归档目录
    命中规则时返回对应目录，未命中时使用兜底值 待分类/待确认。

    Args: doc_type、归档规则

    Return: 目标目录字符串
    """
    for rule in rules:
        if doc_type == rule.doc_type:
            return rule.target_folder
    return "待分类/待确认"


def resolve_suggested_name(
        ai_result: AIResult,
        source_path: Path
) -> str:
    """
    生成建议文件名
    优先使用 ai_result.suggested_name，缺失或空字符串时使用原文件名

    Args:
        ai_result: AI结果
        source_path: 源文件路径
    
    Return: 建议文件名
    """
    if ai_result.suggested_name.strip():
        return ai_result.suggested_name
    return source_path.name

def merge_ai_and_rules(
        ai_result: AIResult,
        resolved_doc_type: str, 
        resolved_folder: str, 
        suggested_name: str
) -> AIResult:
    """
    将规则结果覆盖回标准输出对象
    处理规则：只覆盖最终分类、目录和建议名称，不重算摘要和关键词。

    Arges: AI结果，规则决策结果

    Return: 修正后的AI结果
    """
    ai_result.doc_type = resolved_doc_type
    ai_result.suggested_folder = resolved_folder
    ai_result.suggested_name = suggested_name

    return ai_result