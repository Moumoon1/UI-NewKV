# 配色方案提案与用户确认

Phase 2 完成 KV 取色后、Phase 3 冻结 Paint Recipe 前执行。本文只负责把新 KV 的颜色证据组织成可选择的整套 UI 配色；原稿灰度关系、结构保护和最终真实渲染验收仍由对应规则负责。

## 1. 分开判断三个对象

必须分别记录，不能用其中一个替代另一个：

- `sourceKvTone=light|dark|mixed`：旧 KV 的稳定环境明暗，仅用于理解迁移关系和接缝，不作为新色板来源。
- `sourceUiMode=light|dark|mixed`：原 UI 页面、卡片和容器最终合成后的整体深浅。半透明卡按与背景合成后的实际外观判断，不能因 Paint Alpha 低就自动归为浅色或深色。
- `targetKvTone=light|dark|mixed`：新 KV 的稳定环境明暗，排除标题、高光、主体局部发光和边缘遮罩后判断。

原 UI 的灰度与业务语义继续决定层级骨架；新 KV 决定新色板的颜色来源。深色 KV 可以搭配浅色 UI 或深色 UI，不能从 KV 深浅直接推导唯一 UI 模式。

## 2. 先从新 KV 提炼来源色

从 `colorAnchors` 中整理 3–5 个真正会参与搭配的来源色；简单 KV 可以少于 3 个，不能为凑数加入偶然反光：

1. 稳定环境色：负责页面、卡片和容器的整体色相与冷暖。
2. 环境深浅端或相邻环境色：负责表面层级、边界和已有氛围。
3. 主体稳定本色或材质中间色：负责同色系方案中的交互、Icon 和强调候选。
4. 稳定辅助色：只在画面中有足够面积或重复证据时进入候选。
5. 受光色或带倾向中性色：负责文字、高光和浅表面方向，不把镜面最亮点直接当主体基底。

另确定 `kvPrimaryHue`：新 KV 中最能代表主视觉的非中性色相，通常来自主体稳定本色、主要材质或反复出现的主题级颜色，不机械等于像素占比最大的环境色。保存来源区域、原始 RGB、色相口径和可信度。若 KV 没有任何可靠的非中性主色相，不能用固定蓝色、红色或旧 UI 色伪造补色，也不能少给一套方案冒充完成；在只读阶段说明缺少撞色基准，请用户指定基准色后再生成完整方案矩阵。

来源色只是依据，不是直接复制到 UI 的 Token。允许在保持色相家族、冷暖与角色来源的前提下，为大面积、交互和文字分别派生合适的明度和彩度。

## 3. 固定的方案矩阵

默认按新 KV 明暗决定提案数量：

| 情况 | 默认提案 |
|---|---|
| 深色 KV＋浅色 UI，换新的深色 KV | 深色同色系、浅色同色系、深色撞色、浅色撞色，共 4 套 |
| 深色 KV＋深色 UI，换新的浅色 KV | 浅色同色系、浅色撞色，共 2 套 |
| 浅色 KV 换新的深色 KV | 深色同色系、浅色同色系、深色撞色、浅色撞色，共 4 套 |
| 浅色 KV 换新的浅色 KV | 浅色同色系、浅色撞色，共 2 套 |

因此，未另行限定时：

- `targetKvTone=dark`：输出 4 套，覆盖 `targetUiMode=dark|light` × `hueStrategy=analogous|complementary`。
- `targetKvTone=light`：输出 2 套，固定 `targetUiMode=light`，覆盖 `analogous|complementary`。
- `targetKvTone=mixed` 且证据不足以归入深/浅：输出 4 套以保留深浅选择，并明确不确定来源。

用户在当前请求中明确限制“只看浅色 UI”“只看深色 UI”或只看一种色相关系时，删除不符合要求的方案，不拿无关方案让用户再次选择；否则按上表完整输出。

## 4. 两种色相关系怎样搭配

### 同色系 `analogous`

- 页面、卡片和内部容器从稳定环境色及其深浅/邻近色派生。
- 按钮、CTA、选中态、功能 Icon 和高亮字从 KV 主体稳定本色、材质中间色或同一主家族的邻近色派生。
- 同色系不等于所有角色同 Hex。用明度、彩度、已有材质和面积建立层级，CTA 与小按钮从共同交互主体配方派生。

### 撞色 `complementary`

- 页面、卡片和内部容器仍从新 KV 的稳定环境色派生。
- 按钮、CTA 与突出的高亮字，以 `kvPrimaryHue` 在色相环上的对立色 `Hc=(H+180°) mod 360°` 作为强调家族起点。
- 可为真实背景、材质和可读性调整对立色的感知明度与彩度；渐变暗部、受光面和高光围绕同一交互家族派生。若精确对立色产生明显脏色或视觉振动，可在保持“对立色家族”身份的前提下做小幅 Hue 校正，并在方案中同时展示原始对立色与最终候选，不能静默改成任意辅助色。
- 撞色集中用于按钮和关键强调，不能把背景、卡片和多个大面积模块分别铺成不同色相。Tab 选中态和功能 Icon 根据状态清晰度、面积与材质决定使用对立色家族还是协调的环境/材质色，不因都可点击而强制撞色。普通文字仍按真实表面选合适的带倾向中性色。
- 该撞色方向是用户明确要求的候选类型，不再要求 KV 本身先出现风格化撞色；是否最终采用由用户选择和真实试色共同决定。

## 5. 每套方案的交付格式

每套方案使用稳定 ID，例如 `D-A`（深色同色系）、`L-A`（浅色同色系）、`D-C`（深色撞色）、`L-C`（浅色撞色），并同时给出：

```text
targetUiMode / targetSurfaceDepth / hueStrategy
来源锚点与派生关系
page / card / container / border
textPrimary / textSecondary
titleAccent / dataAccent
tabSelected / tabDefault
iconGraphic / iconContainer
smallButton / CTA / buttonText
色板 Hex（用于沟通的代表值，不冒充所有渐变色标）
方案优势、风险和适合的视觉方向
```

用相同角色顺序并排展示方案，并用 `scripts/render_palette_proposals.py` 生成只读角色预览板；色块按页面、卡片、交互的近似面积级别表达，不能只给几个等大色块让小面积强调色看起来虚假占优。预览输入中的 `colors` 使用本节列出的 15 个代表角色，输出图片和输入哈希清单一起保存。提案阶段不复制页面、不替换 KV、不写 Figma UI，也不把预览板当成真实材质试色通过。

```sh
python3 scripts/render_palette_proposals.py palette-proposal.json palette-proposal.png
```

## 6. 用户确认是写入前门禁

将全部方案写入 `themeDecision.paletteProposal`，状态设为 `awaiting-user-palette-choice`，向用户展示方案 ID、代表色和角色关系，并可给出一条有依据的设计建议，但不得代替用户选择。

用户明确选择方案 ID 或清楚指定其中的 UI 深浅＋色相关系后，记录：

```text
themeDecision.paletteSelection.status = selected
themeDecision.paletteSelection.schemeId
themeDecision.paletteSelection.selectedAt
themeDecision.paletteSelection.userInstruction
```

选择前禁止进入 Phase 3 的最终配方冻结、Phase 4 复制/KV 替换和任何 UI 写色。选择后由该方案展开完整 Paint Recipe，再执行预检、代表试色、全页扩展和验收；后续合法的材质微调不重复请求配色选择。用户改变方案时使旧配方、试色门禁及其下游证据失效，但继续使用同一原稿审计；尚未创建副本时不要提前创建。
