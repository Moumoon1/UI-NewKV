# 表面系统硬门禁

本门禁解决两类不能再依赖整页目测的问题：同级卡片稳定底色被拆成不同家族，以及裁切边、页面末端出现直线断色。规则适用于所有正式换肤，不以“视觉上大概协调”代替。

## 1. 自动发现

先运行：

```sh
python3 scripts/surface_system_audit.py discover source-before.json > surface-candidates.json
```

工具先从冻结原稿枚举全部可见、非文字、非图片 Fill，不设宽度、高度或面积门槛。尺寸只能帮助理解层级，不能决定一个节点是否值得检查。语义清单中标为页面/背景/表面/卡片/容器/面板/区块/Chrome/氛围的节点，以及每张已确认卡片下面的**全部**可见非文字 Fill 后代，必须进入 `surfaceSystemPlan` 并且只分类一次。分类可为 `page / card / container / chrome / interaction / atmosphere / decoration / icon / state / protected / proxy`；进入清单不等于被判成容器，真正的结构职责决定分类及后续门禁。工具同时枚举所有有彩色后代越过 `clipsContent` 边界的裁切线。

这意味着主内容底板、通知条、分组面板、按钮底、图标与装饰层都不能因尺寸被发现逻辑静默跳过；其中只有承担内容承载或视觉分组职责的节点归为 `container`，按钮、图标、状态和装饰分别进入自己的分类与既有门禁。若某节点是否为容器不明确，必须回看原稿层级、重复关系、内容承载范围和真实 1:1 图，不能以“超过 35%”之类几何阈值代替语义判断。

占比和内缩仍是重要的**正向证据**。审计在卡片语义确定后输出候选相对最近卡片的 `widthRatio / heightRatio / areaRatio`、四边 `insetsPx`、左右/上下是否对称，以及与常见内容间距 `8 / 12 / 16 / 20 / 24 / 32px` 的近似命中。宽高占据主要内容区、左右内缩相近，并沿用卡片的 8/12/16px 或更大 Token 间距时，应优先检查它是否为主内容容器；内部还承载多行、列表或重复内容时，结构证据更强。上述数值不是穷举白名单：特殊异形、单侧入口、嵌套容器或非标准 Token 即使没有命中，也不能退出清单。

## 2. `surfaceSystemPlan`

把审核后的计划放入 manifest，并通过 `prepare_semantic_preflight.py` 的 `reviewed-choices.surfaceSystemPlan` 原样传入：

```json
{
  "schemaVersion": 1,
  "sourceHash": "...",
  "surfaces": [{
    "id": "income-card",
    "nodeId": "...",
    "kind": "card",
    "carrierPaths": ["/nodes/.../props/fills/0/color"],
    "stableRepresentativePath": "/nodes/.../props/fills/0/color",
    "hostSurfaceId": "page",
    "boundaryRelationshipId": "income-card-to-page",
    "basis": "原稿稳定底板及真实宿主证据"
  }],
  "cardBaseGroups": [{
    "id": "peer-content-cards",
    "surfaceIds": ["income-card", "task-card", "works-card"],
    "additionalDeltaE": 1,
    "basis": "原稿同级卡片稳定底色相同或接近"
  }],
  "boundaryReviews": [{
    "candidateId": "clip:node-id:right",
    "decision": "fade",
    "displayedGroupId": "clip-node-right-native",
    "basis": "内部装饰不得在裁切线形成有色矩形"
  }]
}
```

- `carrierPaths` 必须完整覆盖每个语义候选节点的全部可见 Fill 色通道；漏节点、漏 Paint 或重复分类均失败。
- manifest 的精确表面角色必须与这里的 `kind` 一致；`surface.container → decoration`、`card.chrome → container` 等跨职责改名直接失败，不能用第二份分类绕过第一份门禁。
- `candidateGeometryEvidence` 保存候选相对真实卡片的占比和内缩，只用于支持职责分类和 1:1 审核，不得作为删除候选或自动降级为装饰的依据。
- `stableRepresentativePath` 只指稳定底板，不拿氛围高光、描边、按钮或文字冒充卡面。
- 每个 `card` 必须且只能进入一个 `cardBaseGroup`。目标卡片组的最大 ΔE76 不得超过原稿组内最大 ΔE76 加 `additionalDeltaE`；额外余量只能为 `0–3`，不能事后放宽到容纳错误结果。
- 每个非根页面、卡片和容器必须绑定真实宿主及 `kind=surface` 的对比关系，关系必须包含双方节点、样本和非零 `minimumDeltaE`。跨模式仍服从验收规则的更严格下限。
- 卡内节点先按原稿职责分类；确认为 `container` 后，无论尺寸大小，都必须冻结 `minimumDeltaE >= 4`。目标为浅色 UI 时还必须同时冻结不低于最小值的 `maximumDeltaE`。前者阻止容器淡到消失，后者阻止为追求可辨而压成灰棕重块；最终数值由真实 1:1 合成样本验证。
- 自动发现的每个裁切边和非根页面底部终点必须在 `boundaryReviews` 中恰好出现一次，并绑定 `displayed-relations` 的原生 1:1 像素组。只写人工 PASS、只看缩略图或漏登记均失败。
- 每个像素组的 `xy` 必须以不超过 4px 的跨度实际跨过自动发现的根坐标边线，并位于该边的有效区间；`nativePixels` 必须等于根画板原生尺寸。`continuous/fade` 的 `maximumChannelDelta` 上限为 `16/255`，`[1,1]/[2,1]` 等与真实边界无关的占位坐标和事后放宽阈值均失败。
- 裁切边线恰好位于原生 PNG 外沿时，图外像素不存在。该像素组可预先冻结 `samplingMode=root-edge-inward` 和非空 `samplingBasis`：左/顶沿使用第 0、1 列/行，右/底沿使用最后两个可见列/行。仅检查实际画框外沿的内侧裁切质量，不宣称已比较图外宿主；内部边界不能采用此例外。
- 卡片稳定底与同一卡内 Chrome/氛围/装饰的可见 SOLID 若源 sRGB8 相同，审计自动建立源同色组并要求目标 sRGB8 仍相同；容器、交互、Icon、状态和保护内容按各自职责门禁，不靠这条规则吞并。

规则账本中的 `surface-system` 机器规则须以 `{type:"surface-system",planHash:...}` 绑定完整计划。冻结、静态/完整预检和最终 `finalize` 都会重新运行审计；任何局部修正改变计划或表面颜色后，旧哈希和旧样本立即失效。

## 3. 判定边界

本门禁不要求所有卡片使用同一 Hex，也不替代审美判断。它只阻止没有原稿依据的同级表面分裂、缺少页面/卡片边界样本，以及漏审的裁切/末端接缝。源稿确有独立卡片家族时，应在写入前建立独立组并保存依据；不能从换肤后的错误颜色反推拆组。

## 4. 按颜色依赖执行换肤

本规则不预设任何组件形状，也不要求每个 UI 都有背景代理。逐完整视觉单元先识别颜色职责，再为独立职责选色；有依赖的颜色沿真实依赖派生，不能仅按组件类型或旧 RGB 映射。

| 颜色职责 | 目标依据 | 真实渲染验收 |
|---|---|---|
| 信息/操作前景 | 已选语义配方与真实宿主 | 可读、可操作，维持原有优先级 |
| 背景代理 | 对应位置的宿主合成外观 | 留白、遮挡、透底、连续或消隐关系成立 |
| 材质/受光 | 主体材质配方及原色标职责 | 高光、中间调、塑形暗部关系保留 |
| 状态表达 | 同族正常态和既定业务状态 | 选中、禁用等状态仍可辨，背景代理不随之错误强调 |

背景代理不是独立内容容器，不套用容器“必须与背景拉开”的最小色差，也不是可随意减弱的装饰。用原有载体维持原有职责，不新增形状或修改尺寸/Z 顺序/蒙版。简单、稳定、正常不透明宿主可直接继承其基底；Alpha、渐变、纹理或状态叠加时须检查实际局部合成，不能把裸 RGB 相等当成外观相等。把代理直接透明化可能暴露背后内容，不能默认采用。

在现有 `surfaceSystemPlan.surfaces` 中，对确认的背景代理登记 `kind=proxy`，其 manifest 承载路径使用 `role=surface.proxy`，不标六色 `anchorId`。没有这类职责的 UI 不需要代理条目，既有信息、表面和材质门禁照常执行。条目示例（字段以当前任务真实路径和原生像素坐标替换）：

```json
{
  "id": "background-proxy-unit",
  "nodeId": "dependent-carrier",
  "kind": "proxy",
  "carrierPaths": ["/nodes/dependent-carrier/props/fills/0/color"],
  "hostSurfaceId": "actual-host-surface",
  "appearanceGroupIds": ["host-dependent-appearance"],
  "visualReviewRuleId": "host-dependent-responsibility",
  "basis": "原稿完整单元中该承载层借宿主外观实现具体视觉目的"
}
```

每个 `appearanceGroupIds` 对应已启用机器规则中的 `surface-linked-appearance`：`targetBasis=surface-recipe`、`anchorPath` 为宿主真实承载路径、`carrierPaths` 为依赖承载路径、`anchorPointIndex=0`。关系覆盖全部依赖通道，`nodeIds` 包含依赖层和宿主。冻结同一局部环境里的宿主/依赖层原生采样点；多宿主时用 `hostSurfaceIds` 列出全部稳定宿主（替代单个 `hostSurfaceId`），每个宿主各有自己的真实锚点和依赖组；空间变化明显时登记相应的多组依赖，不用一个平均色代表整块背景。既有显示关系门禁对新鲜原生图验证“源外观等价、目标跨度不扩大”，机器规则须在冻结、预检及终审保持启用。

`visualReviewRuleId` 指向有明确 acceptance、依赖层及宿主 scope 的视觉规则，完整单元仍由已有 visualUnits 覆盖。验收直接回答源职责是否兑现：该消失的层是否融入背景，该遮住的内容是否遮住，该保留的间隔/连续关系是否成立；边缘、状态、背景发生变化后重算影响闭包并使旧证据失效。不以属性未变、目标色正确、个别像素相等或整页缩略图通过替代。

`surface_system_audit.py` 拦截缺宿主、把代理归为独立装饰/容器、代理独立锚点、缺依赖通道/原生关系或视觉义务。它不能从任意图形自动判断语义；源职责识别与采样位置仍需原生图审查。这项限制不能用新的组件特例掩盖。
