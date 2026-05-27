# COC 7th Edition 480购点角色卡生成器

CLI 工具，用于校验和渲染 COC 7版 480购点制角色卡。

**架构**：大模型/Agent 负责交互引导生成 JSON → CLI 负责严格校验 + 渲染 HTML 角色卡。

---

## 安装

```bash
cd coc_generator
pip install -e .
```

依赖：Python 3.10+，Jinja2。

---

## CLI 命令

### 1. 校验角色卡 JSON

```bash
coc verify character.json
```

输出 JSON 格式的校验报告：

```json
{
  "valid": true,
  "errors": [],
  "warnings": [],
  "derived": {
    "hp": 11,
    "mp": 10,
    "san": 50,
    "db": "0",
    "build": 0,
    "mov": 7,
    "dodge": 30,
    "native_language": 70,
    "pro_points_total": 220,
    "pro_points_used": 140,
    "pro_points_remaining": 80,
    "interest_points_total": 160,
    "interest_points_used": 110,
    "interest_points_remaining": 50
  }
}
```

如果校验不通过，`valid` 为 `false`，`errors` 数组包含所有违规项，每条 error 都有 `code`、`field`、`expected`、`actual`、`message`，方便大模型解析并自动修正。

### 2. 生成 HTML 角色卡

```bash
coc render character.json -o card.html
```

- 必须先通过校验，否则拒绝生成
- 生成的 HTML 用浏览器打开后，可直接打印为 PDF
- 适配 A4 纸张

### 3. 查询职业列表

```bash
coc jobs
```

输出所有 112 个可用职业名称（JSON 数组）。

### 4. 查询职业详情

```bash
coc job "私家侦探"
```

输出该职业的点数公式、信用评级范围、本职技能列表：

```json
{
  "name": "私家侦探",
  "formula_text": "教育×2 + (力量×2 或 敏捷×2)",
  "credit_range": "9~30",
  "occupation_skills": ["乔装", "侦查", "取悦", "图书馆使用", ...],
  "skill_description": "技艺(摄影)，乔装，法律，图书馆使用，心理学，侦查，..."
}
```

---

## 校验规则（严格模式）

CLI 是唯一的规则 truth source，校验不通过即报错，不允许渲染 HTML。

| 校验项 | 规则 |
|--------|------|
| 属性总和 | 8项属性（STR/CON/DEX/APP/POW/SIZ/EDU/INT）必须严格等于 480 |
| 属性范围 | 每项属性必须在 20~80 之间 |
| 幸运 | 15~90，不包含在 480 内 |
| 职业点数 | 按职业公式计算（如 EDU×4、EDU×2+DEX×2 等），总和不得超过 |
| 兴趣点数 | INT × 2，总和不得超过 |
| 职业技能上限 | 最终值（初始值+职业点）≤ 80 |
| 兴趣技能上限 | 最终值（初始值+兴趣点）≤ 60 |
| 本职技能 | 职业点数**只能**投给该职业的本职技能 |
| 克苏鲁神话 | **禁止**分配任何点数 |
| 信用评级 | 必须在职业允许的范围内 |

---

## JSON 输入格式

大模型/Agent 生成的中间 JSON 格式：

```json
{
  "basic": {
    "name": "亚瑟·布莱克伍德",
    "player": "Alice",
    "job": "私家侦探",
    "age": 32,
    "gender": "男",
    "hometown": "波士顿",
    "era": "1920s"
  },
  "attributes": {
    "str": 50, "con": 50, "dex": 60, "app": 55,
    "pow": 50, "siz": 65, "edu": 70, "int": 80
  },
  "luck": 60,
  "credit_rating": 25,
  "skill_allocations": {
    "pro": {
      "侦查": 45,
      "图书馆使用": 30,
      "心理学": 25,
      "话术": 20,
      "法律": 20
    },
    "interest": {
      "潜行": 30,
      "聆听": 35,
      "锁匠": 25,
      "射击(手枪)": 20
    }
  },
  "background": {
    "appearance": "...",
    "belief": "...",
    "important_person": "...",
    "important_place": "...",
    "important_item": "...",
    "trait": "...",
    "scar": "...",
    "madness": "...",
    "description": "..."
  }
}
```

**大模型不需要计算**：技能初始值、职业点数上限、兴趣点数上限、HP/MP/SAN/DB/体格/MOV/闪避/母语。这些全部由 CLI 内部计算。

**大模型需要知道**：
- 8属性分 480，每项 20~80
- 幸运 3D6×5（15~90），不含在 480 内
- 职业技能最终值 ≤ 80，兴趣技能最终值 ≤ 60
- 职业点数只能投给**本职技能**
- 兴趣点数可以投给**任何技能**
- 信用评级在职业范围内
- 克苏鲁神话不能分配点数
- 推荐优先点：侦查、聆听、图书馆使用

---

## Agent Skill 建议流程

```
1. 引导用户确定角色概念
2. 调用 coc job <职业名> → 获取点数公式、本职技能、信用范围
3. 生成 JSON 草稿
4. 调用 coc verify → 获取校验报告
5. 如有 errors，向用户说明并修正（或自动修正）
6. 重复 4-5 直到 valid: true
7. 调用 coc render → 获取 HTML 路径
8. 告诉用户：浏览器打开打印即可
```

---

## 数据来源

- **职业/技能数据**：提取自 [trpg-saikou](https://github.com/masquevil/trpg-saikou)（侠小然）
- **规则计算**：参考 [cochar](https://github.com/ajwalkiewicz/cochar)（Adam Walkiewicz）

---

## 项目结构

```
coc_generator/
├── coc_generator/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py              # CLI 命令入口
│   ├── engine.py           # 规则引擎（校验+计算）
│   ├── renderer.py         # HTML 渲染
│   ├── schema.py           # 数据模型
│   └── data/
│       ├── skills.py       # 140 技能定义
│       ├── jobs.py         # 112 职业定义
│       └── templates/
│           └── card.html   # A4 角色卡模板
├── examples/
│   ├── valid_detective.json
│   ├── invalid_detective.json
│   └── detective_card.html
├── scripts/
│   └── extract_data.py     # 从 trpg-saikou 提取数据
├── README.md
└── pyproject.toml
```
