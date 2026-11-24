# 行业标准与项目证据来源

本审核体系融合了主流商业三维资产平台技术标准、影视仿真工业规范以及本项目实测结论。

## 对标的外部商业与工业标准

- **TurboSquid CheckMate Pro v2 & StemCell v2**：真实世界物理尺寸、世界原点居中与变换清零、单一主层级容器、零孤立点与共面重叠面、曲面上清零 ≥6 边高阶极点、微小紧固件豁免细分循环、非金属 PBR 反照率物理范围（避免纯黑纯白）、2 的幂次贴图与 UV 棋盘格展示要求。
- **Khronos 3D Commerce Asset Creation Guidelines v1.0 / v2.0**：米制 `1 unit = 1 meter`、轮廓圆滑度优先与不可见内腔精简、同材质统一纹素密度（主视觉面可重点分配）、自然工艺分件缝藏 UV 接缝、4–8 px 岛边距防 Mipmap 渗色、Metallic-Roughness 标准通道与 Clearcoat 等扩展兼容。
- **Superhive（原 Blender Market）& BlenderKit 官方审核规范**：当前正式版 `.blend` 开箱即用、正面朝 `-Y` 轴、清零 `Cube.001` / `Material.004` 默认命名、清理孤立未使用数据块、预标 Asset Browser 资产与 Catalog、贴图打包或相对路径零断链、兼顾 Cycles 与 EEVEE 实时表现。
- **Epic Games Fab & Unity Asset Store + AAA 游戏美术外包 QA 清单**：从大形剪影 → 法线着色 → 拓扑面数预算 → UV 布局与光照图通道 → 纹素密度与引擎零报错导入的分级检验链。
- **Blender Studio 开放电影管线 & Pixar OpenSubdiv / NVIDIA SimReady USD**：单一根集合（内分 `GEO_` / `RIG_` / `COLL_`）支撑无损 Library Override、OpenSubdiv 极限曲面下核验折痕与 UV 边界、视觉网格与简化碰撞体分离、关节枢轴对准真实运动轴心。

## 项目内部配套规范与实证

- **资产管理规范**：`<PROJECT_ROOT>/docs/asset-management/STANDARD.md`
- **基础几何体检内核**：`tools/blenderctl/mesh_qa.py`（提供 29 项几何、BVH 空间相交、UV 重叠与骨骼权重基础检测）
- **方法论与商业审核访谈决议**：`<PROJECT_ROOT>/docs/proposals/methodology-agents-restructure-interview-20261124.md`
- **Blender 5.x 硬表面栈序、折痕与 SubD UV 实证**：`<PROJECT_ROOT>/tutorial-library/hard-surface-modifiers/专题_硬表面卡线倒角加权法线与布尔清理工作流_5.2.1实证.md` · `<PROJECT_ROOT>/tutorial-library/hard-surface-topology/COMPLEX-CURVED-COMBINED-CASES.md`
- **早期双轨评估参考（BlenderWorld MIT 协议研究归档）**：`work/audit/<batch>/`
