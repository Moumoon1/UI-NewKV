# 配色方案提案与用户确认

Phase 2 完成 KV 取色后、Phase 3 冻结 Paint Recipe 前执行。生成任何方案 Hex 前，先继承《颜色决策规则》第 1 节在 Phase 1 建立的原稿显著性证据，再按第 3.0–4 节完成表面家族、目标明度拓扑、彩度与受光感的初始选色门禁。本文负责把新 KV 的颜色证据组织成可选择的整套 UI 配色；原稿灰度关系、结构保护和最终真实渲染验收仍由对应规则负责。

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

另确定 `kvPrimaryHue`：新 KV 中最能代表主视觉的非中性色相，通常来自主体稳定本色、主要材质或反复出现的主题级颜色，不机械等于像素占比最大的环境色。再从 `surfaceFamilyId` 的稳定环境中确定 `surfaceContrastBasis`，作为无金属场景优先生成约 180° 对向候选的基准；同时登记 KV 中有可追溯面积或重复证据的高彩高明度交互候选；同时检查主体或标题是否存在明确、显著的金属视觉，若成立则登记 `metalAccentEvidence`：来源区域、金属家族判断、稳定本色/中间调/暗部/镜面高光样本、面积或重复证据及可信度。`metalAccentEvidence` 必须来自画面表现，不能由“金色标题”“银色主题”等文案或材质名称推断。

可靠金属证据会切换候选矩阵，不再把“金属色”统称为撞色。每个适用 UI 模式固定生成三个按钮方向：`metallic-analogous`（跟随本次金属家族的同色系金属色）、`gold-bright`（正常明亮金色）、`clean-deep`（有来源的干净深色）。金色是用户明确要求的通用金属对照候选，不要求 KV 本身已经是金色，但必须保持正常金色的明亮、鲜明和受光感。优先从类似 `#FFEED7→#FFC58A`、`#FFEEC6→#F9DB92`、`#FFE5A3→#FFC165` 的暖亮金范围建立方向，再根据 KV 光照与真实宿主微调；这些是范围标尺而非每次照抄的固定值。暗铜、棕橙、土黄或低明度黄褐不能代替，且默认使用深棕按钮字，不为迁就白字把金色整体压暗。深色方向单独成案，不能把金色方案压暗后充当深色，也不能把同色系银蓝仅因更深就称为撞色。无可靠金属证据时才使用`analogous|contrast` 两分支，其中撞色先以约 180° 对向色生成基线候选，再比较 KV 中有面积或重复证据、彩度与明度更高的鲜明色；最终记录 `contrastDerivation=hue-opposition|kv-vivid-accent`，不能把后者伪称严格补色。若无可靠金属证据且缺少可靠的有彩 `surfaceContrastBasis`，不能伪造撞色基准；在只读阶段一次性说明缺少输入。

来源色只是依据，不是直接复制到 UI 的 Token。允许在保持色相家族、冷暖与角色来源的前提下，为大面积、交互和文字分别派生合适的明度和彩度。

### 2.1 初始选色顺序与提案前硬门禁

每套方案严格按以下顺序形成，不能先拍 Hex 再补理由：

1. **先锁定一个表面家族。** 从稳定环境锚点中为该方案选定唯一 `surfaceFamilyId`，再从它派生 `page/card/container/border`。比较候选时先看环境身份，再看连续面积、空间稳定性、实际 Hero 可见下缘的连接关系及延展后是否自然；大面积连续环境优先于人物、建筑、树叶、标题、局部反光等前景物。底部区域若被局部前景、阴影、装饰或具体纹理主导，排除为页面背景锚点并回到整张 KV 的大范围环境色；若是大片草原、海面、天空、雾光、较纯颜色或低纹理渐变，则把底部延伸列为强候选，但仍与其他连续环境按空间合理性、整页面积效果、卡片层级和视觉舒适度比较，不自动胜出。把结果写入 `heroBottomExtensionDecision`：选择延伸时记录接缝起点和纯色/渐变延续配方；未选择时记录更优环境证据及衔接方式。多个环境锚点只是候选，不等于可以逐个分配给不同大面积表面；除非 KV 本身存在可延展到 UI 的连续多色环境，并已记录其空间关系，否则四个大面积表面不得跨到另一色相/冷暖家族。
2. **再建立显著性与明度拓扑。** 结合 `targetUiMode/targetSurfaceDepth`、`semanticPriorityMap` 和原稿层级，先写 `targetSalienceOrder / roleLightnessPlan / targetLuminanceTopology`，明确页面→卡片→容器的可辨关系，以及按钮/CTA 相对真实宿主的主体明度方向。`targetUiMode=light` 时默认使用明亮但不漂白的表面拓扑：页面背景保持较高明度和可识别主题彩度，但不能接近无色白；撞色方案须冻结 `cardSurfaceStrategy=tinted-near-white|pure-white-atmosphere`：卡片通常比页面更亮并显著降低 HSB 的 S；当页面/KV 彩度高、卡片面积或重复较大时可用 S=0 的纯白稳定底，只在原有顶部氛围/Chrome 保留淡主题色。内部容器在二者之间或以同家族轻微深浅差分层。若原结构需要其他顺序，须证明卡片边界仍清楚且页面没有灰白化。不能用趋同的表面明度冒充层次，也不能让与 KV 光照和目标表面深度不符的暗部占据大面积。
3. **再建立彩度、受光与强调家族目标。** 写入 `colorClarityPlan.lightnessAndChroma` 与 `colorClarityPlan.hsbGuardrails`。页面中的主要操作只按 UI 模式和尺寸分为 `深色 UI 小按钮 / 深色 UI 大按钮 / 浅色 UI 小按钮 / 浅色 UI 大按钮` 四类；按钮自身方向另记 `bright|metallic|clean-deep`，高光、渐变、立体不新增类型。普通鲜亮按钮的所有可见主体本色色标以 `B=100` 为默认门禁；用户指定的 `gold-bright` 暖亮金示例允许 `B98–100` 的近满明度色标。更低 B 只允许用于深色 UI 中有可靠金属证据的金属主体/金属深端分段，或浅色 UI 的已选 `clean-deep` 按钮，且须单列来源、面积与真实宿主证据。白色高光、透明端、极小阴影和结构层不参与主体门禁。大小按钮分别记录亮端、主体中间调、稳定暗端、包边/深度层、面积职责与排除项，分别 PASS 后才比较共同 `buttonPrimary`。普通鲜亮 Icon 的稳定主体色标可优先 `B=100`；`B=100` 本身不判过亮。每案冻结 `iconPairPlan`，用真实卡片、底托、图形面积和重复频率联合选择图形/底托配方；原 Icon 的可见渐变若由低 S/高 B 到高 S/高 B 建立层次，目标须逐 stop 保留可感知差异，不能把全部 stop 指向同一个 `icon` Hex。为每案先比较约 180° 对向色与 KV 高彩高明度色在真实宿主上的预期突出程度，再写 `accentFamilyPlan`：`iconSource=surface-environment`，从背景/卡片连续环境家族派生 Icon 稳定主体并记录来源、派生的明度/彩度与重复面积；`targetUiMode=dark` 时设 `darkNumberSync=icon`，六色提案的 `number` 和 `icon` 必须使用相同 Hex。浅色 UI 的高亮数字可按宿主独立选择，但数字/Icon/按钮默认不出现第三个显著高彩家族。金属 Icon 的小面积环境反射不计作稳定主体，不能靠反射把 Icon 主体换成另一家族。同时冻结 `controlColorSalienceOrder=icon-container < selected-tab < primary-button`，不要求按钮 B 高于 Icon B。
4. **最后才派生代表 Hex。** Hex 必须服务前三步的关系，并在预览板上按近似真实面积检查；不能期待 Phase 3 的材质展开或 Phase 5 的高光补救一套本身已灰闷、过暗或表面割裂的平面色板。

提案展示前逐套记录 `proposalColorPreflight`：

```text
surface-family-coherence       page/card/container/border 来自同一表面家族，且层级可辨
surface-anchor-validity        主锚点来自可延展环境；底部候选满足可见、连续、面积、纯度与环境身份条件
hero-bottom-extension         已判断底部是否适合延伸、是否采用及原因；采用时接缝连续，未采用时有更优环境与衔接证据
luminance-topology             表面深度与交互主体明度方向符合当前模式和 KV 气质
lightness-and-chroma           浅色 UI 的页面明亮有彩；撞色卡片按 cardSurfaceStrategy 降 S、提明度，可用纯白稳定底；主操作按真实宿主选择明亮有彩或有证据的干净深色，不灰闷
ui-mode-size-button-hsb        只按深色 UI 小/大、浅色 UI 小/大四类记录；普通鲜亮主体 B=100，低 B 仅命中金属/clean-deep 例外
metallic-three-way             有可靠金属证据时，同色系金属 / 正常明亮金色 / 干净深色三案齐全；金色未被暗铜棕橙替代，深色未冒充金色或撞色
control-color-salience         三类角色并存时满足 Icon 底托 < 选中 Tab < 主要按钮/CTA；底托淡而可见，浅色 UI 的底托与 Tab 不暗沉，三层不近似或倒置
icon-pair-balance               Icon 图形与底托成组后无底托偏重、渐变塌缩成纯色、组合低分离或整页重复抢焦点
accent-family-economy          Icon 稳定主体来自连续背景环境；深色 UI 的 number/icon 锚点 Hex 完全相同；数字/Icon/按钮无第三显著高彩家族
icon-anchor                    功能 Icon 图形有独立锚点，符合 accentFamilyPlan；与底托、文字和宿主均清楚
lighting-and-area              受光面、暗部和高光的计划符合 KV 光照；不靠窄亮边伪装通过
contrast-candidate-comparison   无金属撞色比较对向色与 KV 鲜明色的来源、HSB、感知彩度/明度、预览面积和宿主分离；选择后者时说明为何更突出
palette-role-control           大面积色相受控；撞色只集中在小面积交互与强调
preview-review                 按角色面积预览后仍满足以上关系
```

任一项为 `FAIL/UNKNOWN` 时，留在 Phase 2 修正或淘汰该候选，不能展示给用户选择。同一 UI 模式的所有候选默认保持同一个 `surfaceFamilyId` 与表面明度拓扑，只改变交互方向；只有明确要比较不同表面家族且两者各自有 KV 环境证据时才允许不同，并说明变量，避免一次改变过多维度。

## 3. 固定的方案矩阵

先按金属证据决定矩阵，再按新 KV 明暗决定需要覆盖的 UI 模式：

| 新 KV 情况 | 无可靠金属证据 | 有可靠金属证据 |
|---|---|---|
| `targetKvTone=dark` | 深/浅 UI × 同色系/撞色，共 4 套 | 深/浅 UI × 同色系金属/正常明亮金色/干净深色，共 6 套 |
| `targetKvTone=light` | 浅色 UI × 同色系/撞色，共 2 套 | 浅色 UI × 同色系金属/正常明亮金色/干净深色，共 3 套 |
| `targetKvTone=mixed` 且无法可靠归入深/浅 | 深/浅 UI × 同色系/撞色，共 4 套 | 深/浅 UI × 三个金属按钮方向，共 6 套，并说明不确定来源 |

因此，未另行限定时：

- 无可靠金属证据时，沿用 `A/C`：`A=analogous`，`C=contrast`；撞色优先比较可靠的 `hue-opposition` 候选，并允许有证据且更突出的 `kv-vivid-accent` 胜出。
- 有可靠金属证据时，改用 `M/G/D`：`M=metallic-analogous`，`G=gold-bright`，`D=clean-deep`。三者是按钮方向，不得互相合并或换标签。
- 用户明确限制 UI 深浅时，只保留该模式下的 2 套无金属方案或 3 套金属方案。

用户在当前请求中明确限制“只看浅色 UI”“只看深色 UI”或某一按钮方向时，删除不符合要求的方案，不拿无关方案让用户再次选择；否则按上表完整输出。

## 4. 交互候选怎样搭配

### 同色系 `analogous`

- 页面、卡片和内部容器从稳定环境色及其深浅/邻近色派生。
- 按钮/CTA 从 KV 主体稳定本色、材质中间色或同一主家族的邻近色派生；功能 Icon 的稳定主体从背景/卡片连续环境提取。深色 UI 的高亮数字与 Icon 公开锚点同 Hex，浅色 UI 的数字按真实宿主选色；Tab 保持在表面家族内。
- 同色系不等于所有角色同 Hex。用明度、彩度、已有材质和面积建立层级，但主要小按钮与 CTA 必须共享同一个 `buttonPrimary` 代表色和主体中间调。

### 无可靠金属证据：撞色 `contrast`

- 页面和内部容器仍从新 KV 的稳定环境色派生；卡片维持同一冷暖关系，但优先用低彩近白或纯白稳定底，主题色只留在原有顶部氛围/Chrome。
- 先以 `surfaceContrastBasis` 为基准生成约 180° 的 `hue-opposition` 候选；再同屏比较 KV 中有面积/重复或明确主题语义的高彩高明度候选，包括紫色、粉色等非 180° 色相。分别记录来源区域、HSB、感知彩度/明度、按钮面积和真实宿主分离。KV 鲜明色更突出且操作层级、文字与材质可成立时，选 `contrastDerivation=kv-vivid-accent`；否则选 `hue-opposition`。不能只用白卡的亮度对比比值、单一 HSV S/B 或最暗阴影决定。
- 撞色必须在综合色相上与同色系方案产生可见区别；仅把同一蓝色、绿色或其他家族压深/提亮，不得标为撞色。
- `buttonPrimary` 同时约束卡片内主要小按钮与全局 CTA 的代表色、主体色相和中间调。两者的暗部、高光和反射可以按原材质结构调整，但不能形成肉眼可见的黄/橙或其他跨家族分裂；次级、禁用或语义不同的按钮必须在方案选择前有明确角色证据。
- Tab 选中态默认使用表面家族或其邻近色，通过明度、彩度、边界、文字或既有指示条表达状态；其颜色存在感须高于普通 Icon 底托、低于主要按钮/CTA。除非用户明确要求或原业务语义有强证据，Tab 不使用按钮撞色。功能 Icon 图形仍按状态清晰度、面积与材质决定颜色，普通 Icon 底托不能引用按钮强度。
- 撞色集中用于按钮与少量有证据的高亮，不能把背景、卡片、Tab 和多个大面积模块分别铺成不同色相；深色 UI 的关键数字仍与环境来源的 Icon 同色，不跟按钮撞色。普通文字仍按真实表面选合适的带倾向中性色。
- `contrast` 是无可靠金属证据时的视觉撞色方向，不保证色相严格互补；金属三案仍独立处理。

### 有可靠金属证据：三种按钮方向

- `metallic-analogous`：从本次金属的稳定本色、中间调、暗部和高光派生同色系金属按钮。银色可得到银、银蓝灰或环境反射后的冷金属色；金/玫瑰金按实际画面派生。它仍是同色系金属，不因深浅差被叫作撞色。
- `gold-bright`：固定提供一套正常明亮金色按钮作为金属对照。优先从类似 `#FFEED7→#FFC58A`、`#FFEEC6→#F9DB92`、`#FFE5A3→#FFC165` 的暖亮范围建立主体与暗部关系，再按当前 KV 光照微调；不得把示例机械照抄，也不得偏到暗铜、棕橙、土黄。主体中间调必须明确呈现金黄，具有较高感知明度、有效彩度和充足受光面积；暗部只负责塑形，高光不能成为唯一“金色”证据。按钮字默认使用深棕色，并分别核对最亮、最暗和文字覆盖区；只有深棕确实失败且另有明确视觉证据时才允许偏离，不能先把金色整体压暗来迁就白字。
- `clean-deep`：固定提供一套干净深色按钮，从 KV 的深色主体、标题、金属暗部或稳定环境深端选择最协调的有来源家族。它必须有清楚色相和稳定中间调，不得灰黑、脏褐或只剩亮边。以 `#BE9D72→#966F3F` 的明暗关系作为校准：亮端可落在约 `S 40–45 / B 70–80`、稳定暗端约 `S 50–65 / B 58–65`，稳定主体最低执行 `S >= 40, B >= 58`；实际 Hue 仍从本次 KV 取证，不固定使用棕色。
- 三套方案共用相同页面、卡片和 Tab 表面家族；主要小按钮与 CTA 在各自方案内共用该方案的 `buttonPrimary`。金色不扩散到 Tab，Tab 仍保持表面同系。

## 5. 每套方案的交付格式

无金属矩阵使用 `D-A/L-A/D-C/L-C`。金属矩阵使用 `D-M/L-M`（同色系金属）、`D-G/L-G`（正常明亮金色）、`D-D/L-D`（干净深色）。内部提案增加 `buttonVariant=analogous|contrast|metallic-analogous|gold-bright|clean-deep`，并继续保存来源锚点、表面家族、`cardSurfaceStrategy`、`iconPairPlan`、明度拓扑、彩度/受光目标、优势、风险和 `proposalColorPreflight`。面向用户的预览只展示以下六个冻结锚点：

```text
background  页面连续背景代表色
card        主卡片稳定表面代表色
number      关键数字/数据强调代表色
icon        普通功能 Icon 图形代表色，不是 Icon 底托
button      主要小按钮与 CTA 共用的 buttonPrimary
tab         选中 Tab 的表面同系代表色
```

用相同角色顺序并排展示方案，并用 `scripts/render_palette_proposals.py` 生成只读角色预览板；背景和卡片按较大面积表达，数字、Icon、按钮和 Tab 按局部面积表达。渲染器输入只是 `themeDecision.paletteProposal` 的展示投影：`colors` 必须且只能包含上述六个角色，门禁证据仍保存在完整提案对象中。输出图片和输入哈希清单只保存到本次 `runWorkspace`，不得落入稳定 `artifacts/` 或复用旧提案。必须看过预览再完成 `preview-review`，不能只验证 JSON 字段。提案阶段不复制页面、不替换 KV、不写 Figma UI，也不把预览板当成真实材质试色通过；任务成功完成后随 `runWorkspace` 一并清理，用户明确要求保留审计包除外。

按钮预览字色分情境：仅特别鲜艳的无金属撞色按钮设置 `buttonTextPriority=vivid-contrast-white`，优先显示白字；渲染器不得仅因深字静态比值较高替换它。其他按钮按材质、宿主和可读性选择字色，预览的自动字色仅是临时候选，不能被当成 Figma 定稿；`gold-bright` 仍默认深棕字。需要显式指定预览字色时，同时提供 `buttonTextColor` 与非空 `buttonTextEvidence`：特别鲜艳撞色若指定深字，证据须指向真实 1:1 白字对比度不足及深字选择依据；其他方案的证据说明情境选择。输出清单记录实际预览字色，Phase 5 再用真实按钮验证。

渲染器对深色方案执行 `number/icon` 公开 Hex 的 RGB 精确相等预检，失败即拒绝生成预览；Icon 是否确实来自连续背景环境、共色在真实宿主上是否清楚仍由只读取色证据与视觉预览判断，不以这个数值检查代替。

用户选定方案后，把六个值保存为 `schemeAnchorContract`。Phase 3 可为文字、描边、容器、氛围和材质层派生更多色标，但必须引用这六个锚点并保持角色关系：页面/卡片不得静默换家族，关键数字不得改用无关强调色，普通功能 Icon 图形须引用或有依据地派生自 `icon`，主要小按钮与 CTA 的主体必须共同引用 `button`，Tab 必须共同引用 `tab`；Icon 底托不是第七个公开锚点，须从表面方向派生，并与 `tab/button` 共同满足 `icon-container < selected-tab < primary-button`，同时在真实卡片上保持可见。渐变暗部、高光和反射不是额外主题色，不能用它们把最终视觉改成另一套方案。任何锚点家族、代表值或上述显著性顺序的实质变更都使用户选择及下游门禁失效，必须重新展示方案并确认。

六个值必须各自绑定至少一个稳定可见的 `anchorId` 目标通道，RGB 与公开方案值一致。`tab` 不能只保持“同色系”却在落稿时改成 `button` 或 `icon` 的代表色；`button` 也不能因材质展开而从用户选择的代表色漂到另一个橙/黄/蓝。代表试色写入后先读回锚点一致性，再允许扩展；任一错绑或漂移都回到 Phase 3，若需要改变公开锚点则必须重新展示方案让用户确认。

```sh
python3 scripts/render_palette_proposals.py palette-proposal.json palette-proposal.png
```

## 6. 用户确认是写入前门禁

仅将 `proposalColorPreflight=pass` 的全部规定方案写入 `themeDecision.paletteProposal`，状态设为 `awaiting-user-palette-choice`，向用户展示方案 ID、代表色和角色关系，并可给出一条有依据的设计建议，但不得代替用户选择。规定数量中的候选失败时先在 Phase 2 内重做，不能少给一套或把失败方案交给用户筛错。

用户明确选择方案 ID 或清楚指定其中的 UI 深浅＋色相关系后，记录：

```text
themeDecision.paletteSelection.status = selected
themeDecision.paletteSelection.schemeId
themeDecision.paletteSelection.selectedAt
themeDecision.paletteSelection.userInstruction
```

选择前禁止进入 Phase 3 的最终配方冻结、Phase 4 复制/KV 替换和任何 UI 写色。选择后由该方案展开完整 Paint Recipe，再执行预检、代表试色、全页扩展和验收；后续合法的材质微调不重复请求配色选择。用户改变方案时使旧配方、试色门禁及其下游证据失效，但继续使用同一原稿审计；尚未创建副本时不要提前创建。
