---
name: blender-modeling-review
description: 按五级商业梯度和百分制成绩单独立审核 Blender 模型与资产的工程可用性、四边面拓扑与大纲规范、造型还原、光影法线和 UV/PBR 品相。在白模送审、成品材质送审、外部导入初筛和正式入库前调用。
metadata:
  version: "1.0.0"
---

# Blender 建模商业质量审核

这份技能属于 [建模部门](https://github.com/tsist/blender-ai-workflow/blob/main/skills/blender-work-methodology/references/departments/modeling.md)，管一件事：用一把对标主流商业资产市场（Superhive、BlenderKit、StemCell、CheckMate Pro、Khronos 3D Commerce）和 Blender 5.3 原生特性的尺子，客观量出每件作品能不能按商业标准交付，并落盘一份统一格式的百分制成绩单 `quality-scorecard.json`。

## 四档标尺与独立盲审规矩

每次审核先明确本次委托的目标等级，默认正式交付与入库一律按 **L2** 把关：

| 等级 | 定位 | 放行条件 | 谁来执锤 |
|---|---|---|---|
| **L0 草稿探索** | 试大形与构思小样 | 看清造型方向即可 | 制作代理快看 |
| **L1 镜头自用** | 固定机位或单次远景配角 | G1 工程门禁全过，总分 ≥65 | 制作代理跑探针自检 |
| **L2 商业标准级** | **默认正式交付与入库线** | G1 与 G2 红线全过，总分 ≥80 且各梯度得分率 ≥70% | **未参与制作的独立只读子代理盲审** |
| **L3 旗舰主角级** | 特写主角、细分大件或可动精密机构 | 红线全过，总分 ≥90 且 G2、G3、G4 得分率均 ≥85% | **未参与制作的独立只读子代理盲审** |

过线之后再把预览图和成绩单呈给用户审看；没过线就带着具体问题单退回制作环节返修。

## 按五级梯度从上往下审，前级不过当场打回

先保文件干净和网格规矩，再看造型、光影与贴图。上一级红线没过，直接出返修单打回，省下后面白跑渲染的工夫：

1. **G1 工程生死门（15 分）**：另起进程冷重开零报错；零丢贴图、零本机绝对路径（贴图已打包或走 `//` 相对路径）；零负缩放与非有限坐标；法线、粗糙度、金属度贴图全设 `Non-Color`；视口隐藏或线框显示的布尔切刀已同步关掉渲染可见（`hide_render=True`）；细分修改器的视口级与渲染级一致。
2. **G2 拓扑四边面与大纲卫生（25 分）**：场景采用米制 `1 unit = 1.0 m`、Z 向上、正面朝 `-Y`，落地道具原点居底面中心且静态网格缩放已归 `1,1,1`；整件资产收在单一根集合下，清零 `Cube.001`、`Material.004` 等默认自动名与零引用孤立数据块；控制笼干净好改，细分曲面与可变形网格零 N-gon 且曲面上零 ≥6 边高阶极点（纯平面静态封口允许有护边的共面 N-gon，游戏导出档清零；15 mm 以内的微小螺丝铆钉豁免苛刻细分循环）。
3. **G3 大形比例与参考还原（25 分）**：多视角剪影轮廓、长宽高体量比例、标志性切口与分件关系，逐条对上开工前锁定的一致性核对单。
4. **G4 光影法线与运动变形（20 分）**：面法线一致朝外；5.x 法线修改器守住黄金顺序（`Bevel → Smooth by Angle → Weighted Normal(keep_sharp=True)`，有 `Data Transfer` 时置于栈底）；条形斜光扫过主曲面顺滑连贯、无极点夹捏与 UV 接缝黑线；控制笼局部试改不塌面，角色关节弯折或机构全行程无穿插。
5. **G5 UV 纹素、PBR 校准与双引擎品相（15 分）**：硬表面细分修改器开 `Keep Corners` 锁住 UV 边界；UV 岛留够 4–8 px 边距、棋盘格方正均匀；非金属 `Base Color` 落在物理区间 `30–240 sRGB`（避免靠 AgX 掩盖死黑过曝），法线用 Blender 原生 OpenGL `+Y`；Cycles、EEVEE Next（开光追阴影反射）与干净工程纯贴图重建版三者同机位一致。

只审白模阶段（审看①）时，G5 标为不适用，系统自动按前四项 85 分满分折算成百分制总分。各梯度的细则阈值见 [商业红线与 Blender 专检细则](references/commercial-gates.md)。

## 四步标准审核流程

### 第一步：跑只读数字硬体检（阶段 0）

在独立审计目录对保存好的 `.blend` 先跑公共 CLI 体检，再跑本技能自带的 Blender 商业探针脚本，全程只读原文件：

```powershell
$ctl    = './blenderctl.ps1'
$blend  = (& $ctl discover --summary | ConvertFrom-Json).data.selected_blender.file
$script = './.agents/skills\blender-modeling-review\scripts\commercial_qa_scorecard.py'
$batch  = 'work/audit/<batch>/'
$jobs   = Join-Path $batch 'jobs'
New-Item -ItemType Directory -Path $jobs -Force | Out-Null

# 1. 公共 CLI 基础几何与空间 BVH 体检
& $ctl --jobs-dir $jobs --compact model inspect $targetBlend --expected-sha256 $sha --qa-profile game

# 2. Blender 商业红线探针（可传 --qa-report 直接复用上一步的 qa-report.json，秒出默认名、切刀误渲、法线栈序、SubD 锁角、曲面极点/N-gon 分离与反照率区间）
& $blend -b --factory-startup -P $script -- `
    probe --blend $targetBlend --stage final --target-level L2 --output "$batch\commercial-probe.json"
```

查看 `commercial-probe.json` 里的 `hard_gates_passed`。一旦 G1 或 G2 红线报警，直接把报错对象名和位置发回建模环节修干净；属于纯数据贴图误标 `sRGB` 或未用空材质槽这类无争议小项，可让制作侧调 `model prepare` 的 `qa.fix_safe` 在新副本上一键修好。

### 第二步：拍标准看图包（阶段 1）

G1 与 G2 红线过关后，按阶段生成固定看图包并解码亲眼查看（优先用 `blenderctl preview` 隔离桌面真视口直出，默认已控制在 2048 像素以内且严格对齐正面 `-Y`；纯离线无桌面环境可回退 `model inspect --review-grid`）：

- **白模看图包**：
  - Quad 四视角实体+半透明线框：`& $ctl --jobs-dir $jobs --compact preview $targetBlend --mode solid_wire --layout quad`
  - 曲面流线与法线翻面联检：`& $ctl --jobs-dir $jobs --compact preview $targetBlend --compare-modes solid,solid_wire,matcap,face_orientation --view front_3q`
  - 局部搭接件特写：`--objects <对象名>`（默认留上下文查穿插，加 `--isolate` 独显查拓扑）与 `--mode wireframe --xray` 查内部穿插。
- **成品看图包**：
  - 同机位四阶段联检板：`& $ctl --jobs-dir $jobs --compact preview $targetBlend --compare-modes solid,solid_wire,material,rendered --view front_3q`
  - 四向环绕材质+线框（`--mode material --wire-overlay 0.35 --layout orbit`）、Cycles 快速渲染预览（`--mode rendered`，优先 DLSS 或显式标注 GPU OptiX 回退）与 EEVEE Next 光追对照（`--mode rendered --render-engine eevee --layout orbit`），再配标准 UV 棋盘格图与干净工程纯贴图重建对照。

### 第三步：逐梯度打分并复算成绩单

对照参考图一致性核对单、探针 JSON 和标准看图包，按 [计分规则与用途配置](references/scorecard-and-profiles.md) 给 G1–G5 打分并写明具体观察依据，把视觉评分写入 `visual-scores.json`，运行复算命令生成正式成绩单：

```powershell
$py     = Join-Path (Split-Path $blend -Parent) '5.3\python\bin\python.exe'
$script = './.agents/skills\blender-modeling-review\scripts\commercial_qa_scorecard.py'
& $py $script score `
    --probe "$batch\commercial-probe.json" `
    --scores "$batch\visual-scores.json" `
    --output "$batch\quality-scorecard.json" `
    --markdown "$batch\quality-scorecard.md"
```

### 第四步：出具结论与返修闭环

把 `quality-scorecard.json`、`quality-scorecard.md` 与标准看图包交给下游或用户：

- **达标放行**：交出总分、达到的质量等级（L2 / L3）、各梯度得分与看图包，进入用户审看或资产入库。
- **打回返修**：按梯度高低顺序列出问题部件名、截图机位、违反的具体条款和建议改法。返修出新副本后，核对新 SHA 重跑受影响梯度复验。

## 例子：盲审一件桌面监听控制器成品资产

建模与材质代理做完 `Monitor_Dial_v001.blend`，申请按 **L2 商业标准级**入库。主线程派一名未参与制作的只读审核子代理接手：

1. **跑阶段 0 探针**：`commercial-probe.json` 查出 13 个网格全部归在根集合 `Monitor_Dial` 下，米制 `1.0`、缩放全 `1,1,1`、贴图 57 张全部打包且法线粗糙度均为 `Non-Color`，顶盖 2 个内凹五边面经法线检测确认为有护边的纯共面平面封口，曲面 ≥6 边极点为 0，`hard_gates_passed = true`。
2. **看成品图包**：审看四向图、旋钮滚花特写、UV 棋盘格图，以及 Cycles 节点版、干净工程纯贴图版和 EEVEE Next 光追对照图。发现旋钮刻度线清晰方正、拉丝高光连贯，唯独底壳背面铭牌区纹素密度略低。
3. **合成成绩单**：G1 得 15/15、G2 得 24/25、G3 得 23/25、G4 得 18/20、G5 得 13/15，运行脚本算出 `total_score_100 = 93.0`，且各梯度得分率均超 85%，通过 **L2 商业标准级**（并达到 L3 线）。
4. **交接**：把 `quality-scorecard.md` 和三联对照图呈给用户做最终材质审看，底壳铭牌密度备注为可选后续优化项，用户点头后交 [blender-asset-manager](https://github.com/tsist/blenderctl/blob/main/skills/blender-asset-manager/SKILL.md) 入库。

## 参考

- [商业红线与 Blender 5.x 专检细则](references/commercial-gates.md)
- [五梯度计分规则、用途配置与 JSON 格式](references/scorecard-and-profiles.md)
- [行业标准与项目证据来源](references/sources.md)
- 只读商业探针与成绩单复算脚本：`scripts/commercial_qa_scorecard.py`

维护：唯一维护源是 `./.agents/skills/blender-modeling-review/`，改完运行同步脚本更新各镜像。
