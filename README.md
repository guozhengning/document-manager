# 文档管理系统

一个面向课程演示与后续开发的 Python 项目骨架，用于承载文档监听、解析、AI 分析、结果保存与归档流程。

当前仓库只完成目录与占位文件初始化，尚未实现实际业务逻辑。

## 运行方式

1. 使用 Python 3.14 或更高版本。
2. 按需创建虚拟环境并安装依赖。
3. 参考 `.env.example` 与 `config/settings.example.yaml` 补齐本地配置。
4. 当前主入口为 `main.py`，后续业务流程从这里接入。

示例命令：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## 当前状态

- 已补齐推荐的核心目录结构
- 已添加高价值配置、测试、演示模板文件
- 尚未实现监听、解析、AI 调用、存储与工作流逻辑

## 文档索引

- `docs/first_version_interface.md`：第一版接口草案，定义最小可运行闭环和关键函数清单
- `docs/detailed_design_v1.md`：第一版详细设计，补齐模块职责、数据结构、接口边界、规则、异常和测试约束

## 目录结构

```text
document manager/
  src/
    watcher/
    parser/
    ai/
    storage/
    workflow/
    utils/

  config/
    settings.example.yaml
    rules.example.json
  prompts/
    document_analysis.txt
  data/
    inbox/
      README.md
    results/
      README.md
    logs/
      README.md
    archive/
      README.md
    temp/
      README.md
  samples/
    raw/
      README.md
    labeled/
      README.md
  tests/
    cases/
      manual_test_cases.md
    reports/
      bug_list.md
    项目总说明与开发要求.md
  scripts/
    README.md
  .env.example
  .gitignore
  .python-version
  README.md
  requirements.txt
  pyproject.toml
  main.py
```

## 目录说明

- `src/`：核心代码目录
- `config/`：示例配置与规则模板
- `prompts/`：Prompt 模板
- `data/`：运行过程中的输入、输出、日志、归档与临时文件
- `samples/`：测试样本与标注样本说明
- `tests/`：测试场景与结果记录
- `docs/`：项目说明、架构、分工、汇报与演示资料
- `scripts/`：一次性脚本或初始化脚本

## 注意事项

- `pyproject.toml` 作为主项目配置文件保留。
- `requirements.txt` 作为课程/交付兼容清单，默认与 `pyproject.toml` 保持同步。
- `.env.example` 与 `config/*.example.*` 仅提供模板，不应直接提交真实密钥或本机路径。
- `data/logs/` 与 `data/temp/` 下的实际运行产物默认不纳入版本控制。
