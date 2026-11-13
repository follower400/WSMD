# 真实法规 / 案例导入指南

## 你现在能直接做什么

本包已经补好了三类内容：

1. `storage/raw/laws.template.jsonl`：法规 JSONL 模板
2. `storage/raw/cases.template.jsonl`：案例 JSONL 模板
3. `scripts/validate_real_exports.py`：检查导入文件格式和字段完整性
4. `scripts/merge_exports.py`：把多个 JSON / JSONL 合并成建库脚本所需的 `laws.jsonl` 和 `cases.jsonl`
5. `scripts/setup_env_from_template.py`：生成根目录 `.env` 的辅助脚本

## 重要说明

- 本包 **没有内置 1000 条真实法规/案例全文**。
- 请使用你**合法取得并可导出**的数据源。
- 建议优先整理与你比赛演示最相关的内容，例如：邻里噪音、夜间扰民、物业费、服务质量、家庭财产、赡养抚养。
- `OPENAI_API_KEY` 需要你自己配置，脚本不会替你生成。

## 文件格式

### 法规 JSONL
每行一条：

```json
{"id":"law-001","title":"中华人民共和国民法典","article":"第二百八十八条","content":"不动产的相邻权利人应当按照有利生产、方便生活、团结互助、公平合理的原则，正确处理相邻关系。","region":"全国","dispute_type":"邻里纠纷","keywords":["相邻关系","邻里","噪音"],"source_url":"https://示例来源","effective_status":"有效"}
```

### 案例 JSONL
每行一条：

```json
{"id":"case-001","title":"夜间装修噪音纠纷调解案例","summary":"装修方夜间施工引发邻里矛盾，最终通过限定施工时段和书面承诺解决。","content":"案情概要：夜间施工持续三天，引发休息受扰。调解过程：核实施工时段，协调物业介入，形成限时施工约定。结果：双方签署书面承诺。","region":"北京","dispute_type":"邻里纠纷","keywords":["装修","噪音","夜间"],"handling_points":["核实时段","书面约定"],"source_url":"https://示例来源"}
```

## 最短落地流程

### 1. 复制模板

- `storage/raw/laws.template.jsonl` -> `storage/raw/laws.jsonl`
- `storage/raw/cases.template.jsonl` -> `storage/raw/cases.jsonl`

### 2. 填入你合法导出的真实数据

### 3. 校验格式

```powershell
python scripts/validate_real_exports.py --laws storage/raw/laws.jsonl --cases storage/raw/cases.jsonl
```

### 4. 生成或更新 `.env`

```powershell
python scripts/setup_env_from_template.py
```

### 5. 建库

```powershell
python ingestion/build_chroma_kb.py --rebuild
```

## 多文件导出时怎么处理

如果你不是一份 `laws.jsonl` / `cases.jsonl`，而是一个目录里很多 JSON / JSONL 文件，可以这样：

```powershell
python scripts/merge_exports.py \
  --laws-dir storage/imports/laws \
  --cases-dir storage/imports/cases \
  --out-laws storage/raw/laws.jsonl \
  --out-cases storage/raw/cases.jsonl
```

## 推荐先做多少条

- 第一次跑通：法规 20 条 + 案例 20 条
- 比赛演示版：法规 100~300 条 + 案例 100~300 条
- 你想冲更完整版本：法规 + 案例总量 1000 条以上

## 验收标准

- 校验脚本通过
- `storage/chroma` 下出现 collection 文件
- `/knowledge/search` 能返回法规和案例
- `/mediate` 在 `.env` 配置了 OpenAI Key 后能切到 RAG 路径
