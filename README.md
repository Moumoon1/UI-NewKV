# kv2ui1 · KV 活动页 UI 换肤

根据新 KV 为现有 Figma 活动页提出配色方案，在用户选定后保留业务结构、文案、字体和受保护素材，完成副本换肤与视觉验收。

## 使用准备

1. 将整个 `kv2ui1` 文件夹安装到支持 `SKILL.md` 的助手的 skills 目录，保留目录结构。
2. 连接自己的 Figma 账号与官方 Figma 插件。环境需要提供 `use_figma`、截图能力及 `figma:figma-use` 技能；本文件夹不包含账号、密钥或授权。
3. 本地脚本使用 Python 3.10 或以上版本。进入本文件夹后，在自己的 Python 环境中运行 `python3 -m pip install -r requirements.txt`。多数审计脚本只依赖标准库；Pillow 用于图片分析和配色预览。
4. 快照传输助手使用 POSIX 终端，适用于 macOS/Linux；Windows 请使用 WSL。Figma JavaScript 片段在插件工具环境运行，不是独立网页程序。

## 调用示例

```text
使用 $kv2ui1，根据我提供的新 KV 给这个 Figma 活动页提出配色方案。
我选定后，在保留原稿和业务结构的副本上完成换肤。
原页面：<填写你自己的 Figma 页面或画框链接>
新 KV：<填写你自己的素材或 Figma 节点链接>
```

所有文件路径、Figma 文件和节点 ID 均在每次任务中从用户输入及实时读取获取。命令示例中的 `scripts/` 相对于本文件夹；运行产物写入系统临时目录，完成后按 `SKILL.md` 清理。

## 文件说明

- `SKILL.md`：入口、边界与工作流程。
- `agents/`：技能显示名称和调用配置。
- `references/`：按阶段读取的配色及验收规则。
- `scripts/`：通用采集、预演、写入和审计工具。
- `scripts/vendor/pako/`：随附压缩依赖及其许可证，分享时一并保留。

分享包仅包含通用规则和工具，不附带历史任务、截图、生成结果或开发仓库信息。
