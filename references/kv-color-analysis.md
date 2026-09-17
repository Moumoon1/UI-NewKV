# KV 色彩分析

画风迁移模式的条件和最小差异白名单见[《画风迁移规则》](style-adaptation.md)。启用时，仅其登记的风格外观允许覆盖本文件的原材质/图片/Paint 结构保持限制；业务结构与精确保护不变。


Phase 2 前完整读取。先使用 Phase 1 已完成的 `kvStyleComparison` 与模式结论，再分析新 KV 配色；旧 KV 只用于画风比较和原结构理解，不把旧配色带入新色板。本文件负责理解新 KV 和确定可用颜色证据；禁止在本阶段修改 Figma，也不直接决定最终 UI Token。

## 1. 数据与 AI 的职责

数据提供颜色聚类、占比、空间分布、亮度、对比度和 KV 接缝证据。AI 必须判断：

- 主体、环境、材质和光照方式。
- 颜色是稳定环境色、主体本色、材质中间色、镜面高光、品牌色、文字色还是偶然反射。
- 小面积颜色放大到按钮、CTA 或大面积表面后是否仍协调。
- 画面气质、彩度、冷暖、情绪能量和空间光照。

不得把“春节、春季、科技、成长、儿童、奢华”等题材直接映射到预设 Hue。题材帮助理解画面关系，最终颜色由真实像素、面积、位置、材质和试色共同决定。用户约定的“春节／新春／过年按钮红色优先、金色备选”在 Phase 3 按《颜色决策规则》第 8 节作为候选偏好执行，不代替本阶段的颜色证据，也不据此预设页面、卡片氛围或 Icon 的颜色。

若有原始图像，优先读取原始像素；其次使用无 UI 污染的截图。只有视觉观察时不得伪造精确数值，应标记 `analysisConfidence=medium/low`。

## 2. 环境主色证据

只采样新 KV，不包含 UI、透明画布或相邻 Frame。以下数字是首轮分析参数，不是有效颜色的禁用门槛；记录所用参数，按真实图像调整并复核来源，不让算法漏掉高调、低彩度或透明材质环境。

1. 排除 Alpha `< 0.5`。
2. 第一轮排除 HSL `L > 80%` 的白色高光、反光和亮边。
3. 第一轮排除 HSL `S < 30%` 的灰白中性色。
4. 对剩余像素聚类，保留 Top 5 色群。
5. 圆形 Hue 距离 `±12°` 内的色群可作为合并候选，仍须保留空间与角色分组；环境暗部、主体材质和反光不能只因色相接近而合并为同一取色来源。
6. 最大稳定环境色相的加权中心作为 `themeHue` 候选。

AI 必须检查最大色群是否来自大面积环境。若来自标题、Logo、人物、主体局部或强光，不得认定为页面主色。

### 2.1 保留可追溯的颜色锚点

在现有 `kvAnalysis` 内维护 `colorAnchors`，供后续角色配色引用，不另外维护一份同义主色表。按实际图像区分稳定环境表面、环境暗部、弥散环境光、主体/材质与局部反光；没有的类别不补造。每个有效锚点包含 `id`、来源区域/坐标与图像引用、群内真实 RGB 样本或代表值、冷暖/色相倾向、可信度及适用角色。确认环境色时查看非相邻区域的重复分布，或同一连续区域的稳定性；不能以一个偶然像素为证据，也不固定采样数量。

- 聚类或粗量化只用来找区域和估计占比。最终代表色回到该区域/群内的原始像素计算，并与实际图像并排复核；量化格的中心、取整后的色值和色名不能替代真实取色。深暗、低彩度或多色图尤其要检查，不能让聚类合并抹掉红棕/黄棕、冷灰/暖灰等区别。
- 色相可信度与模式可信度分开。极暗或接近中性时，单一 HSV H 不作为稳定结论；结合可辨认的同类环境中间调、多个 RGB 样本和实际冷暖判断。可借助一致的感知色彩空间辅助诊断，不因数值漂移强行增加彩度。
- 一个 KV 可以有多个环境家族。保留各自空间、照明和面积关系；进入深/浅模式的 UI 角色应选择与其表面职责相符的锚点，不机械取全图平均色，也不只取底部色。
- 主体与环境锚点分别登记。某色可以同时承担多个角色，但每个角色都要有其来源证据；“同属暖色”“有金属主体”不足以把主体颜色扩展为整页背景或卡片氛围。

有效像素不足不透明像素 5% 时，可从 `S ≥ 15%`、`L ≤ 90%` 的放宽参数重新分析，也可按图像调整。被首轮筛掉的中性/高明度色单独保留为环境证据；筛选不足不等于无稳定环境。经实际图像复核仍无稳定 Hue 时令 `themeHue=null`，使用有证据的 KV 冷暖中性方向并记录可信度；禁止回退到固定蓝色或其他预设色。

## 3. 分开判断接缝、模式和表面深度

### 用户指定优先

在 `themeDecision` 中记录 `requestedUiMode=light/dark/auto` 和 `targetUiModeSource=user/kv-inference`。用户明确说“新 UI 做深色／浅色”时直接采用该 `targetUiMode`；未指定或明确选择自动时，再按下文环境证据推断。当前任务内用户后续修改模式，以最新明确要求更新相关配方和失效场景，不重新复制页面。

用户指定决定 UI 的目标模式，KV 仍提供色相、冷暖、材质与光照来源；具体 `targetSurfaceDepth` 在指定模式内选择。不能因为明亮 KV 就把用户指定的深色 UI 改回浅色，也不能因为 KV 深暗而拒绝浅色 UI。优先在允许的既有表面、氛围和 Hero 衔接层处理过渡，不擅自调亮／调暗 KV 图片，也不把“KV 与 UI 深浅不同”当成阻塞。

`sourceUiMode` 始终根据原稿 UI 实际判断，不能随用户的目标要求改写；`themeTransition` 用它与最终 `targetUiMode` 计算，供卡片氛围及文字规则使用；Icon／按钮还须结合 KV 明暗、色彩力度和真实宿主判断，不由转换方向直接推导 S/V 调整。用户指定整体深浅不表示所有局部组件都同深浅，实际宿主有例外时明确记录并按局部关系验收。

必须分别输出：

```text
source/targetHeroEdgeTone  KV 与页面接缝明暗
source/targetUiMode        light / dark / mixed
source/targetSurfaceDepth  very-light / light / mid-light / mid-dark / dark
themeTransition            sourceUiMode → targetUiMode
```

### 接缝明暗

旧/新 KV 底部不透明区域分别采样：

```text
stripHeight = clamp(KV高度 × 15%, 64px, 120px)
Y = 0.2126R_linear + 0.7152G_linear + 0.0722B_linear
```

- `medianY < 0.25` 且 `darkRatio ≥ 60%`：深色接缝候选。
- `medianY ≥ 0.35` 或 `darkRatio < 40%`：浅色接缝候选。
- 其他：`mixed`。

取样带大小及 0.25/0.35、40%/60% 是接缝候选的分析起点，可因分辨率、构图或实际显示调整并记录；R/G/B 先按 sRGB 转换为线性值。任何统计分支都不是 UI 深浅模式的自动判决。

底部遮罩、装饰带或局部暗边不得触发整套 UI 深色模式。

保留尺度并截去下方高度时，按主图在 Hero 的实际可见下边缘取样，不能用被截去的源图底部代替接缝；contain 有上下留白或透明区域时，源图底部也只是候选接缝证据。结合 `kvFitPlan` 的主图位置与环境补底规划判断实际 Hero→UI 衔接，并在 Phase 4/7 用最终合成截图复核 `targetHeroEdgeTone`。补底只能来自新 KV 稳定环境/边缘色，不得让旧背景或标题高光污染接缝判断。

### UI 模式与连续深度

以下证据在自动模式下用于决定目标深浅；用户指定时用于在指定模式内选择表面深度、配色和衔接，不能推翻其模式。先建立 `highlightMask`，排除或降权镜面高光、亮字、窄亮边、点状星光、局部光束和主体孤立受光面，再综合：

1. 上下左右是否存在连续稳定的环境场。
2. 亮区是可延展的天空/雾光/环境光，还是主体曝光和镜面反射。
3. 暗部是否形成大面积连续包络，而不是一条边缘或底部遮罩。
4. KV 底部与第一张卡片怎样衔接最自然。
5. 灰度、模糊和缩略图中由亮环境还是暗环境承担主要重量。
6. 夜空、日光、棚拍等场景语义只作为证据，不作自动规则。

中央主体很亮不自动等于浅色 UI；四周或底部略深也不自动等于深色 UI。类似“边缘较深但主体和稳定环境高调明亮”的 KV，通常应落在 `light/mid-light` 而不是近黑页面。反之，主体局部发光但整体被连续深暗环境包围时，可判为 `dark/mid-dark`。

`targetUiMode` 决定文字大方向和跨模式规则；`targetSurfaceDepth` 决定页面、卡片和容器的真实重量；`targetHeroEdgeTone` 只决定接缝。允许组合如 `targetUiMode=light + targetSurfaceDepth=mid-light + targetHeroEdgeTone=dark`。

原稿或自动推断的目标仍为 `mixed/uncertain` 时，降低可信度并先按实际局部宿主确认转换，未确认的区域不执行跨模式氛围转换；不得让底部统计替代判断。KV 接缝为 mixed 不会使用户已明确指定的目标模式变成 uncertain。

可靠时输出：

```text
light → dark  = light-to-dark
dark → light  = dark-to-light
light → light = light-to-light
dark → dark   = dark-to-dark
```

## 4. 颜色角色分类

对重要色群至少结合面积、空间位置、重复分布和材质属性分类：

```text
environmentColors       大面积环境和氛围色
uiContinuationPalette   可延展到页面、卡片和容器的稳定环境色
highlightOnlyColors     仅用于局部高光、关键数据或交互材质的强光色
subjectColors            主体稳定本色
materialMidtones         主体材质中间色
specularColors           镜面高光、折射、亮边和彩虹反射
supportingColors         有面积和重复度的辅助色
sparseAccents            面积很小但显著的局部颜色
brandColors              只属于品牌/Logo 的颜色
neutralColors            带冷暖倾向的中性色
semanticCandidates       可能承担成功、警告、错误、危险含义的颜色
cardAtmosphereCandidates 仅由环境色及邻近色构成的卡片氛围候选
```

必须分离：

- `uiContinuationPalette` 来自稳定环境场和 KV→UI 接缝，负责大面积表面。
- `highlightOnlyColors` 来自主体强光、镜面反射、标题亮字和窄亮边，不得生成页面底色。
- `cardAtmosphereCandidates` 只来自大面积环境色及邻近色。标题、人物、箭头、Logo、金属包边和局部反光不得升级为卡片氛围色。
- 交互颜色可以参考主体中间色、稳定辅助色或材质色，但最终由整页候选比较决定。
- 局部 Icon 底托独立于大面积表面和卡片氛围：保留环境色、稳定辅助色、主体/材质中间色、环境反射及协调中性色的来源证据，供《颜色决策规则》第 7.1 节选择。不得在分析阶段只输出主色的浅色变体，也不得把主色之外的有效色群全部排除；颜色能否用于底托由其面积、承托作用及与实际 Icon 的关系决定。

以上分类用于区分颜色承担的职责，不是只允许按钮使用少量浅色反光的取色白名单。主体稳定本色也应进入交互候选；环境色对页面/卡片氛围的限制不得套用到按钮。保留有依据色群的明暗和彩度跨度，不把鲜明主体色全部柔化为粉彩，也不从高光颜色直接推导整个按钮基底。低彩度和高彩度都须结合实际角色与背景判断，不预设红色、金色或任一色相胜出。

小于约 1% 的色群通常是高风险信号，不是绝对禁用。若只存在于品牌或高光，不得直接铺满按钮；若有明确主题级重复和结构证据，可进入交互候选。

### 4.1 区分 KV 明暗与色彩力度

在现有 `visualIntentProfile` 分别记录 KV 的明亮/深暗程度和淡雅/鲜明/混合的色彩力度，并关联环境、主体及材质锚点；不另建同义色板。判断连续区域、主体面积与重复色群，不能用最艳像素或局部高光代表整体。亮的淡雅 KV 与明亮的鲜红 KV 都可能高明度，但给控件的配色依据不同；深暗环境也可能包围鲜亮主体。

这些证据进入 Phase 3 的 `colorClarityPlan.lightnessAndChroma`，按《颜色决策规则》第 3.2 节决定按钮/CTA/Icon 的突出方向。目标 UI 深浅、KV 明暗与色彩力度、组件实际宿主相互独立；浅色 UI 不必使用浅按钮，深色 UI 不必使用暗 Icon。本阶段只记录证据，不提前写入固定配方。

## 5. 材质与光照证据

记录：

```text
dominantLightDirection: top / top-left / top-right / other / uncertain
specularSpatialPattern: linear / radial-bloom / edge-ring / flat / mixed / uncertain
surfaceChromaStrategy: 页面、卡片、容器如何分配色度
```

无法稳定判断光照时标为 `uncertain`，不得为套用按钮渐变而伪造方向。材质只决定高光、明暗分段、反射和边缘亮线的组织方式，不自动决定 Hue。

在 `visualIntentProfile` 中分别描述环境明亮程度、主体受光面的彩度/明度、阴影面积和高光集中程度。高调明亮的环境、带颜色的受光主体与局部强反光可以同时存在；不能在排除环境取样中的高光后，也把交互和 Icon 所需的受光色一并排除。稳定材质中间色不等于深色或最暗色。页面延续环境，交互与 Icon 则在各自角色及原有材质结构内承接主体颜色与光照气质，不能只继承 Hue 而丢失明快感。低调深色 KV 同样按实际光照关系判断，不机械提亮。

## 6. Phase 2 必需输出

写入 `themeDecision.kvAnalysis`：

```text
themeHue 与色群证据 / colorAnchors（原始像素、空间角色、适用范围与可信度）
source/targetHeroEdgeTone
source/targetUiMode
source/targetSurfaceDepth
themeTransition
visualIntentProfile
environmentColors / uiContinuationPalette / highlightOnlyColors
subjectColors / materialMidtones / specularColors
supportingColors / sparseAccents / brandColors / neutralColors
cardAtmosphereCandidates
dominantLightDirection / specularSpatialPattern / surfaceChromaStrategy
analysisConfidence 与所有不确定项
```

缺少稳定环境与高光分离、UI 模式证据或连续表面深度时，Phase 2 不得通过。算法排名、题材名称或单个最亮/最深区域都不能作为最终结论。
