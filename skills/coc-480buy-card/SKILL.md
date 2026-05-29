---
name: coc-480buy-card
description: 生成《克苏鲁的呼唤》7 版中文调查员角色卡，使用 480 购点制，并输出合法 JSON 或可打印 HTML。用户提到 COC/CoC/克苏鲁的呼唤/跑团/调查员/车卡/角色卡/480buy/480购点/7版/可打印 HTML 时应使用本 skill。角色卡模板、职业名、技能名和校验信息都以中文为主，因此不要自行翻译成英文职业或英文技能名；必须通过 GitHub 上的 coc-cardwright Python CLI 校验，不要手算后直接给结论。
---

# COC 480 购点角色卡

本 skill 是一个轻量操作指南：它不内置 Python 源码，而是指导 code agent 从 GitHub 获取并调用 `coc-cardwright` Python CLI。模型可以负责创意、人物设定和背景文本，但点数预算、本职技能、上限、衍生值和渲染必须交给 CLI 校验。

## 引擎仓库

先读取本目录的 `ENGINE_REPO.txt` 获取 Python CLI 仓库地址。默认是：

```text
https://github.com/tanis90/coc-cardwright.git
```

如果 `ENGINE_REPO.txt` 不存在或仓库地址不可用，向用户确认仓库地址；不要猜一个新的 GitHub URL。

## 安装或复用 CLI

优先复用当前工作区已有的 `coc-cardwright` / `coc_generator` 项目。如果没有，就从 `ENGINE_REPO.txt` 指向的仓库 clone。

推荐放在当前工作区的工具目录，例如：

```bash
git clone <ENGINE_REPO> .coc-cardwright
python -m pip install -e .coc-cardwright
```

如果用户不希望全局安装，创建项目内虚拟环境再安装：

```bash
python -m venv .coc-cardwright-venv
.coc-cardwright-venv/Scripts/python -m pip install -e .coc-cardwright
```

Windows 也可以使用：

```bash
py -3 -m pip install -e .coc-cardwright
```

安装后优先调用 `coc` 命令；如果 PATH 没刷新或找不到 `coc`，进入仓库后用 Python 模块方式调用：

```bash
python -m coc_generator --help
```

## CLI 能做什么

CLI 是本 skill 的规则入口。它能做四类事情：

- `jobs`：列出所有可用中文职业名，返回 JSON 数组。
- `job "<职业名>"`：查看某个职业的职业点公式、信用评级范围、本职技能和技能说明。
- `verify <json>`：校验角色 JSON，返回 `valid/errors/warnings/derived`。这是生成角色卡前必须通过的步骤。
- `render <json> -o <html>`：在 JSON 校验通过后渲染双面 A4 可打印 HTML 角色卡。

不确定命令或参数时，先调用 CLI 自带 help，而不是猜参数：

```bash
coc --help
coc verify --help
coc render --help
coc job --help
```

如果 `coc` 不可用，就在 Python 仓库目录下调用：

```bash
python -m coc_generator --help
python -m coc_generator verify --help
python -m coc_generator render --help
python -m coc_generator job --help
```

常用例子：

```bash
coc jobs
coc job "私家侦探"
coc verify character.json
coc render character.json -o character_card.html
```

## 工作流程

1. 收集或合理补全调查员概念：姓名、时代、职业、年龄、性格、背景和玩法定位。
2. 安装或定位 `coc-cardwright` CLI，然后先跑 `coc --help` 确认命令可用。
3. 选择职业时运行 `coc jobs`；分配职业点前运行 `coc job "<职业名>"` 查询职业公式、信用评级范围和本职技能。
4. 按下方结构起草 JSON 角色文件。职业名和技能名必须使用 CLI 返回的中文名称，避免英文名或自造译名。
5. 运行 `coc verify <json>`。如果 `valid` 不是 `true`，根据错误信息修改 JSON 后再次校验。
6. 只有校验通过后才运行 `coc render <json> -o <html>`，生成双面 A4 可打印 HTML。
7. 回复用户时给出 JSON 路径、HTML 路径，以及简短的人物概述和点数使用情况。

## 规则提醒

- 八项属性总和必须严格等于 480。
- 每项属性必须是 20 到 80 之间的整数。
- 幸运不计入 480 购点，范围为 15 到 90。
- 职业点只能投入该职业的本职技能，并且信用评级也计入职业点消耗。
- 兴趣点可以投入任意技能，但不能投入克苏鲁神话。
- 职业技能最终值不能超过 80。
- 兴趣技能最终值不能超过 60。
- 信用评级必须落在职业允许范围内。
- 克苏鲁神话不能通过正常分配点数提升。

这些提醒只是辅助记忆；最终规则以 `coc verify` 的结果为准。

## JSON 结构

使用下面结构作为文件契约：

```json
{
  "basic": {
    "name": "角色姓名",
    "player": "玩家名",
    "job": "职业名",
    "age": 32,
    "gender": "男",
    "hometown": "故乡",
    "era": "1920s"
  },
  "attributes": {
    "str": 50,
    "con": 50,
    "dex": 60,
    "app": 55,
    "pow": 50,
    "siz": 65,
    "edu": 70,
    "int": 80
  },
  "luck": 60,
  "credit_rating": 25,
  "skill_allocations": {
    "pro": {},
    "interest": {}
  },
  "weapons": [],
  "items": [],
  "assets": {
    "cash": "",
    "consumption": "",
    "assets": "",
    "items": ""
  },
  "mythos": 0,
  "friends": "",
  "experienced_modules": "",
  "background": {
    "appearance": "",
    "belief": "",
    "important_person": "",
    "important_place": "",
    "important_item": "",
    "trait": "",
    "scar": "",
    "madness": "",
    "description": ""
  }
}
```

## 输出要求

用户要求生成角色卡时，默认在当前工作区创建文件；如果用户指定目录，则写入指定目录。文件名应清晰可读，例如 `investigator.json` 和 `investigator_card.html`。

如果用户只要角色数据，生成并校验 JSON 后即可停止；如果用户要求可打印角色卡，还要渲染 HTML。
