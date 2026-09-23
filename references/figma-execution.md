# Figma 执行规范

画风迁移模式的条件和最小差异白名单见[《画风迁移规则》](style-adaptation.md)。启用时，仅其登记的风格外观允许覆盖本文件的原材质/图片/Paint 结构保持限制；业务结构与精确保护不变。


Phase 1 前完整读取。本文只规定 Figma 节点识别、快照、复制、解绑和分阶段写入；颜色选择以《颜色决策规则》为唯一来源。

每次调用 `use_figma` 前必须加载并遵守 `figma:figma-use`。默认自主执行，只有真实权限、目标、素材或结构阻塞才向用户提问。

## 1. 解析目标

- 只接受 `figma.com/design/...`。
- 优先当前唯一选中且经旧 KV/Hero 核实的顶层 Frame；否则使用 URL `node-id` 指向并经核实的顶层 Frame。没有选中画框不是阻塞；当链接指向 `PAGE` 或仅提供文件链接时，只读枚举该页顶层 Frame 的名称、尺寸、层级与旧 KV/Hero 证据，唯一确认原活动页即可继续复制。已有换肤副本不得仅凭名称/位置误认作原稿；多个候选经核查仍不唯一时才请用户指明。
- 目标父级必须为 `PAGE`。
- 写入前必须实际读取新 KV，不得根据文件名或描述猜测。
- 旧 KV 容器和其中承担主视觉的 IMAGE Paint 必须由名称、位置、层级和截图共同确认；多个合理候选时继续只读核查有效可见性、图片和构图，仍不能唯一确定才请求用户指明。

为寻找右侧空位，只读取同 Page 其他顶层 Frame 的 `id/name/x/y/width/height`。除非用户明确要求参考，不得截图、取色或读取可能已完成同一 KV 换肤的相邻页面 Paint。

## 2. 建立 `sourceAudit`

写入前读取整页和关键区域截图，并遍历目标子树。记录：

```text
目标与父级 ID、名称、x/y/width/height
顶层相邻节点边界
节点类型统计、子节点路径与顺序
Fill、Stroke、Effect、样式与变量绑定
全部 IMAGE Paint 分类、路径和证据
逐节点 paintPresenceMask
旧 KV 容器与可替换 Paint、Hero 外框与下方 UI 起点
旧图绝对/相对变换、全部祖先 clipsContent/蒙版与实际可见窗口
复合异形表面的前后层、遮挡、Alpha、blendMode 与蒙版
卡片氛围层和锚点
KV 衔接信息带
一级/二级 Tab、状态和实现方式
视频封面 protected-media-overlay 精确节点清单
排行榜前三名 protected-rank-top3 的名次文字、形状及原色指纹清单
独立营销 Banner protected-marketing-banner 的完整子树与原始外观指纹清单
全部换肤相关实例和主组件信息
语义组件到 visualSurfaceCarrier 的映射
sourceSalienceMap 与 sourceLuminanceTopology
```

### IMAGE Paint 分类

每个 IMAGE Paint 必须分类：

- `kv`：允许替换的主视觉。
- `content-media`：视频、封面、头像、作品图等内容，保持不变。
- `brand-media`：Logo/品牌图片，保持不变；已确认属于被新 KV 替代的旧 Hero 视觉资产时，适用第 5 节 `kv-asset-subtree` 例外。
- `protected-rank-top3`：承载排行榜前三名名次/奖牌/领奖台形状的位图，保留原图片哈希、Paint、滤镜、Alpha 和效果；不得误归类为可换色的主题装饰。
- `theme-decoration-raster`：只承担旧主题纹理、光雾、边角装饰或染色。
- `unknown-image`：证据不足，保持不变并继续核实实际贡献/语义；若明显旧色阻碍结果，先核查分类及允许的调整路径，只有仍无法安全处理时报告具体素材阻塞，不在第一次分类不明时停止全任务。

`theme-decoration-raster` 可以保持图片哈希、几何、变换和节点整体 Alpha，只调整 Paint 滤镜和 Paint Alpha。同模式不得归零；跨模式只有滤镜无法协调且不承载内容/业务含义时，才可把该 IMAGE Paint Alpha 降为 0 并记录。

IMAGE 位于 `protected-marketing-banner` 子树时，优先服从该保护分类，不能因同时含有主题插画、文字或装饰而改归 `theme-decoration-raster`。

## 3. 找到真实视觉承载层

语义角色与绘制节点必须分开。对每个卡片、容器、Tab、标签和按钮遍历完整局部子树及内容同组兄弟节点，检查所有带 Fill、Stroke 或颜色 Effect 的 Rectangle、Vector、Boolean、Ellipse、Frame 等节点。无语义名称不是跳过理由。

卡片标题还须读取 TEXT 本体的每层 Paint、局部文字区间与渐变色标；Icon 要从底托深入到可见图形子树，区分 Vector/Boolean/IMAGE、Fill/Stroke/Effect 和稳定主体层。清单分别标记 `title`、`icon-glyph` 与 `icon-container`，不能以换掉父级卡片或底托代替本体。位图图形或烘焙按钮若不能在保护边界内安全换色，记录素材阻塞；不得叠加新图形、Rectangle 假按钮或新文字来掩盖旧像素。

`visualSurfaceCarrier` 至少由两类证据确认：

- 位于文字/Icon 下方的 Z 顺序。
- 覆盖并空间重叠对应内容或状态区域。
- 轮廓与容器/选中态一致，或经父级裁切形成最终形状。
- 同类组件出现相同结构。
- Paint 对截图真实贡献像素。

窄下划线标为 `state-indicator`；边角光斑和纹理标为 `decoration`；大范围柔光标为 `card.atmosphere`。复合表面拆为：

```text
surface-base / surface-highlight / surface-shadow
surface-stroke / state-indicator / decoration
```

不得只改语义父 Frame，也不得给空父级另铺普通底色。承载关系不确定时暂停该区域写入，继续读取同组兄弟、Paint、裁切/蒙版和截图；穷尽安全核查仍不能确定才报告该区域阻塞，不以面积、坐标、名称或原色猜测。

### 3.1 排行榜前三名的精确颜色保护

使用 `protected-rank-top3` 记录以下保护范围，优先级与 `protected-media-overlay` 相同，高于全页换肤、文字阶梯、Icon/材质配色和旧色清理规则：

- 前三名的名次文字或数字，例如 1/2/3、第一名/第二名/第三名，以及相应编号图形。
- 专属于这三名的徽章、奖牌、名次底托、领奖台/异形背景、头像名次装饰框，以及组成这些形状的描边、高光、阴影、丝带、星形等附属装饰。形状即使位于姓名或收益文字下方，也保留原色。
- 上述对象的所有 Fill、Stroke、渐变色标与 Alpha、带颜色 Effect、多色 Vector region Paint 和相关图片参数，均与原稿一致；不能只保护一个主 Fill，漏掉边缘、阴影或小数字。

先用截图、名次内容与层级确认角色。领奖台常按“第二、第一、第三”排列，不按从左到右索引认定名次，也不因页面其他位置出现数字 1/2/3 就扩大保护。对每个实际存在的名次记录源节点 ID/路径、角色、截图证据和完整 Paint 指纹；不存在前三名时记录空集合及原因。

保护外的榜单标题、外卡片、Tab、按钮、姓名、收益/分数和第四名及之后的普通编号仍按角色换肤。头像等内容图片本身沿用既有内容保护。不得直接跳过整个排行榜或前三名的混合内容组件；受保护形状与普通文字共享父级时，只跳过受保护节点自身的颜色通道，继续检查后代。共享 TEXT/Vector 中同时含保护与非保护内容时，按文字区间/矢量区域建立映射，禁止整节点覆盖造成误改。

建立 `sourceAudit.protectedRankTop3`，并在 `mutationPlan.protectedRankTop3Ids` 和必要的 `protectedRankTop3PaintRanges` 中映射到副本。保护项不进入代表/扩展写色白名单；每次写入前检查重叠。固定色交付时，副本保护项仅允许解除颜色变量/颜色样式引用，保持有效 Paint/Effect 色值与外观不变；将该引用差异单独登记，不能把它当作受保护颜色的换色许可。需要修复误改时，只允许按原稿颜色/材质指纹恢复并记录 `protectedColorRestorations`，不得以修复为由改成新主题色。

完全受保护的节点从写色 ID 集合排除；混合节点则按“节点 ID＋属性/文字区间/Vector region”判断白名单与保护集合的交集，允许写非保护通道，但必须保留保护通道完整指纹。不能因为节点 ID 相同就整组跳过，也不能因为允许改一个区间就覆盖整个节点的 fills。

若为处理保护范围之外的内容而解绑祖先，解绑后必须重建保护映射并逐项比对。不得为前三名名次/形状重新配色而解绑实例；也不得通过祖先整体 Alpha、滤镜、混合模式或额外覆盖层间接改变这些保护对象。合法外卡片背景变化引起的透明边缘合成差异不等于保护 Paint 被改动，不能因此重着色补偿。

### 3.2 独立营销 Banner 创意内容保护

页面中不承担通用卡片、列表、任务或奖励结构，只作为独立营销传播位存在的 Banner，把其定制插画/图片背景、活动文案与促销构图登记为 `protected-marketing-banner` 并保持原样。典型证据是横向或独立比例的完整视觉单元，内部颜色与素材共同组成已经完成的营销创意；不能只凭节点名称含 `banner` 判定，也不能把普通业务卡片误保护。

保护范围按语义子树/通道精确登记：创意背景、插画、图片和营销文案的 Fill、Stroke、渐变、文字颜色、图片参数、Effect、Alpha、blendMode、几何与层级均与原稿一致，不因含旧主题色而进入残留清理。Banner 内或紧邻 Banner、可单独识别且可编辑的 CTA、按钮与通用操作控件必须从保护集合中剔除，继续进入对应按钮家族换肤；不能因它们嵌套在同一个实例或视觉上属于促销构图就漏改。只有操作画面已烘焙进不可编辑单图，或用户明确要求整个 Banner 连同控件保持原样时，才允许整体保护。不得通过保护祖先的滤镜、透明度或覆盖层间接改变已保护创意，也不得用祖先保护跳过未保护 CTA。

在 `sourceAudit.protectedMarketingBanners` 保存根节点、实际受保护后代/通道、显式排除的 CTA/控件、截图证据、营销语义证据与外观指纹；受保护集合映射到 `mutationPlan.protectedMarketingBannerIds` 并从写色/残留目标中排除，CTA/控件则映射到各自交互家族。Phase 7 分别对保护集合做零差异比较、对排除控件做目标配方比较。无法区分营销创意与普通卡片/控件时继续读取同类实例、内容和宿主关系，证据仍不足才把该区域列为写入阻塞，不能猜测换色。

## 4. 结构与 Paint 快照

以子节点索引路径记录原稿：

```text
type、name、visible、locked、opacity、blendMode
x/y/width/height、rotation、constraints、圆角、裁切
Auto Layout、对齐、padding、gap
子节点数量、顺序和父子关系
文字内容与全部字体排版
Fill/Stroke/Effect 数量、类型、顺序、颜色、Alpha 与几何
渐变类型、transform、色标数量和位置
图片哈希、变换、缩放和滤镜
蒙版、布尔和矢量几何
itemReverseZIndex、实际绘制顺序、蒙版类型及同组作用范围
组件、实例、组件属性、样式和变量绑定
```

`paintPresenceMask` 记录每个 Fill/Stroke/颜色 Effect 是否存在、可见、具有非零有效 Alpha 并实际参与渲染。对复合异形卡额外保存每层 Z 顺序、Paint/节点 Alpha、blendMode、isMask 和可见边界；对媒体保护区及前三名颜色保护区保存完整 Paint/Effect 指纹。

完整快照一次保存并复用；工具输出可返回分组统计、稳定指纹与差异，原始数据须完整保留可追溯，不反复传输整树制造重复读取。几何指纹和颜色指纹分开：例如 `vectorNetwork.regions[].fills` 是 Paint，不混入几何哈希；顶点、线段、区域拓扑/绕向仍逐项保护。原稿审计仍比较全部字段，不能因副本允许改 Paint 而放松原稿检查。

优先复用[《局部试色与执行工具》](execution-workflow.md)第 4 节的采集与差异脚本，不复制历史任务中的固定 ID 或旧规则。副本颜色解绑的 `fillStyleId/strokeStyleId/effectStyleId`、文字局部颜色样式及颜色 `boundVariables` 路径须逐项列入差异许可；保护项只豁免引用元数据，不豁免显示色、Paint/Effect 结构或材质。采集错误、缺失字段和不可比映射必须显式处理，不能忽略后记 PASS；中间阶段只读回受影响属性/依赖，原稿及副本最终仍做完整结构核对。若 Figma 上游组件集损坏，使某个实例的 `componentProperties` getter 单独报 `Component set for node has existing errors`，采集器可以在该字段留下 `$unavailable`，并在 `unavailableFields` 逐实例披露；其余字段、子树、Paint 和文字必须继续完整采集。此例外只适用于这一条精确错误，不把字段缺失当成成功读取，也不豁免原稿与副本在可读属性上的比较；最终报告受限字段。

## 5. 任意比例 KV 自动适配与旧资产叠层

默认遵循用户的 KV 尺度要求：先按新 KV 在 Figma 中的原设计尺寸直接使用；需要匹配页面宽度时按同宽等比显示，不能为容纳较长尾部而整体缩小。高度超出原 Hero 时，允许截去下方超高部分，Hero 外框与下方 UI 起点不变。源像素尺寸与设计尺寸分别记录，高分辨率资源不按像素数当设计尺寸。禁止拉伸、AI 重画/扩图、重排图中文字或混入旧主题。只有用户明确要求整张完整显示时才采用下文 contain 分支；不可把旧的完整显示默认值盖过当前尺度要求。

适配前先确定 `sourceVisualUnitType=single-image|composite-kv`。用户指定的新 KV 若是 Frame、Group、Component 或其他由多个 IMAGE、Vector、文字、遮罩、纯色/渐变层共同构成的完整主视觉，整棵指定节点就是原子级 `composite-kv`；不能因为其中某个 IMAGE 看起来最像主图，就只抽取该内层图片替换。记录整组原设计宽高、子节点相对几何、裁切链、每层 Paint 与渐变变换、可见下缘过渡及截图指纹。

`composite-kv` 在页面同宽且原设计宽度已匹配时默认 `scale=1`、顶部对齐；Hero 较矮时由 Hero 可见窗口裁去整组下方超出部分，不能把整组 resize 到 Hero 高度。需要同宽时只做一次统一等比缩放，内部各层共享同一变换；不得单独缩放某个子层、重算内部渐变或改变文字/主体相对位置。若 Figma 结构限制导致整组无法可靠克隆/重挂，可把完整复合节点按原设计尺度导出为单张图并作为 `kv-main-image` 放入；这是保真兜底，不能退化为导出或复用某个内层 IMAGE，源 KV 节点本身不修改。

新 KV 已含底部纯色或渐变衔接时，它属于复合主视觉的一部分，必须精确保留渐变类型、`gradientTransform`、色标数量/位置/Alpha、方向与最终下缘颜色。若其终点被选作页面延伸色，页面从该实际终点继续；不得翻转、重建或叠加旧接缝渐变。旧 KV 的衔接层已被新 KV 覆盖时按 `kv-asset-subtree` 抑制；确需复用并重着色时只改已登记的色标颜色/Alpha，保持原 `gradientTransform` 和位置，禁止写入默认恒等 transform。任何渐变方向或色标位置变化都必须来自用户明确要求或独立的结构修复计划，普通换肤/KV 适配不授权。

### 5.1 先确认实际可见安全窗口

区分三个对象：受保护的 `heroFrame`（页面中的 Hero 外框）、旧图 `imageCarrier`（可能负偏移、超大或嵌在蒙版内）、最终用于主图显示的 `heroVisibleWindow`。**不能只把旧负偏移图片节点改为 `FIT`，也不能直接把旧图节点尺寸当作 Hero 可见尺寸。**

- 用层级、绝对变换、截图和第一段下方 UI 的边界确认 Hero 的原有范围；其位置、宽高、圆角、裁切、Auto Layout 占位及下方 UI 起点保持不变。
- 沿选定主图载体的全部祖先读取 `clipsContent`、蒙版、圆角和变换，把裁切区域换算到 Hero 局部坐标并求实际交集。记录裁切链；旋转、圆角或非矩形蒙版不能只用外接矩形代替真实可见区域。
- 安全窗口由真实 Hero 边界和有效裁切决定，不把返回、规则、钱包、客服等功能叠层的位置自动扣除为整圈留白。导航覆盖 KV 背景是正常叠放关系；先验证原尺寸/同宽显示，不因存在叠层就加顶部或左右内边距。非矩形裁切核对真实可见边界，必要时按 5.3 避开旧 KV 专用内层蒙版。
- `hero-adjacent-ui` 的位置、尺寸、层级和可见性保持不变。截图确认叠层实质遮挡关键标题、Logo 或主体时，先在现有 Hero 内检查最小定位修正；不能为导航留白或尾部完整而整体缩图。用户要求完整显示的 contain 分支另按其边界处理。高度有差异时先检查真实裁切和可复用的 KV 专属载体，不从少量高度差推导大幅缩小，不移动控件或下推首卡。

### 5.2 分开计算保留尺度与完整显示

使用解码后方向正确的原图尺寸或完整 `composite-kv` 原设计边界 `Iw × Ih`，安全窗口 `x,y,W,H`；尺寸必须为有限正值。默认 `fitMode=preserve-scale-bottom-crop`：有源设计尺寸时优先使用原设计尺度；需要同宽时采用 `s=W/Iw`，不使用高度限制缩放。顶端对齐，居中或按原合理 x 放置，记录超出 Hero 下方的实际高度；单图载体或复合视觉单元保留完整等比尺寸，由既有 Hero 边界裁切，不把载体 resize 成不同宽高比。关键内容若意外被切，先检查载体、祖先和最小定位修正，不自动退回 contain。

仅用户明确要求整图完整显示时令 `fitMode=contain`，在 Hero 局部坐标计算：

```text
s = min(W / Iw, H / Ih)
imageWidth = Iw * s
imageHeight = Ih * s
imageX = x + (W - imageWidth) / 2
imageY = y + (H - imageHeight) / 2
```

contain 分支默认居中；为固定功能控件或接缝做顶部/底部对齐时，只可在安全窗口余量内平移，保持整个图像矩形可见。保留尺度分支默认顶部对齐，按实际 Hero 边界记录下方截去区域。保留小数精度，不能分别取整宽高造成比例变化。原变换只有在已满足当前 fitMode 的尺度/裁切结果时才沿用；否则自动改 `scaleMode`/`imageTransform`，无需审批。

### 5.3 最小写入例外

按最少变更选择实现，并在写入前列出节点与属性白名单：

若 KV 位于实例内而本地覆盖不支持必要的几何/增层操作，可按第 9 节先解绑对应副本实例并验证解绑前后视觉一致，再执行下列适配；原稿实例和主组件不变。

若 `sourceVisualUnitType=composite-kv`，优先把完整根节点作为一个单元 clone/reparent 到副本 Hero 的 KV 层，并只对根做统一等比尺度与定位；内部节点不进入普通 KV 适配写入白名单。放置完成后把根加入 `kvLockedSubtreeRootIds`，采集内部节点顺序、Paint、文字、素材、渐变、相对几何与渲染指纹。后续 UI 颜色解绑、写色、旧色扫描和自动残色修正均不得遍历进入该子树；任何操作目标是其根或后代都须在写入前报错。结构或跨文件限制导致无法可靠保留整组时，先导出完整根节点，再按第 3 项的单一 `kv-main-image` 路径放置；必须保存完整导出与源截图比对证据。以下针对 IMAGE Paint 的路径不得被用来只替换复合 KV 的某个内层图。

1. 若现有载体及其祖先已覆盖安全窗口，优先在指定 IMAGE Paint 上重设适配模式/变换，让主图按当前 fitMode 落入计算边界；保留无关 Paint、混合模式和效果。
2. 若现有载体仅属于 KV，可调整其 `x/y/width/height` 以匹配计算边界。不得更改作为 Hero 外框或参与页面布局的载体尺寸，不得移动同节点承载的功能 UI。
3. 若旧载体负偏移、含混合内容或内层蒙版使以上操作不可靠，允许在 Hero 内合适的既有祖先下新增**最多一个**独立 `kv-main-image` Rectangle。它使用原始新图 IMAGE Paint、正常不透明显示和等比计算尺寸；在 Auto Layout 下设绝对定位，不参与尺寸计算。放在功能 UI 后方，并避免继承旧 KV 专属裁切。原 KV 的指定 Paint 可将 Alpha 设为 0；不删除旧节点，不关闭含功能内容的祖先。新增载体不是新增页面模块。
4. contain 留出的空间或图片透明区域，可复用 Hero 的 KV 专属环境底层；没有合适层时允许新增**最多一个** `kv-environment-backdrop` Rectangle，或在 KV 专属载体中增加一个底层 Fill。使用新 KV 稳定环境/边缘色的 SOLID 或克制渐变，覆盖 Hero 内留白，位于主图之后、功能 UI 之后。不得从标题/Logo/主体高光取补底色，不复制放大整张图充当背景以免出现重复主体，不添加新插画，也不描画地面曲线、建筑轮廓或其他原图元素来延展构图。禁止先人为缩图制造留白再补底。补底不能越出 Hero，也不能改 UI 卡片的 Paint。

以上仅为 `kvFitPlan` 中的 KV 适配例外，不放开 Hero 外框、页面布局、UI 几何、蒙版、混合模式、字体或文案保护。所有既有 UI 节点的相对顺序保持不变；因新增 KV 节点导致索引变化时，用原稿→副本节点映射对照，不能跳过整段结构审计。

### 5.4 旧资产与执行记录

旧 Hero 若由背景图片加标题/Logo/主体图形叠层组成，而新 KV 已烘焙对应内容，可把有父级路径、截图和语义证据的 `kv-asset-subtree` 节点整体 Alpha 设为 0，保留 `visible=true` 和 Auto Layout 占位。只隐藏被替代的 KV 资产，不隐藏整个 Hero 或混合内容祖先。倒计时、周期、规则、状态、返回、分享和导航属于 `hero-adjacent-ui`，必须保留。其中叠在 KV 上的返回、规则、钱包、客服、分享及同类导航/功能入口，精确标记为 `protected-hero-controls`。同模式全部样式仍按原 UI 精确保留，不参与画风迁移或旧色清理。浅→深或深→浅时允许适配前景，遵守下述唯一规则；不通过祖先透明度、覆盖层或移动入口间接适配。倒计时、周期及 Hero 外信息带不自动豁免，仍按独立角色处理。

**跨模式入口配色例外。** 仅 `light-to-dark` / `dark-to-light` 生效，在副本中优先调整精确入口文字及对应功能图形的 Fill/Stroke RGB，使其适合真实新 KV 背景；不套普通文字弱化阶梯，不改变现有状态。原稿以及入口几何、字体、文案、素材、渐变空间结构、混合模式、节点/祖先 Alpha、效果有效开关保持。已有底托默认保留；仅当前景调整仍不能满足真实可辨性或用户明确指定的对比度标准时，允许最小联动其颜色与 Paint opacity，必须用原/新宿主、前景候选及失败证据说明必要性，不能新增底板或影响 KV 构图。将精确节点、属性前后值、模式、原因和原稿基线写入 `mutationPlan.heroControlAdaptations`，纳入试色、覆盖、结构白名单及最终入口审计。已登记适配通道校验目标配方，其余通道精确保留；同模式和媒体/前三名保护项不引用此例外。跨模式前景与实际宿主按《验收规则》第 5.1 节的 contextual 策略验收，原稿比值保留作参考；真实可读性、状态层级与用户明确标准仍是门禁，不为追赶旧比值把既有底托强行加深或拉满 opacity。

在 `mutationPlan.kvFitPlan` 记录：

```text
sourceVisualUnit: single-image / composite-kv、完整根节点、原设计宽高与截图指纹
sourceImage: 单图时的宽高、方向、文件/imageHash、解码与源清晰度证据；复合 KV 时为全部成员和完整导出兜底证据
compositeSnapshot: 子节点顺序、相对几何、裁切/蒙版、Paint、渐变类型/gradientTransform/色标位置/Alpha、文字与素材指纹
bottomTransition: none / embedded-in-new-kv / reused-old-layer、实际终点、方向所有权及保持证据
heroFrame: ID、原始外框、下方 UI 边界
clipChain: 主图所经祖先 ID、变换、裁切/蒙版形状与求交证据
heroVisibleWindow: Hero 局部坐标 x/y/W/H、内接/避让依据
directFitCheck: 原尺寸/同宽显示的真实边界与截图，是否可直接使用；若缩放/补底，记录实际冲突而非假设留白
protectedHeroControls: 精确节点/通道、原稿样式快照与副本映射
fitMode: preserve-scale-bottom-crop / contain，用户依据
imageFit: 单一 s、原设计尺寸、imageX/imageY/imageWidth/imageHeight、对齐理由、可见/下方截去区域
carrier: 原/新节点 ID、父级与层级、原/新 Paint 模式和变换
backdrop: none 或节点/Fill、环境取色证据、配方与边界
allowedMutations: 逐节点 ID/路径、Paint 索引、允许属性及前后值
kvLockedSubtreeRootIds / kvLockedSubtreeFingerprint / kvLockedSubtreeScreenshot
hiddenKvAssets / suppressedOldKvPaints / protectedHeroUiIds
sourceToCloneNodeMap: 既有节点对应关系与新增节点清单
renderEvidence: Hero 截图、实际尺度与下方裁切符合计划、复合 KV 内部几何/渐变方向未变、接缝连续、关键标题/Logo/主体核对、UI 未位移；contain 另核对完整四边
```

先完成可见窗口与适配白名单，再写入；截图若有非计划裁切、尺度变化或旧图透出，在同一副本重算窗口、载体或补底并复验。仅真实的文件/权限/唯一目标问题，或无法在受保护 Hero 内形成任何有效窗口时，才说明具体阻塞。

## 6. 复制和替换

在 `clone-and-kv` 阶段：

1. 用稳定 ID 重读原稿，确认关键快照未变化。
2. 只调用一次 `clone()`，明确 `appendChild` 到原 `PAGE`。
3. 保持副本名称、`y`、尺寸，以及 KV 适配例外之外的内部结构。
4. 在原稿右侧寻找无碰撞位置，240px 是默认起始间距而非必需值；可按现有画布空间调整，保持副本根 y，且不得移动现有节点。
5. 按第 5 节执行 `kvFitPlan`，仅替换/适配白名单内副本 KV 主图、必要补底及被替代的旧 KV 资产；复制 Paint 数组后重新赋值。
6. 返回原/副本 ID、位置、Paint 索引、新旧 imageHash、尺度/裁切适配记录和 Hero 实际截图。

本阶段禁止任何 UI 颜色写入；KV 专属环境补底属于图像适配，可在本阶段执行。新 KV 放置完成后立即冻结锁定子树，后续阶段不能把它当作副本 UI 全树的一部分参与颜色解绑或主题映射。若调用失败，先检查是否已经生成副本，禁止盲目再次复制。

## 7. 建立 `mutationPlan`

在首次 UI 写色前，为每个目标记录：

```text
节点 ID/路径、语义角色和 visualSurfaceCarrier
原 Paint 与每层职责
目标 Paint Recipe 和选色理由
局部背景与显著性目标
是否属于氛围、复合表面、Tab、媒体/前三名颜色保护或 KV 衔接
允许的 Paint/Alpha/配方差异
是否需要实例本地覆盖或解绑及原因
```

同时按《局部试色与执行工具》第 6 节建立 `mutationPlan.regionPlan`：卡片/完整视觉区域是 Phase 6 的完成单位，角色配方仍可跨卡复用。视觉上归属卡片但位于其 Frame 子树外的兄弟叠层不得漏登记；页级共享底色只登记一次，其他区域引用其状态。

把 `kvLockedSubtreeRootIds` 作为所有区域计划的 `excludedSubtreeRootIds`。工具建立允许写入集合、扫描旧色或遍历颜色绑定时遇到这些根必须停止下钻；不是只保护根节点本身。任何 `operations[].cloneId` 落入锁定子树均为预执行失败，不能先写后恢复。

按《局部试色与执行工具》第 1 节建立 `trialScenes`、依赖和精确写入通道，再汇总 `representativeNodeIds`。覆盖普通卡、收益复合卡、标题、多层功能 Icon、小按钮、一级 Tab 和 CTA 的实际角色；按《叠层合成审计》区分非等价材质、状态和背景。先列实例→代表映射，再写色；必要共享背景 Paint 单独登记为 `sharedContextPaths`，不能只写前景、用旧背景验证新方案。

保护节点/区间与写色白名单必须无交集；仅因保护区域与普通内容同属一个实例，不能扩大跳过范围。按《颜色决策规则》第 5、8 节规划 `cardAtmosphereReview` 与 `buttonCompositeReview`；强度差异分别登记 `atmosphereMutations` / `buttonMaterialAlphaOverrides`，包含节点、通道/索引、层职责、原/目标值及合成问题。

## 8. 分阶段颜色写入

颜色写入必须是相互独立的调用：

```text
representative-trial → trial-review(pass) → expand
```

### 代表试色

- 只允许修改 `trialScenes` 中代表节点、必要 Paint 后代及确切共享背景通道；依赖节点不自动获得写权限。
- 禁止通过全树遍历、旧色相、坐标、面积或名称发现并修改其他节点。
- 每个区域调用都传入 `excludedSubtreeRootIds=kvLockedSubtreeRootIds`；KV 内命中的旧 UI 相似色不进入残色计数，也不触发自动修正。
- 只读遍历可以进行，但写入必须由 ID 白名单驱动。
- 返回 `representativeMutatedNodeIds`，任何白名单外节点都使本阶段失败。
- 彩度、对比度或高光合成不满足目标时，在同一副本的同一白名单内依次写入候选配方并截图，记录每次实际使用的配方与结果，最终恢复选中的配方；禁止把仅有色板/文字描述的方案记为已渲染比较。

完成整个局部场景后再取 1:1 图并观察彩色、灰度、模糊和缩略图；整页图只检查上下文及意外影响，未扩展区域不参与本阶段残留/整页美观判定。按《局部试色与执行工具》第 2 节封存逐场景视觉证据与指纹，必要场景均有效通过后才能汇总 PASS。无改善时按其第 1 节重新诊断，不反复盲试。

### 全页扩展

- 必须在后续独立调用中验证对应场景门禁和新鲜读回指纹；配方、共享背景、映射或祖先变化使相关门禁失效，不能只查历史 PASS。
- 按 `mutationPlan` 的角色映射扩展，返回 `expansionMutatedNodeIds`。
- 按 `regionPlan` 一次完成一张卡片或其他完整视觉区域，区域内按背景/表面→材质→文字/Icon→操作状态的依赖顺序处理；请求超限时只在该区域内拆技术批次，不跨区域穿插。组合完成后统一截图并完成该区残色/保护/覆盖检查，通过后再进入下一区域。每批属性读回与保护检查不延后；不能用通用旧色扫描脚本覆盖全页。
- 一张有效区域截图可复用到多个角色检查；只重截变化区域，最终仍核对逐实例上下文和整页累计视觉重量。

所有批次的前值、目标值、部分失败和重试统一按《局部试色与执行工具》第 3 节落盘与恢复。正常属性批次不混入 clone/detach/增删层，失败后先读回，不假定异常意味着没有任何写入。

允许写入的普通属性仅为：

```text
SOLID Paint: color；Paint opacity 按对应角色 Alpha 规则（不能降低稳定结构表面）
GRADIENT Paint: gradientStops[].color/alpha（保持结构有效开关）
已有带颜色 Effect: color
已登记按钮材质 Fill/Stroke: SOLID/GRADIENT Paint opacity（仅 buttonMaterialAlphaOverrides）
已登记 card.atmosphere Fill: SOLID/GRADIENT Paint opacity（仅 atmosphereMutations）
已登记禁用按钮视觉单元根: node opacity（仅 disabledButtonOpacityOverrides；相对正常态有效倍率 50%）
已登记普通 TEXT: 自身 opacity（仅 textNodeAlphaOverrides，见《文字换色与恢复》）
```

必须复制 Paint/Effect 数组后赋值，保留结构层 Alpha、顺序、渐变几何和阴影几何；节点整体 Alpha 除已登记的普通 TEXT 自身例外、KV 资产隐藏和禁用按钮视觉单元根 50% 例外外不变。只有《颜色决策规则》定义的跨模式氛围、浅色→深色描边和收益卡 Fill 例外可改变相应结构。

按钮与氛围的已登记材质 Alpha 覆盖只调整合成强度，不构成结构重做；遵守《颜色决策规则》第 5、8.1 节。`dark-to-light` 中仅被判为 `remove-visually` 的纯装饰 `card.atmosphere` Paint 可把既有 Paint/色标 Alpha 降到 0；稳定底色、结构表面、功能边界及非氛围材质继续保持原零/非零开关。禁用按钮只允许在最小完整视觉单元根应用相对正常态 50% 的有效 opacity，并在写入前排除已有等效衰减，其他节点/祖先 Alpha 不变。Effect 只可改已有颜色 RGBA，不改变半径/偏移/类型/开关。氛围 IMAGE 必须另按既有分类和滤镜/Paint Alpha 边界处理。

多层 Paint 按职责逐层写入，禁止把同一渐变复制到同一节点多个 Fill。文字写入、普通 TEXT Alpha 例外与字体故障按[《文字换色与恢复》](text-color-recovery.md)执行，纯颜色写入不先加载字体。媒体和前三名颜色保护区的精确节点/通道完全跳过，写入后与原稿比对；误改只按原稿恢复。

## 9. 组件实例与解绑

可使用实例暴露属性、实例后代本地 Fill/Stroke 覆盖或解绑副本实例。无需机械保留组件关系。KV 适配所需的位置/尺寸/增层无法本地覆盖时，同样可计划解绑对应副本实例。

只要实例承载需换肤且不属于保护范围的卡片表面、氛围、Icon、按钮、标签、Tab、选中态、文字色或透明遮罩，而本地覆盖不能完整修改相关 Paint/状态，就必须解绑。仅承载受保护配色的实例无需解绑。解绑前记录实例路径、ID、主组件 ID/名称和组件属性；解绑后从稳定副本根重新发现节点 ID，并验证结构。

`detachInstance()` 可能把源实例未暴露的隐藏主组件子节点带入副本，使后续子节点索引后移。解绑后、任何换色或旧 KV 资产归零之前，必须先对照解绑前的源实例/副本快照，核对子节点数量、名称、类型、相对顺序及内容/几何指纹，重建原稿→副本 `sourceToCloneNodeMap`；**禁止直接沿用解绑前的索引路径或节点 ID 白名单**。同名节点不能只靠名称匹配，应结合父级、类型、顺序和指纹确认。

若确认出现仅由本次解绑产生、源实例中不存在、`visible=false` 且不含业务内容/状态/交互的额外节点，允许在副本移除该额外节点，作为恢复源实例结构的最小例外。证据必须同时包含解绑前快照、解绑后结构差异和隐藏/无业务依据，不能仅因节点隐藏或名称重复就删除；原有节点、有业务节点和来源不明节点均不得删除。清理后重新核对数量、顺序及渲染一致性，再更新 KV 资产、代表节点、保护节点等所有受影响白名单。无法可靠匹配时暂停该子树写入并继续只读核查，不凭旧索引猜测最后一个 Logo 或其他目标。

在 `mutationPlan.detachedInstances[].structureRecovery` 记录解绑前后数量、额外节点 ID/路径与指纹、来源/隐藏/无业务证据、实际移除集合、恢复后节点映射和截图。无额外节点时记录空集合；不得以结构恢复为由清理其他节点。

不得解绑原稿实例、修改主组件或批量解绑内容型无关实例。即使媒体或排行榜组件祖先解绑，精确 `protected-media-overlay` 与 `protected-rank-top3` 仍须与原稿一致；不能因此跳过封面外文字或前三名姓名、收益等普通内容。

## 10. 执行记录

把以下内容写入 `mutationPlan`：

```text
sourceFrameId / cloneFrameId / clonePosition / kvReplacement / kvFitPlan
visualSurfaceCarrierMap / paintLayerRecipes
regionPlan（区域归属、逐区状态与验收证据）
representativeNodeIds / representativeMutatedNodeIds
representativeCoverage
trialScenes / trialGates / sharedContextPaths
trialGateStatus（有效场景门禁汇总）与截图时间证据
batches（逐操作前值/目标值/读回、恢复和冲突）/ runId
expansionMutatedNodeIds
localInstanceOverrides / detachedInstances
protectedMediaOverlayIds
protectedRankTop3Ids / protectedRankTop3PaintRanges / protectedColorRestorations
buttonMaterialAlphaOverrides
textNodeAlphaOverrides / textColorRecoveryLog
atmosphereMutations / controlledExceptions
imagePaintClassification
skippedNodes 与原因
executionPhaseLog
```

禁止仅在最终回复中补写阶段记录。时间和节点集合必须证明代表试色发生在全页扩展之前。
