# 商业红线与 Blender 5.x 专检细则

本表汇总了跨平台商业标准（CheckMate Pro v2、StemCell v2、Khronos 3D Commerce、Epic Fab、Unity Asset Store）与 Blender 生态标准（Superhive、BlenderKit、Blender Studio、Blender 5.3 原生机制）的核心卡关边界。

## 一、G1 工程生死门红线（L1 / L2 / L3 全部必过）

| 检查项 | 探针码 | 合格标准与原因 |
|---|---|---|
| 独立冷重开与有限坐标 | `non_finite` | 新进程后台打开零异常，全部顶点世界坐标为有限实数。 |
| 变换无负缩放 | `negative_scale` | 全部对象缩放分量为正数；负缩放会在导出引擎后把面法线整片翻黑。 |
| 数据贴图色彩空间 | `data_texture_srgb` | 接入 Metallic、Roughness、Normal、Bump、Displacement 等非颜色通道的贴图统一设为 `Non-Color`，避免伽马曲线扭曲高光和凹凸。 |
| 贴图完整与相对路径 | `missing_texture_file` · `absolute_texture_path` | 全部外部图像已打包进 `.blend` 或采用包内 `//textures/` 相对路径，清理干净 `<LOCAL_PATH>/`、`<LOCAL_PATH>/` 等本机绝对路径，换台电脑照常打开。 |
| 材质槽有效 | `empty_material_slot_in_use` | 被网格面实际引用的材质槽均绑有有效材质球，避免引擎导入出现品红丢材质块。 |
| 切刀与辅助体关渲染可见 | `cutter_render_visible` | 视口隐藏（`hide_viewport`）或设为线框盒（`WIRE` / `BOUNDS`）的布尔切刀、缩裹母面，同步勾选 `hide_render=True`，防止正式出图把切刀一起渲进画面。 |
| 视口与渲染细分一致 | `modifier_level_mismatch` | Subdivision / Multires 修改器的 `levels` 与 `render_levels` 对齐（或渲染级按明确规格高一级且无穿插），防止视口看着贴合、渲染时鼓包错位。 |

## 二、G2 拓扑四边面与大纲卫生红线（L2 / L3 商业必过）

| 检查项 | 探针码 | 合格标准与原因 |
|---|---|---|
| 米制物理尺寸与朝向 | `unit_scale_mismatch` | `scene.unit_settings.system == 'METRIC'` 且 `scale_length == 1.0`（1 单位 = 1 米），Z 轴向上，资产正面朝 `-Y`（Blender 正前视图）。 |
| 原点定位与缩放归零 | `unapplied_scale` · `ground_z_offset` | 落地道具原点设在底面中心 `[0,0,0]`，可动件枢轴落在真实转轴中心；静态网格缩放统一应用为 `(1, 1, 1)`，避免倒角和实体化（Solidify）厚度变形。 |
| 单一根集合与语义命名 | `root_collection_check` · `default_datablock_name` · `orphan_datablocks` | 整件资产收在同一个与资产同名的根集合下（内部可按 `GEO_`、`RIG_`、`COLL_` 分组），方便 Asset Browser 一键拖入和 Library Override；彻底清零 `Cube.001`、`Sphere.002`、`Material.004` 默认名及零用户孤立数据块。 |
| 网格基础健康 | `nonmanifold_edges` · `degenerate_faces` · `duplicate_verts` · `zfighting` · `inside_out_islands` | 清零孤立点线、零面积退化面、重合顶点、共面重叠闪烁面与法线内翻壳体（薄片叶片、开口袖口等合理开放边按设计核销）。 |
| 四边面与 N-gon 精确分界 | `curved_ngons` · `planar_ngons` | **细分曲面与可变形网格**：零 N-gon。**静态硬表面**：曲面上零 N-gon；纯共面平面封口（面内点共面且邻面法线平行）若有内插护边挡住平滑拉扯，L2 原生档允许保留，走 `game` 游戏导出档时三角化或四边化清零。 |
| 曲面高阶极点控制 | `curved_pole_ge6` | 有曲率变化的可见表面清零 ≥6 边的星形极点（五边 E-pole 挪离主高光脊线）；包围盒对角线小于 15 mm 的独立螺丝、铆钉等微型标准件豁免苛刻细分循环。 |

## 三、G3–G5 Blender 5.x 专属工艺卡点

- **5.x 法线修改器黄金顺序（`modifier_order_violation`）**：使用硬表面加权法线时，栈顺序保持 `Bevel → Smooth by Angle → Weighted Normal(keep_sharp=True)`；若颠倒把 `Weighted Normal` 放在 `Smooth by Angle` 上方，顶底平面法线会被拉偏。栈内有 `Data Transfer` 传递母面法线时，把它放在最底端并取消 `Smooth by Angle` 的置底钉选。对外导出 `FBX / GLB / USD` 前，把程序化法线和修改器求值固化进网格切分法线。
- **硬表面细分锁住 UV 边界（`subd_uv_smooth_all`）**：带硬边接缝、文字图案或烘焙法线贴图的细分网格，Subdivision 修改器的 `UV Smooth` 设为 `Keep Corners` 或 `Keep Boundaries`，防止默认 `All` 把硬边 UV 拉缩变形、在 EEVEE Next 光追阴影下暴出锯齿暗边。
- **反照率不被 AgX 宽容度骗过（`albedo_out_of_range`）**：Blender 默认 AgX 色彩变换很耐过曝，容易掩盖越界贴图。非金属材质（`Metallic < 0.5`）的 `Base Color` 控制在 `30–240 sRGB`（线性约 `0.013–0.88`），留住暗部环境光反射与亮部高光层次；法线贴图统一采用 OpenGL `+Y` 切线空间。
- **软信号结合视口核销**：阶段 0 报出的对称镜像 UV 重叠（`uv_high_overlap`）、眼球或内部机芯的合法包裹件（`enclosed_island`）、双面薄布料（`back_to_back`），在阶段 1 对照看图包核实合理后正常放行并在报告注明。
