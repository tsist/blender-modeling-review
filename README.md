# Blender Modeling Review & Commercial QA Scorecard

A commercial-grade quality review skill and headless Blender 5.3.0 read-only probe + 100-point scorecard generator (`commercial_qa_scorecard.py` + standalone `mesh_qa.py`), aligned with **StemCell**, **Superhive**, **BlenderKit**, **3D Commerce**, and **CheckMate Pro** standards.

## Delivery Levels & 5 Priority Gradients

- **L0 Draft Exploration**: Fast iteration on working copies.
- **L1 Shot-Only Prop**: G1 hard gates pass, total score ≥ 65.
- **L2 Commercial Standard (Default Release Line)**: G1 & G2 hard gates pass, total ≥ 80, every gradient ≥ 70%, independent read-only blind review.
- **L3 Flagship Hero Asset**: All hard gates pass, total ≥ 90, G2/G3/G4 ≥ 85%, independent read-only blind review.

Priority cascade (earlier gate failure rejects immediately):
1. **G1 Engineering Survival (15 pts)** — cold reopen, zero missing/absolute textures, zero negative scale, Non-Color data maps, cutter objects hidden from render.
2. **G2 Topology & Outliner Hygiene (25 pts)** — 1 m unit scale, `-Y` front, grounded origin & applied transforms, single root collection, zero default names (`Cube.001`) & orphan datablocks, clean quad SubD cage & pole discipline.
3. **G3 Silhouette & Reference Fidelity (25 pts)** — proportions, key landmarks, functional clearances.
4. **G4 Shading, Normals & Deformation (20 pts)** — reflection continuity, weighted/clean normals, clean silhouette bevels & animation deformation.
5. **G5 UV Texel Density, PBR Calibration & Dual-Engine Polish (15 pts)** — low-stretch UV, calibrated PBR albedo/roughness, Cycles & EEVEE Next parity (white-model deliveries rescale G1–G4 out of 85 to 100).

## Usage

```powershell
# 1. Run read-only probe inside headless Blender 5.3.0
blender -b --factory-startup -P scripts/commercial_qa_scorecard.py -- probe `
  --blend ./asset.blend --stage final --target-level L2 --output ./probe.json

# 2. Combine probe facts with independent visual scores into quality-scorecard.json + .md
python scripts/commercial_qa_scorecard.py score `
  --probe ./probe.json --scores ./visual-scores.json `
  --output ./quality-scorecard.json --markdown ./quality-scorecard.md
```

See [SKILL.md](SKILL.md), [references/commercial-gates.md](references/commercial-gates.md), and [references/scorecard-and-profiles.md](references/scorecard-and-profiles.md).
