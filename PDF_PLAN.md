# PDF 打印方案分析

## trpg-saikou 的打印方案

**技术**：`html-to-image` 库把 Vue 组件渲染成 JPEG 图片
**输出**：两张图片（正面 + 背面），分辨率 `1680×2376px`（210mm×297mm × 8dpi）
**用户操作**：下载两张图 → 分别打印 → 手动双面

### 正反面布局

| 正面（PaperFront） | 背面（PaperBack） |
|-------------------|-------------------|
| 调查员信息 | 背景故事（形象/信念/重要之人/地点/物品/特质/疤痕/症状/介绍） |
| 8属性 + 幸运 | 物品栏 |
| 衍生属性（HP/MP/SAN/DB/体格/MOV/闪避） | 资产（现金/消费水平/资产） |
| 技能表 | 克苏鲁神话 |
| 武器 | 好友 |
| 战斗属性 | 经历模组 |
| 版权/提示 | 致谢/版权 |

**关键设计**：
- 使用 `em` 单位，基准 `3.2mm`，容器精确 `65.625em × 92.8125em` = `210mm × 297mm`
- 像素级精确控制排版，确保打印时内容不会溢出 A4

---

## 我们的现状

当前 CLI 输出的是**单页 HTML**，包含：
- 基本信息
- 属性 + 衍生属性
- 技能表（只显示有分配点数的 + 推荐技能）
- 背景故事

**缺少**：
- 武器栏
- 物品栏
- 资产栏
- 克苏鲁神话栏
- 好友/经历模组栏
- **背面页面**

---

## PDF 生成方案对比

### 方案 1：Playwright（无头 Chromium）⭐ 推荐

**原理**：用无头 Chrome 打开 HTML → 调用 CDP `Page.printToPDF()` → 输出 PDF

**优点**：
- 真实浏览器渲染，CSS 完美支持
- 精确控制 A4 尺寸、页边距、页眉页脚
- 可以生成多页 PDF（正面第1页，背面第2页）
- 和现有 HTML 模板完全复用

**缺点**：
- 需要安装浏览器（Playwright 自动下载 Chromium，约 100MB）
- 作为可选依赖，首次使用需要下载

**依赖**：
```bash
pip install playwright
playwright install chromium
```

**代码示例**：
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.set_content(html_content)
    page.pdf(path="card.pdf", format="A4", margin={"top": "10mm", "bottom": "10mm"})
```

---

### 方案 2：WeasyPrint（Python 原生）

**原理**：纯 Python 的 HTML→PDF 渲染引擎

**优点**：
- pip 直接安装，无需外部浏览器
- 支持 CSS `@page` 规则
- 可以控制页面尺寸和边距

**缺点**：
- **Windows 需要安装 GTK**（这是最大痛点）
- CSS flex/grid 支持有限，复杂布局可能崩
- 字体渲染不如真实浏览器

**依赖**：
```bash
# Windows 上需要先装 GTK
pip install weasyprint
```

---

### 方案 3：保留 HTML + 浏览器打印（现状）

**原理**：用户用浏览器打开 HTML → Ctrl+P → 另存为 PDF

**优点**：
- 零依赖
- 浏览器渲染效果最好
- 用户可以自己调打印设置

**缺点**：
- 不是 CLI 直接输出 PDF
- 双面打印需要手动操作（先打正面，再翻面打背面）
- 不同浏览器效果有差异

---

### 方案 4：ReportLab（纯 Python 手写排版）

**原理**：用 Python 代码逐元素绘制 PDF

**优点**：
- 零外部依赖
- 完全可控的像素级排版

**缺点**：
- 需要手写所有排版代码，无法复用 HTML 模板
- 开发成本高，维护困难
- 不支持 CSS，所有样式用 Python 代码描述

---

## 推荐实现路径

### Phase 1：双面 HTML（立即做）

先不引入 PDF 库，而是把 HTML 模板升级为**双面打印版**：

1. **正面**：现有的内容（信息/属性/衍生属性/技能表）
2. **背面**：新增背景故事/物品/资产/好友/经历模组等
3. 用 CSS `@media print` 控制分页：
   ```css
   @media print {
     .page-front { page-break-after: always; }
   }
   ```
4. 用户浏览器打开 HTML → 打印 → 选择"双面打印"（现代打印机支持）

**优点**：零依赖，立即可用

### Phase 2：Playwright PDF（后续加）

作为可选功能：

```bash
# 默认输出 HTML
coc render character.json -o card.html

# 安装可选依赖后输出 PDF
coc render character.json -o card.pdf
```

实现方式：
1. 先渲染双面 HTML（和 Phase 1 相同）
2. 如果输出路径是 `.pdf`，调用 Playwright 转换
3. 否则输出原始 HTML

---

## 需要新增的数据字段

为了支持完整的双面角色卡，JSON Schema 需要扩展：

```json
{
  "weapons": [
    {"name": "手枪", "skill": "射击(手枪)", "damage": "1D10", "range": "15m", "attacks": 1, "ammo": 8, "malf": 100}
  ],
  "items": ["手电筒", "笔记本", "香烟", "怀表"],
  "assets": {
    "cash": "$25",
    "consumption": "贫困",
    "assets": "$1500",
    "items": "一间狭小的公寓、一辆旧汽车"
  },
  "friends": "警局的旧同事汤姆、线人小混混杰米",
  "experienced_modules": "《敦威治的恐怖》"
}
```

---

## 结论

| 维度 | 最佳选择 |
|------|---------|
| 立即可用 | **双面 HTML**（零依赖，浏览器打印即可） |
| CLI 直接出 PDF | **Playwright**（真实浏览器渲染，效果最可靠） |
| 跨平台无依赖 | 没有完美方案，Playwright 需要下载浏览器 |
| 排版精确度 | Playwright > 浏览器打印 > WeasyPrint |

**建议**：
1. 先升级 HTML 模板为**双面版**（正面+背面），支持浏览器直接双面打印
2. 后续版本增加 `--pdf` 选项，用 Playwright 生成 PDF
3. 不要选 WeasyPrint，Windows GTK 安装是噩梦
