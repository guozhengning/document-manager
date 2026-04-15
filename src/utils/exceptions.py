



# 配置缺失、字段非法、目录初始化失败。
class ConfigError(Exception): ...

# 文件扩展名不在支持列表中。
class UnsupportedFileError(Exception): ...

# 文本读取失败、编码异常、清洗后文本为空。
class ParseError(Exception): ...

#Prompt 模板读取失败、Mock 分析异常、后续模型调用异常。
class AIError(Exception): ...

#结果写入失败、归档失败、日志写入失败。
class StorageError(Exception): ...

