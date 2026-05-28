# COC 7版 480购点角色卡生成器 — 技术方案 v2

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent（大模型侧）                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │ 聊天引导     │ → │ 查询职业规则 │ → │ 生成JSON草稿 │      │
│  └─────────────┘    └─────────────┘    └─────────────┘      │
│                                               │             │
│  ┌─────────────┐    ┌─────────────┐          │             │
│  │ 解释/修正   │ ←  │ 解析校验报告 │ ← ──────┘             │
│  └─────────────┘    └─────────────┘                        │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      CLI（Python）                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │  jobs/job   │    │   verify    │    │   render    │      │
│  │  查询规则   │ →  │  严格校验   │ →  │  生成HTML   │      │
│  └─────────────┘    └─────────────┘    └─────────────┘      │
│                           ↑                                │
│                      ┌─────────────┐                        │
│                      │  规则引擎   │                        │
│                      │ 计算+校验   │                        │
│                      └─────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

**核心原则**：
- **CLI 是唯一的规则 truth source**。所有数值计算、合法性校验、边界检查都在 CLI 内完成。
- **大模型可以自由生成 JSON**，不需要在生成时严格遵守规则。它甚至可以完全不懂 COC 规则，只凭用户描述输出分配方案。
- **CLI 严格 enforcement**。校验不通过就是 error，不是 warning。大模型必须根据反馈修正后才能进入 render。
- **查询接口降低迭代成本**。大模型可以在生成前先调用 `coc job` 查规则，让初稿尽量合法，减少 verify → 修正的轮数。

---

## 2. 大模型 ↔ CLI 边界

### 2.1 大模型生成的 JSON（输入）

大模型只输出**分配方案**和**叙事内容**，不计算任何上限或衍生值：

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
      "聆听": 35,
      "图书馆使用": 30,
      "心理学": 25,
      "话术": 20
    },
    "interest": {
      "潜行": 30,
      "锁匠": 25,
      "射击(手枪)": 20
    }
  },
  "background": {
    "appearance": "总是穿着皱巴巴的灰色风衣...",
    "belief": "真相值得一切代价",
    "important_person": "已故的搭档马库斯",
    "important_place": "老城区的地下酒吧",
    "important_item": "马库斯留下的怀表",
    "trait": "强迫症般地整理线索",
    "scar": "左肩枪伤",
    "madness": "",
    "description": ""
  }
}
```

**大模型需要知道的事情（Prompt里要教）**：
- 8项属性（不含幸运）总和必须严格等于 480
- 每项属性范围 20~80
- 幸运单独掷，15~90，不包含在480内
- 职业技能最终值（初始值+职业点）不能超过 80
- 兴趣技能最终值（初始值+兴趣点）不能超过 60
- 职业点数只能投给该职业的**本职技能**
- 兴趣点数可以投给**任何技能**
- 信用评级必须在职业允许的范围内
- 推荐优先点：侦查、聆听、图书馆使用

**大模型不需要知道的事情（CLI内部计算）**：
- 技能初始值是多少
- 这个职业的本职技能具体有哪些（但可以通过 `coc job` 查询）
- 职业点数上限 = 多少
- 兴趣点数上限 = INT × 2
- HP/MP/SAN/DB/体格/移动力/闪避 怎么算
- 母语 = EDU，闪避 = DEX/2

### 2.2 CLI 校验后输出的 JSON（反馈给大模型）

```json
{
  "valid": false,
  "errors": [
    {
      "code": "ATTR_SUM_MISMATCH",
      "field": "attributes.sum",
      "expected": 480,
      "actual": 470,
      "message": "8项属性总和为470，不等于480"
    },
    {
      "code": "ATTR_OUT_OF_RANGE",
      "field": "attributes.edu",
      "expected": "20~80",
      "actual": 85,
      "message": "属性【教育(EDU)】为85，超出范围20~80"
    },
    {
      "code": "PRO_SKILL_NOT_OCCUPATION",
      "field": "skill_allocations.pro.锁匠",
      "expected": ["侦查", "聆听", "图书馆使用", "心理学", "话术", "乔装", "法律", "摄影", "任意其他1项"],
      "actual": "锁匠",
      "message": "【锁匠】不是【私家侦探】的本职技能，职业点数不能投给该技能"
    },
    {
      "code": "PRO_SKILL_CAP_EXCEEDED",
      "field": "skill_allocations.pro.侦查",
      "expected": "<=80",
      "actual": 85,
      "message": "职业技能【侦查】最终值85，超过上限80（初始25+职业点60）"
    },
    {
      "code": "INTEREST_SKILL_CAP_EXCEEDED",
      "field": "skill_allocations.interest.潜行",
      "expected": "<=60",
      "actual": 65,
      "message": "兴趣技能【潜行】最终值65，超过上限60（初始20+兴趣点45）"
    },
    {
      "code": "PRO_POINTS_OVERFLOW",
      "field": "skill_allocations.pro.sum",
      "expected": "<=280",
      "actual": 320,
      "message": "职业点数总和320，超过上限280（EDU70×4）"
    },
    {
      "code": "INTEREST_POINTS_OVERFLOW",
      "field": "skill_allocations.interest.sum",
      "expected": "<=160",
      "actual": 180,
      "message": "兴趣点数总和180，超过上限160（INT80×2）"
    },
    {
      "code": "CREDIT_RATING_OUT_OF_RANGE",
      "field": "credit_rating",
      "expected": "9~30",
      "actual": 35,
      "message": "信用评级35超出职业【私家侦探】允许范围9~30"
    }
  ],
  "derived": {
    "hp": 11,
    "mp": 10,
    "san": 50,
    "db": "0",
    "build": "0",
    "mov": 8,
    "dodge": 30,
    "native_language": 70,
    "pro_points_total": 280,
    "pro_points_used": 155,
    "pro_points_remaining": 125,
    "interest_points_total": 160,
    "interest_points_used": 75,
    "interest_points_remaining": 85
  }
}
```

大模型收到反馈后，逐条修正 JSON，再次调用 `coc verify`，循环直到 `valid: true`。

---

## 3. CLI 内部结构

### 3.1 数据层（从 trpg-saikou 提取）

```
coc_generator/data/
├── jobs.py          # 80+ 职业定义（已解析为标准格式）
├── skills.py        # 技能定义（名称、初始值、分组、别名）
└── templates/
    └── card.html    # Jinja2 HTML模板
```

**职业定义结构**（从 `trpg-saikou` 的复杂格式解析后）：

```python
@dataclass
class Job:
    name: str                              # "私家侦探"
    point_formula: list[list[tuple]]       # 每组内部取max，各组结果相加
    credit_range: tuple[int, int]          # (9, 30)
    # 本职技能池：所有允许投入职业点数的技能名
    # 包含固定技能、多选一展开后的所有选项、分组技能展开后的所有子技能
    occupation_skills: list[str]
    # 原始描述（供查询接口展示）
    skill_description: str
```

**本职技能解析规则**（从 `trpg-saikou` 的 `JobSkills` 格式转换）：

| 原始格式 | 解析后 |
|---------|--------|
| `'侦查'` | 直接加入允许池 |
| `['取悦', '话术', '恐吓', '说服']` | 数组内所有技能都加入允许池（不限制选几个，只限制选什么） |
| `['取悦', '话术', '恐吓', '说服']` 出现 N 次 | 同上，所有技能都加入允许池 |
| `{ 格斗: '斗殴' }` | `"格斗(斗殴)"` 加入允许池 |
| `{ 格斗: '' }` | 格斗分组下所有子技能加入允许池 |
| `{ 技艺: '' }` | 技艺分组下所有子技能加入允许池 |
| `{ 外语: '拉丁语' }` | `"外语(拉丁语)"` 加入允许池 |
| `{ 外语: '' }` | 外语分组下所有子技能加入允许池 |
| `{ 科学: '' }` | 科学分组下所有子技能加入允许池 |
| `{ 母语: '' }` | `"母语"` 加入允许池（母语只有一种） |

**技能定义结构**：

```python
@dataclass
class Skill:
    name: str                    # "侦查"
    init: int                    # 25
    group: Optional[str]         # None 或 "格斗"/"射击"/"科学"/"技艺"/"外语"/"母语"
    aliases: list[str]           # 英文别名或常用简称
```

### 3.2 规则引擎

#### 3.2.1 属性校验

```python
def validate_attributes(attrs: dict) -> list[Error]:
    errors = []
    total = sum(attrs.values())
    if total != 480:
        errors.append(Error("ATTR_SUM_MISMATCH", f"属性总和{total}，必须等于480"))
    for key, val in attrs.items():
        if not 20 <= val <= 80:
            errors.append(Error("ATTR_OUT_OF_RANGE", f"{key}={val}，必须在20~80之间"))
    return errors
```

#### 3.2.2 衍生属性计算（COC 7版标准规则）

| 属性 | 公式 |
|------|------|
| HP | `floor((CON + SIZ) / 10)` |
| MP | `floor(POW / 5)` |
| SAN | `POW` |
| 闪避 | `floor(DEX / 2)` |
| 母语 | `EDU` |
| DB/体格 | STR+SIZ 查表 |
| MOV | STR/DEX/SIZ 关系 + 年龄修正 |

**DB/体格查表**：

| STR+SIZ | DB | 体格 |
|---------|----|------|
| 2~64 | -2 | -2 |
| 65~84 | -1 | -1 |
| 85~124 | 0 | 0 |
| 125~164 | +1D4 | +1 |
| 165~204 | +1D6 | +2 |
| 205~284 | +2D6 | +3 |
| 285~364 | +3D6 | +4 |
| 365~444 | +4D6 | +5 |
| 445~524 | +5D6 | +6 |
| 525+ | 每多80，+1D6 / +1 | |

**MOV计算**：
- 基础：STR<SIZ 且 DEX<SIZ → 7；STR>SIZ 且 DEX>SIZ → 9；其他 → 8
- 年龄修正：40~49减1，50~59减2，60~69减3，70~79减4，80+减5

#### 3.2.3 点数计算

```python
def calc_pro_points(job: Job, attrs: dict) -> int:
    """
    职业点数 = sum(max(每个公式组内的候选项))
    例如 [[('edu',4)]] → edu*4
    例如 [[('edu',2)], [('str',2),('dex',2)]] → edu*2 + max(str*2, dex*2)
    """
    ...

def calc_interest_points(attrs: dict) -> int:
    return attrs['int'] * 2
```

#### 3.2.4 技能校验（严格模式）

```python
def validate_skills(job: Job, skills_data: dict, allocations: dict) -> list[Error]:
    errors = []
    
    # 1. 校验职业点数总量
    pro_total = calc_pro_points(job, attrs)
    pro_used = sum(allocations['pro'].values())
    if pro_used > pro_total:
        errors.append(Error("PRO_POINTS_OVERFLOW", ...))
    
    # 2. 校验兴趣点数总量
    interest_total = calc_interest_points(attrs)
    interest_used = sum(allocations['interest'].values())
    if interest_used > interest_total:
        errors.append(Error("INTEREST_POINTS_OVERFLOW", ...))
    
    # 3. 校验每个职业技能
    for skill_name, points in allocations['pro'].items():
        # 3a. 是否为本职技能
        if skill_name not in job.occupation_skills:
            errors.append(Error("PRO_SKILL_NOT_OCCUPATION", ...))
            continue
        
        # 3b. 是否超过80上限
        init = skills_data[skill_name].init
        if init + points > 80:
            errors.append(Error("PRO_SKILL_CAP_EXCEEDED", ...))
    
    # 4. 校验每个兴趣技能
    for skill_name, points in allocations['interest'].items():
        init = skills_data[skill_name].init
        if init + points > 60:
            errors.append(Error("INTEREST_SKILL_CAP_EXCEEDED", ...))
    
    return errors
```

#### 3.2.5 信用评级校验

```python
def validate_credit_rating(job: Job, credit: int) -> list[Error]:
    if not job.credit_range[0] <= credit <= job.credit_range[1]:
        return [Error("CREDIT_RATING_OUT_OF_RANGE", ...)]
    return []
```

信用评级是独立输入字段，但规则上仍视为技能点投入：`credit_rating` 必须计入职业点数使用量，并在技能表中显示为“信用评级”的职业点/成功率。

### 3.3 CLI 命令

```bash
# 查看所有职业列表
python -m coc jobs

# 查看某个职业的详细规则（供大模型生成前查询）
python -m coc job "私家侦探"
# 输出：
# {
#   "name": "私家侦探",
#   "point_formula": "教育×2 + 力量或敏捷×2",
#   "credit_rating": "9~30",
#   "occupation_skills": ["侦查", "聆听", "图书馆使用", ...],
#   "description": "本职技能：..."
# }

# 严格校验 JSON，输出校验报告（JSON格式，方便大模型解析）
python -m coc verify character.json

# 校验通过后渲染 HTML 角色卡
python -m coc render character.json -o card.html
```

### 3.4 HTML 模板设计

**单页 A4 打印适配**：
- CSS `@media print` 优化，去掉页眉页脚
- 适配 A4 纵向（210mm × 297mm）
- 布局参考传统 COC 7版角色卡：
  - 顶部：基本信息（姓名、玩家、职业、年龄、性别、家乡、时代）
  - 左上：8项属性 + 幸运
  - 右上：衍生属性（HP/MP/SAN/MOV/DB/体格/闪避/母语）
  - 中部：技能表（按分组排列，显示 初始值/职业点/兴趣点/最终值）
  - 底部：背景故事（如果有）
  - 底部右侧：资产/物品（留空或从 JSON 读取）

**技能表显示格式**：

| 技能名 | 初始 | 职业点 | 兴趣点 | 最终值 |
|--------|------|--------|--------|--------|
| 侦查 | 25 | +45 | 0 | 70 |
| 聆听 | 20 | +35 | 0 | 55 |
| 潜行 | 20 | 0 | +30 | 50 |

---

## 4. Agent Skill 侧的设计建议

大模型侧的 Skill 推荐流程：

```
1. 引导用户确定角色概念（职业、背景、玩法倾向）
2. 调用 coc job <职业名> → 获取点数公式、本职技能列表、信用范围
3. 向用户展示参考信息，确认属性分配策略
4. 生成 JSON 草稿
5. 调用 coc verify → 获取校验报告
6. 如果有 errors，向用户说明问题并修正（或自动修正）
7. 重复 5-6 直到 valid: true
8. 调用 coc render → 获取 HTML 路径
9. 告诉用户："角色卡已生成：card.html，浏览器打开后打印即可"
```

**Skill Prompt 里需要硬编码的规则摘要**（给大模型参考，但不强制它遵守）：
- 8属性分480，每项20~80
- 幸运 3D6×5（15~90），不包含在480内
- 职业技能最终值 ≤ 80
- 兴趣技能最终值 ≤ 60
- 职业点数只能投给**本职技能**
- 兴趣点数可以投给**任何技能**
- 信用评级必须在职业允许范围内
- 推荐优先点：侦查、聆听、图书馆使用

---

## 5. 技术栈

- **Python 3.10+**
- 依赖：
  - `jinja2`（HTML模板渲染）
- 无其他外部依赖

---

## 6. 开发优先级

| 优先级 | 内容 |
|--------|------|
| P0 | 提取职业/技能数据、解析本职技能池 |
| P0 | JSON Schema、verify 命令、严格校验逻辑 |
| P0 | 属性校验（480/20-80）、衍生属性计算 |
| P0 | 点数计算（职业点/兴趣点）、技能上限校验（80/60） |
| P0 | 本职技能 enforcement、信用评级校验 |
| P1 | jobs / job 查询命令 |
| P1 | render 命令 + HTML模板（A4打印） |
| P1 | 示例 JSON + 端到端测试 |
| P2 | 武器/装备支持 |
| P2 | 年龄修正对属性的影响（可选，购点制通常不做年龄修正） |

---

## 7. 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 校验严格度 | **严格 enforcement** | 职业点数只能投给本职技能，超上限即报错，不通过不渲染 |
| 大模型生成自由度 | **完全自由** | 大模型可以任意生成，CLI 后验校验。查询接口帮助减少迭代 |
| 年龄修正 | **不做** | 购点制通常不做掷骰后的年龄修正，属性值就是最终值 |
| 多选一限制 | **只限制技能名，不限制数量** | `['取悦','话术','恐吓','说服']` 出现2次理论上是"选两个"，MVP简化为：只要在这个数组里的技能都允许投职业点 |
| HTML输出 | **单页 A4 HTML** | 浏览器打开 → 打印 → 另存为PDF，最通用 |
| 自定义技能 | **允许** | 如果 JSON 里出现了 data/skills.py 里没有的技能名，初始值默认为 0，允许投入兴趣点；投入职业点则需要在本职技能池中 |
