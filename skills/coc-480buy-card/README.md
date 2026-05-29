# COC 480 购点角色卡 Skill

这是一个轻量 Codex skill。它不会内置 Python 源码，而是指导 code agent 使用本仓库的 `coc-cardwright` Python CLI 生成中文 CoC 7 版 480 购点角色卡。

## 安装

使用支持 GitHub 路径的 skills installer 安装本目录：

```bash
npx skills install https://github.com/tanis90/coc-cardwright/tree/main/skills/coc-480buy-card
```

如果你的 installer 使用 repo/path 参数形式，等价路径是：

```bash
npx skills install --repo tanis90/coc-cardwright --path skills/coc-480buy-card
```

安装后重启 Codex，让 skill 生效。

## 使用

安装后可以直接让 Codex 生成角色卡，例如：

```text
帮我生成一张民国上海记者的 COC 7版 480buy 角色卡，并输出可打印 HTML。
```

skill 会指导 agent 复用或安装 Python CLI，并调用：

```bash
coc --help
coc jobs
coc job "私家侦探"
coc verify character.json
coc render character.json -o character_card.html
```
