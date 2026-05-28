# 技术方案：生成式 HTML 角色档案卡

## 分支与工作目录

- 分支：`proposal/html-generated-card`
- 工作目录：`C:\Users\yangqi\code\coc\coc_generator-html-redesign`
- 目标：不再模拟可手写 PDF 表单，而是把 generator 的 HTML 设计成一张已经排版完成、适合浏览器查看和 A4 打印的双面角色档案卡。

## 设计目标

当前 HTML 的主要问题不是信息不全，而是视觉语言仍在模拟纸质空白表：大量横线、黑色标题条、密集表格和占位框会让生成内容显得像填进了旧表格。这个方案只追求最佳生成效果：让 HTML 成为最终成品，而不是 PDF 的替代空表。

最终效果应该是：

- 双面 A4，浏览器打开即可查看，打印时稳定分页。
- 正面是高密度但清爽的角色概览：人物、属性、状态、技能、武器与战斗。
- 背面是可阅读的背景档案：个人介绍、背景条目、物品、资产、联系人、经历。
- 所有生成出来的文本都进入完整框体或卡片，不再使用长横线承载内容。
- 整体风格保留 CoC 档案感，但不照搬目标 PDF 的繁体旧表单。

## 核心取舍

只做 HTML 原生重设计，不做 PDF 背景合成，不做逐字还原 PDF。

这个方向的优势是维护成本低、数据适配自然、长文本表现好。它应该把现有 generator 变成“生成式角色卡产品”，而不是“可编辑 PDF 的仿制品”。

## 视觉规范

建议采用克制的档案页风格：

- 页面背景：打印时纯白，屏幕预览时浅灰工作台。
- 卡面底色：接近纸张的 `#fbfaf6` 或纯白，避免大面积深色。
- 强调色：深墨色 + 暗红色少量使用，例如标题编号、危险/神话相关区域。
- 标题：取消每个 section 的黑底白字，改为轻量标题行、左侧细线或小型章标。
- 框线：使用 1px 浅灰线和少量深色分割线；不要过度斑马纹。
- 字体：中文优先使用系统黑体；主标题可使用宋体/衬线字体增强档案感。
- 打印：所有颜色在灰度打印下仍要可读，不能依赖低对比背景。

## 页面结构

### 正面

正面应保留 A4 单页，不滚动、不溢出：

1. 顶部身份区
   - 左侧：姓名、职业、玩家、时代、年龄、性别、住地、故乡。
   - 中间：8 项属性，以紧凑数据格展示。
   - 右侧：头像区域。无头像时显示简洁占位，不写“形象”两个字。

2. 状态与衍生属性区
   - SAN/HP/MP、DB、体格、MOV、闪避等统一成数字面板。
   - 身体状态、精神状态用小型 checkbox chip，而不是黑白表格。

3. 技能区
   - 仍然是正面的主区域。
   - 分组用左侧窄标签或小标题，不用竖排大边框。
   - 数字列固定宽度，基础/职业/兴趣/成长/成功率对齐。
   - 本职技能用小徽标或细色标记，不使用实心黑块。
   - 空值保持空白，减少视觉噪音。

4. 武器与战斗区
   - 武器表更像装备清单，最多显示 5 行。
   - 战斗数据放在右侧紧凑指标组。

### 背面

背面应从“手写页”改成“阅读页”：

1. 个人介绍
   - 独立的大文本框，允许多段文本。
   - 使用自然段排版，不加横线底纹。

2. 背景条目
   - 形象描述、思想与信念、重要之人、意义非凡之地、宝贵之物、特质、伤口与疤痕、精神症状。
   - 使用 2 列信息卡，每张卡固定标题 + 正文。

3. 物品、资产、神话、好友、经历
   - 物品用 tag/list 形式。
   - 资产用 label/value 小表格。
   - 克苏鲁神话保留警示风格，但不要大红整块。
   - 好友与经历使用正文框，不加横线。

## 技术实现

主要修改：

- `coc_generator/renderer.py`
  - 保持现有数据上下文结构。
  - 如需要，增加少量展示辅助字段，例如 `identity_fields`、`derived_panels`、`status_groups`、`item_tags`。
  - 不改变规则引擎和 JSON 输入协议。

- `coc_generator/data/templates/card.html`
  - 重写 CSS 和 HTML 结构。
  - 保留 `@page { size: A4; margin: 0; }`。
  - `.page` 继续固定 `210mm x 297mm`。
  - 使用 CSS Grid/Flex 做稳定版式。
  - 删除横线式 `.wr .val { border-bottom: ... }` 的主导设计，改成字段框。

建议新增模板结构：

- `.sheet`
- `.panel`
- `.panel-title`
- `.field-grid`
- `.field`
- `.value-box`
- `.stat-grid`
- `.skill-table`
- `.story-card`
- `.text-box`
- `.tag-list`

## 约束

- 不引入前端框架。
- 不引入外部字体 CDN，保证离线可打开。
- 不改变 CLI 命令格式。
- 不改变已有 JSON 示例的可渲染性。
- 允许修改示例 HTML 输出，但不要手写改 examples 作为真实源。

## 验收方式

### 功能验收

在该 worktree 中执行：

```powershell
python -m coc_generator.cli verify examples\valid_detective.json
python -m coc_generator.cli render examples\valid_detective.json -o examples\valid_detective_card.html
python -m coc_generator.cli render examples\doctor.json -o examples\doctor_card.html
python -m coc_generator.cli render examples\archaeologist.json -o examples\archaeologist_card.html
```

验收标准：

- 三个示例都能通过 verify/render。
- HTML 打开后有且只有两张 A4 页面。
- 浏览器打印预览中正反面分别占一页，没有第三页。
- 页面没有横向滚动，没有内容溢出 A4。

### 视觉验收

用 Playwright 截图检查：

- 正面截图：身份区、属性区、状态区、技能区、武器区清晰分层。
- 背面截图：个人介绍和背景条目是完整文本框/信息卡，不再是长横线。
- 黑底标题栏不再作为主要视觉语言。
- 技能表仍能快速扫读，分组、基础值、分配值、成功率不混乱。
- 长中文文本不会覆盖相邻模块；必要时截断或缩小字号，但不能溢出。

建议截图命令可由 agent 自行写 Playwright 脚本，输出到 `artifacts/html-redesign/`。

### 代码验收

- `git diff` 中主要变更集中在 `renderer.py` 和 `card.html`。
- 没有改动规则计算、职业数据、技能数据。
- 没有把生成后的 `examples/*_card.html` 当作唯一实现来源。
- 没有引入网络资源。

## 交付物

- 更新后的 `coc_generator/data/templates/card.html`。
- 如需要，更新后的 `coc_generator/renderer.py`。
- 至少 3 份重新生成的示例 HTML。
- Playwright 截图产物，证明正反两页效果。
- 简短说明：新设计解决了哪些旧 HTML 问题，仍有哪些已知限制。
