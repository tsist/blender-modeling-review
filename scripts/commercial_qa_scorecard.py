"""Read-only Blender 5.x Commercial QA Probe & Task Quality Scorecard Builder.

Usage 1 — Run read-only commercial probe inside headless Blender 5.3.0:
  blender.exe -b --factory-startup -P commercial_qa_scorecard.py -- probe \
      --blend <path.blend> --stage final --target-level L2 --output <probe.json>

Usage 2 — Combine probe + visual assessment into unified 100-point scorecard:
  python.exe commercial_qa_scorecard.py score \
      --probe <probe.json> --scores <visual-scores.json> \
      --output <quality-scorecard.json> --markdown <quality-scorecard.md>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

SCORECARD_SCHEMA_VERSION = "1.0"
DEFAULT_FASTENER_DIAG_M = 0.015  # 15 mm bounding diagonal exempts tiny screws/rivets from strict SubD pole rules
PLANAR_DIST_TOL_M = 2e-4
PLANAR_NORMAL_DEG = 2.0
CURVED_POLE_NORMAL_DEG = 3.5

DEFAULT_NAME_RE = re.compile(
    r"^(Cube|Sphere|Icosphere|Cylinder|Cone|Torus|Plane|Circle|Grid|Monkey|Suzanne|"
    r"Material|Collection|Armature|BezierCurve|NurbsCurve|NurbsPath|Text|Empty|Light|Camera)"
    r"(\.\d{3})?$",
    re.IGNORECASE,
)

GRADIENT_MAX = {
    "G1_engineering": 15.0,
    "G2_structure_topology": 25.0,
    "G3_reference_fidelity": 25.0,
    "G4_shading_continuity": 20.0,
    "G5_delivery_polish": 15.0,
}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _linear_to_srgb_byte(c: float) -> int:
    c = max(0.0, min(1.0, float(c)))
    if c <= 0.0031308:
        s = 12.92 * c
    else:
        s = 1.055 * (c ** (1.0 / 2.4)) - 0.055
    return int(round(max(0.0, min(1.0, s)) * 255.0))


def _is_smooth_by_angle_modifier(mod: Any) -> bool:
    if getattr(mod, "type", "") != "NODES":
        return False
    ng = getattr(mod, "node_group", None)
    name = (getattr(ng, "name", "") or getattr(mod, "name", "")).lower()
    return "smooth by angle" in name or "按角度平滑" in name


def _run_blender_probe(args: argparse.Namespace) -> int:
    import bmesh
    import bpy
    from mathutils import Vector

    blend_path = Path(args.blend).resolve()
    if not blend_path.is_file():
        raise FileNotFoundError(f"Blend file not found: {blend_path}")

    source_sha = _sha256_file(blend_path)
    bpy.ops.wm.open_mainfile(filepath=str(blend_path), load_ui=False)

    # Load pre-computed qa-report.json from `blenderctl model inspect --qa-profile` if supplied,
    # otherwise run in-process mesh_qa with bounded spatial BVH budget for fast standalone probing.
    base_qa_summary: dict[str, Any] = {}
    base_hard_blockers: list[dict[str, Any]] = []
    base_review_signals: list[dict[str, Any]] = []
    qa_res: dict[str, Any] | None = None
    if args.qa_report:
        qa_res = json.loads(Path(args.qa_report).read_text(encoding="utf-8-sig"))
    else:
        here = Path(__file__).resolve().parent
        candidates = [here]
        for anc in here.parents:
            candidates.append(anc / "tools" / "blenderctl")
        mesh_qa_dir = next((d for d in candidates if (d / "mesh_qa.py").is_file()), here)
        if (mesh_qa_dir / "mesh_qa.py").is_file():
            if str(mesh_qa_dir) not in sys.path:
                sys.path.insert(0, str(mesh_qa_dir))
            import mesh_qa  # type: ignore

            qa_profile = "game" if args.export_game else ("render" if args.stage == "white" else "game")
            qa_res = mesh_qa.run(profile=qa_profile, max_tris=args.max_tris, include_hidden=False)

    if qa_res is not None:
        base_qa_summary = {
            "profile": qa_res.get("profile"),
            "status": qa_res.get("status"),
            "blocker_codes": sorted({b.get("code", "") for b in qa_res.get("hard_blockers", [])}),
            "signal_codes": sorted({s.get("code", "") for s in qa_res.get("review_signals", [])}),
            "counts": qa_res.get("counts", {}),
            "skipped": qa_res.get("skipped", []),
        }
        base_hard_blockers = list(qa_res.get("hard_blockers", []))
        base_review_signals = list(qa_res.get("review_signals", []))

    scene = bpy.context.scene
    view_layer = bpy.context.view_layer

    findings: dict[str, list[dict[str, Any]]] = {
        "unit_scale_mismatch": [],
        "absolute_texture_path": [],
        "cutter_render_visible": [],
        "modifier_level_mismatch": [],
        "default_datablock_name": [],
        "root_collection_check": [],
        "orphan_datablocks": [],
        "modifier_order_violation": [],
        "subd_uv_smooth_all": [],
        "curved_ngons": [],
        "planar_ngons": [],
        "curved_pole_ge6": [],
        "highpoly_relief_poles": [],
        "skipped_highpoly_topology_objects": [],
        "albedo_out_of_range": [],
    }

    # 1. Unit scale check (1 unit = 1.0 meter)
    unit_sys = scene.unit_settings.system
    scale_len = float(scene.unit_settings.scale_length)
    if unit_sys != "METRIC" or abs(scale_len - 1.0) > 1e-5:
        findings["unit_scale_mismatch"].append(
            {"scene": scene.name, "system": unit_sys, "scale_length": round(scale_len, 6)}
        )

    # 2. Root collection & orphan datablocks
    top_children = [c for c in scene.collection.children]
    HelperCollRe = re.compile(r"^(rig|wgt|light|cam|studio|turntable|ref|helper|cutter)", re.I)
    asset_top_colls = [c for c in top_children if not HelperCollRe.match(c.name)]
    loose_scene_meshes = [o.name for o in scene.collection.objects if o.type == "MESH" and not o.hide_viewport]
    if len(asset_top_colls) != 1 or loose_scene_meshes:
        findings["root_collection_check"].append(
            {
                "top_asset_collections": [c.name for c in asset_top_colls],
                "loose_scene_root_meshes": loose_scene_meshes[:10],
            }
        )

    orphan_meshes = [m.name for m in bpy.data.meshes if m.users == 0]
    orphan_mats = [m.name for m in bpy.data.materials if m.users == 0 and m.name != "Dots Stroke"]
    if orphan_meshes or orphan_mats:
        findings["orphan_datablocks"].append(
            {
                "orphan_mesh_count": len(orphan_meshes),
                "orphan_material_count": len(orphan_mats),
                "examples": (orphan_meshes + orphan_mats)[:10],
            }
        )

    # 3. Absolute unpacked texture paths
    for img in bpy.data.images:
        if img.source not in {"FILE", "SEQUENCE", "TILED"} or img.users == 0:
            continue
        if img.packed_file is not None:
            continue
        raw_fp = img.filepath or ""
        if raw_fp and not raw_fp.startswith("//"):
            findings["absolute_texture_path"].append({"image": img.name, "filepath": raw_fp})

    # 4. Inspect scene objects: cutters, default names, modifier stack, topology
    visible_meshes = []
    for obj in scene.objects:
        is_helper = obj.type in {"LIGHT", "CAMERA"} or obj.name.lower().startswith(("wgt_", "wgt-", "cutter_", "bool_"))
        if obj.type == "MESH":
            # Boolean cutter / wire helper render leak check
            looks_like_cutter = bool(obj.hide_viewport) or getattr(obj, "display_type", "TEXTURED") in {"WIRE", "BOUNDS"}
            if looks_like_cutter and not obj.hide_render:
                findings["cutter_render_visible"].append(
                    {
                        "object": obj.name,
                        "hide_viewport": bool(obj.hide_viewport),
                        "display_type": getattr(obj, "display_type", ""),
                        "hide_render": bool(obj.hide_render),
                    }
                )
            if not looks_like_cutter and obj.name in view_layer.objects and view_layer.objects[obj.name].visible_get():
                visible_meshes.append(obj)

        if not is_helper and obj.name in view_layer.objects and view_layer.objects[obj.name].visible_get():
            if DEFAULT_NAME_RE.match(obj.name):
                findings["default_datablock_name"].append({"kind": "Object", "name": obj.name})

    for coll in asset_top_colls:
        if DEFAULT_NAME_RE.match(coll.name):
            findings["default_datablock_name"].append({"kind": "Collection", "name": coll.name})

    checked_mats = set()
    for obj in visible_meshes:
        # Bounding box diagonal in world meters (for tiny fastener exemption)
        bbox_world = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        xs = [p.x for p in bbox_world]
        ys = [p.y for p in bbox_world]
        zs = [p.z for p in bbox_world]
        diag_m = math.sqrt((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2 + (max(zs) - min(zs)) ** 2)
        is_tiny_fastener = diag_m <= DEFAULT_FASTENER_DIAG_M

        mods = [m for m in obj.modifiers if m.show_viewport or m.show_render]
        has_subd = False
        has_deform = any(m.type in {"ARMATURE", "CURVE", "LATTICE", "SURFACE_DEFORM"} for m in mods)
        has_bevel_or_sharp = any(m.type == "BEVEL" for m in mods)

        idx_sba = -1
        idx_wn = -1
        idx_dt = -1
        idx_subd = -1
        idx_shrink = -1

        for idx, m in enumerate(mods):
            if m.type in {"SUBSURF", "MULTIRES"}:
                has_subd = True
                idx_subd = idx
                v_lvl = getattr(m, "levels", 0)
                r_lvl = getattr(m, "render_levels", 0)
                if v_lvl > r_lvl or (r_lvl - v_lvl) > 1:
                    findings["modifier_level_mismatch"].append(
                        {"object": obj.name, "modifier": m.name, "viewport_levels": v_lvl, "render_levels": r_lvl}
                    )
                uv_sm = getattr(m, "uv_smooth", "")
                if obj.data and len(obj.data.uv_layers) > 0 and has_bevel_or_sharp and uv_sm in {"SMOOTH_ALL", "ALL"}:
                    findings["subd_uv_smooth_all"].append(
                        {"object": obj.name, "modifier": m.name, "uv_smooth": uv_sm}
                    )
            elif _is_smooth_by_angle_modifier(m):
                idx_sba = idx
            elif m.type == "WEIGHTED_NORMAL":
                idx_wn = idx
                if not getattr(m, "keep_sharp", False) and (idx_sba >= 0 or has_bevel_or_sharp):
                    findings["modifier_order_violation"].append(
                        {"object": obj.name, "issue": "Weighted Normal keep_sharp=False"}
                    )
            elif m.type == "DATA_TRANSFER" and getattr(m, "use_loop_data", False):
                idx_dt = idx
            elif m.type == "SHRINKWRAP":
                idx_shrink = idx

        if idx_wn >= 0 and idx_sba >= 0 and idx_wn < idx_sba:
            findings["modifier_order_violation"].append(
                {"object": obj.name, "issue": "Weighted Normal placed above Smooth by Angle"}
            )
        if idx_wn >= 0 and idx_dt >= 0 and idx_wn > idx_dt:
            findings["modifier_order_violation"].append(
                {"object": obj.name, "issue": "Weighted Normal placed below Data Transfer custom normals"}
            )
        if idx_shrink >= 0 and idx_subd >= 0 and idx_shrink < idx_subd:
            findings["modifier_order_violation"].append(
                {"object": obj.name, "issue": "Shrinkwrap placed above Subdivision Surface"}
            )

        # Control cage topology check: separate planar N-gons vs curved N-gons, and curved >=6-edge poles
        me = obj.data
        if me is not None and len(me.polygons) > 150000:
            findings["skipped_highpoly_topology_objects"].append(
                {"object": obj.name, "polygons": len(me.polygons), "reason": "exceeds 150000 control-cage scan cap"}
            )
        elif me is not None:
            bm = bmesh.new()
            bm.from_mesh(me)
            bm.normal_update()

            curved_ngon_count = 0
            planar_ngon_count = 0
            for f in bm.faces:
                if len(f.verts) >= 5:
                    n = f.normal
                    if has_subd or has_deform or n.length < 1e-8:
                        curved_ngon_count += 1
                        continue
                    c0 = f.verts[0].co
                    max_dist = max(abs((v.co - c0).dot(n)) for v in f.verts[1:])
                    adj_curved = False
                    for e in f.edges:
                        if e.smooth and len(e.link_faces) == 2:
                            other = e.link_faces[0] if e.link_faces[1] == f else e.link_faces[1]
                            if other.normal.length > 1e-8:
                                dot = max(-1.0, min(1.0, n.dot(other.normal)))
                                if math.degrees(math.acos(dot)) > PLANAR_NORMAL_DEG:
                                    adj_curved = True
                                    break
                    if max_dist <= PLANAR_DIST_TOL_M and not adj_curved:
                        planar_ngon_count += 1
                    else:
                        curved_ngon_count += 1

            if curved_ngon_count > 0:
                findings["curved_ngons"].append({"object": obj.name, "count": curved_ngon_count})
            if planar_ngon_count > 0:
                findings["planar_ngons"].append({"object": obj.name, "count": planar_ngon_count})

            if not is_tiny_fastener:
                pole_ge6_count = 0
                for v in bm.verts:
                    if v.is_boundary or len(v.link_edges) < 6 or len(v.link_faces) < 2:
                        continue
                    if has_subd or has_deform:
                        f_normals = [lf.normal for lf in v.link_faces if lf.normal.length > 1e-8]
                        if len(f_normals) >= 2:
                            base_n = f_normals[0]
                            max_ang = max(
                                math.degrees(math.acos(max(-1.0, min(1.0, base_n.dot(fn)))))
                                for fn in f_normals[1:]
                            )
                            if max_ang > CURVED_POLE_NORMAL_DEG:
                                pole_ge6_count += 1
                    else:
                        smooth_curved = False
                        for e in v.link_edges:
                            if e.smooth and len(e.link_faces) == 2:
                                n0, n1 = e.link_faces[0].normal, e.link_faces[1].normal
                                if n0.length > 1e-8 and n1.length > 1e-8:
                                    ang = math.degrees(math.acos(max(-1.0, min(1.0, n0.dot(n1)))))
                                    if ang > CURVED_POLE_NORMAL_DEG:
                                        smooth_curved = True
                                        break
                        if smooth_curved:
                            pole_ge6_count += 1
                if pole_ge6_count > 0:
                    if not has_subd and not has_deform and len(me.polygons) > 15000:
                        findings["highpoly_relief_poles"].append({"object": obj.name, "count": pole_ge6_count})
                    else:
                        findings["curved_pole_ge6"].append({"object": obj.name, "count": pole_ge6_count})

            bm.free()

        # Material naming & PBR dielectric Base Color range check
        for slot in obj.material_slots:
            mat = slot.material
            if mat is None or mat.name in checked_mats:
                continue
            checked_mats.add(mat.name)
            if DEFAULT_NAME_RE.match(mat.name):
                findings["default_datablock_name"].append({"kind": "Material", "name": mat.name})
            if args.stage != "white" and mat.node_tree is not None:
                for node in mat.node_tree.nodes:
                    if node.type == "BSDF_PRINCIPLED":
                        met_sock = node.inputs.get("Metallic")
                        bc_sock = node.inputs.get("Base Color")
                        if met_sock is not None and bc_sock is not None:
                            if not met_sock.is_linked and float(met_sock.default_value) < 0.5 and not bc_sock.is_linked:
                                rgb = list(bc_sock.default_value)[:3]
                                srgb_vals = [_linear_to_srgb_byte(c) for c in rgb]
                                lum_srgb = max(srgb_vals)
                                if lum_srgb < 30 or lum_srgb > 240:
                                    findings["albedo_out_of_range"].append(
                                        {"material": mat.name, "srgb_rgb": srgb_vals, "rule": "dielectric 30..240 sRGB"}
                                    )

    # Classify G1 & G2 hard gates (always emit both lists so score() can grade L1 vs L2/L3 accurately)
    target_level = args.target_level.upper()
    g1_gate_failures: list[str] = []
    for b in base_hard_blockers:
        g1_gate_failures.append(f"mesh_qa:{b.get('code')}({b.get('count', 1)})")
    for code in ("cutter_render_visible", "absolute_texture_path", "modifier_level_mismatch"):
        if findings[code]:
            g1_gate_failures.append(f"{code}({len(findings[code])})")

    g2_gate_failures: list[str] = []
    for code in (
        "unit_scale_mismatch",
        "default_datablock_name",
        "root_collection_check",
        "orphan_datablocks",
        "curved_ngons",
        "curved_pole_ge6",
    ):
        if findings[code]:
            g2_gate_failures.append(f"{code}({len(findings[code])})")
    if args.export_game and findings["planar_ngons"]:
        g2_gate_failures.append(f"planar_ngons_in_game_export({len(findings['planar_ngons'])})")

    # Promote deterministic G2 mesh_qa signals to L2/L3 commercial gates
    g2_promoted_codes = {"unapplied_scale", "zfighting", "inside_out_islands", "degenerate_faces"}
    for sig in base_review_signals:
        sc = sig.get("code", "")
        if sc in g2_promoted_codes:
            g2_gate_failures.append(f"mesh_qa:{sc}({sig.get('count', 1)})")

    active_failures = list(g1_gate_failures) + (list(g2_gate_failures) if target_level in {"L2", "L3"} else [])

    report = {
        "schema_version": SCORECARD_SCHEMA_VERSION,
        "blend_file": str(blend_path),
        "blend_sha256": source_sha,
        "blender_version": bpy.app.version_string,
        "stage": args.stage,
        "target_level": target_level,
        "export_game": bool(args.export_game),
        "visible_mesh_count": len(visible_meshes),
        "hard_gates_passed": len(active_failures) == 0,
        "g1_gate_failures": g1_gate_failures,
        "g2_gate_failures": g2_gate_failures,
        "base_mesh_qa": base_qa_summary,
        "commercial_findings": findings,
    }

    out_path = Path(args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "hard_gates_passed": report["hard_gates_passed"], "output": str(out_path)}, ensure_ascii=False))
    return 0


def _score_and_validate(args: argparse.Namespace) -> int:
    probe = json.loads(Path(args.probe).read_text(encoding="utf-8-sig"))
    visual = json.loads(Path(args.scores).read_text(encoding="utf-8-sig"))

    stage = probe.get("stage", "final")
    target_level = (visual.get("target_level") or probe.get("target_level") or "L2").upper()
    reviewer_role = visual.get("reviewer_role", "self_check")

    g_in = visual.get("gradients", {})
    g_out: dict[str, dict[str, Any]] = {}
    earned_sum = 0.0
    applicable_max_sum = 0.0

    for g_key, g_max in GRADIENT_MAX.items():
        applicable = not (stage == "white" and g_key == "G5_delivery_polish")
        if g_key in g_in and "applicable" in g_in[g_key]:
            applicable = bool(g_in[g_key]["applicable"])
        if not applicable:
            g_out[g_key] = {"score": None, "max": g_max, "ratio": None, "applicable": False, "notes": "当前阶段不适用"}
            continue
        if g_key not in g_in or g_in[g_key].get("score") is None:
            raise ValueError(f"Missing required score for applicable gradient: {g_key}")
        raw_score = float(g_in[g_key]["score"])
        if raw_score < 0.0 or raw_score > g_max:
            raise ValueError(f"Score out of bounds for {g_key}: {raw_score} (allowed 0..{g_max})")
        ratio = raw_score / g_max
        g_out[g_key] = {
            "score": round(raw_score, 2),
            "max": g_max,
            "ratio": round(ratio, 4),
            "applicable": True,
            "notes": str(g_in[g_key].get("notes", "")).strip(),
        }
        earned_sum += raw_score
        applicable_max_sum += g_max

    if applicable_max_sum <= 0:
        raise ValueError("No applicable gradients to score.")

    total_100 = round((earned_sum / applicable_max_sum) * 100.0, 2)
    g1_failures: list[str] = list(probe.get("g1_gate_failures", []))
    g2_failures: list[str] = list(probe.get("g2_gate_failures", []))

    blocking: list[str] = list(g1_failures)
    if target_level in {"L2", "L3"}:
        blocking.extend(g2_failures)
    hard_gates_passed = len(blocking) == 0

    if target_level in {"L2", "L3"} and reviewer_role != "independent_readonly_subagent":
        blocking.append("reviewer_role_must_be_independent_readonly_subagent_for_L2_L3")

    min_ratio = min(v["ratio"] for v in g_out.values() if v["applicable"] and v["ratio"] is not None)
    core_ratios = [
        g_out[k]["ratio"]
        for k in ("G2_structure_topology", "G3_reference_fidelity", "G4_shading_continuity")
        if g_out[k]["applicable"] and g_out[k]["ratio"] is not None
    ]
    min_core_ratio = min(core_ratios) if core_ratios else 0.0

    if g1_failures:
        achieved = "BLOCKED"
    elif not g2_failures and total_100 >= 90.0 and min_ratio >= 0.70 and min_core_ratio >= 0.85:
        achieved = "L3"
    elif not g2_failures and total_100 >= 80.0 and min_ratio >= 0.70:
        achieved = "L2"
    elif total_100 >= 65.0:
        achieved = "L1"
    else:
        achieved = "L0"

    rank = {"BLOCKED": -1, "L0": 0, "L1": 1, "L2": 2, "L3": 3}
    passed = len(blocking) == 0 and rank.get(achieved, -1) >= rank.get(target_level, 2)

    scorecard = {
        "schema_version": SCORECARD_SCHEMA_VERSION,
        "task_id": visual.get("task_id", "unnamed-task"),
        "stage": stage,
        "target_level": target_level,
        "achieved_level": achieved,
        "passed": passed,
        "reviewer_role": reviewer_role,
        "source_blend": probe.get("blend_file"),
        "source_sha256": probe.get("blend_sha256"),
        "blender_version": probe.get("blender_version"),
        "hard_gates_passed": hard_gates_passed,
        "blocking_issues": blocking,
        "gradients": g_out,
        "earned_points": round(earned_sum, 2),
        "applicable_max_points": applicable_max_sum,
        "total_score_100": total_100,
        "evidence_images": visual.get("evidence_images", []),
        "findings": visual.get("findings", []),
    }

    out_json = Path(args.output).resolve()
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.markdown:
        md_lines = [
            f"# 质量成绩单 · {scorecard['task_id']}",
            "",
            f"- **结论**：{'PASS（放行）' if passed else 'BLOCKED / 需返修'} ｜ 目标等级 `{target_level}` → 实达等级 **`{achieved}`** ｜ 折算总分 **`{total_100} / 100`**",
            f"- **审核角色**：`{reviewer_role}` ｜ **阶段**：`{stage}`",
            f"- **被审文件**：`{scorecard['source_blend']}`（SHA256 `{str(scorecard['source_sha256'])[:16]}...`）",
            "",
            "## 五级梯度得分",
            "",
            "| 梯度 | 得分 | 满分 | 得分率 | 观察依据 |",
            "|---|---|---|---|---|",
        ]
        labels = {
            "G1_engineering": "G1 工程生死门",
            "G2_structure_topology": "G2 拓扑四边面与大纲卫生",
            "G3_reference_fidelity": "G3 大形比例与参考还原",
            "G4_shading_continuity": "G4 光影法线与运动变形",
            "G5_delivery_polish": "G5 UV/PBR 与双引擎品相",
        }
        for k, row in g_out.items():
            if row["applicable"]:
                pct = f"{row['ratio'] * 100:.1f}%"
                md_lines.append(f"| {labels[k]} | {row['score']} | {row['max']} | {pct} | {row['notes']} |")
            else:
                md_lines.append(f"| {labels[k]} | - | {row['max']} | 不适用 | {row['notes']} |")

        if blocking:
            md_lines.extend(["", "## 阻断问题（先修清再复审）", ""])
            for item in blocking:
                md_lines.append(f"- `{item}`")

        if scorecard["findings"]:
            md_lines.extend(["", "## 具体问题与改进建议", ""])
            for f in scorecard["findings"]:
                md_lines.append(
                    f"- **[{f.get('severity', 'info')}] {f.get('gradient', '')} `{f.get('object', '')}`**："
                    f"{f.get('observation', '')} → 建议：{f.get('fix', '')}"
                )

        Path(args.markdown).resolve().write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "passed": passed,
                "target_level": target_level,
                "achieved_level": achieved,
                "total_score_100": total_100,
                "output": str(out_json),
            },
            ensure_ascii=False,
        )
    )
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1 :]

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)

    p_probe = sub.add_parser("probe", help="Run read-only Blender 5.x commercial QA probe")
    p_probe.add_argument("--blend", required=True)
    p_probe.add_argument("--stage", choices=["white", "final"], default="final")
    p_probe.add_argument("--target-level", choices=["L0", "L1", "L2", "L3"], default="L2")
    p_probe.add_argument("--export-game", action="store_true")
    p_probe.add_argument("--qa-report", help="Optional pre-computed qa-report.json from blenderctl model inspect")
    p_probe.add_argument("--max-tris", type=int, default=50000, help="Spatial BVH cap when running standalone mesh_qa")
    p_probe.add_argument("--output", required=True)

    p_score = sub.add_parser("score", help="Combine probe + visual review into 100-point scorecard")
    p_score.add_argument("--probe", required=True)
    p_score.add_argument("--scores", required=True)
    p_score.add_argument("--output", required=True)
    p_score.add_argument("--markdown")

    args = parser.parse_args(argv)
    if args.mode == "probe":
        return _run_blender_probe(args)
    return _score_and_validate(args)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
