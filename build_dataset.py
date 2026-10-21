"""
CircuitSight - build a leakage-free PCB defect-crop dataset.

Run once from the project root (the folder that contains dataset/PCB_DATASET):

    python build_dataset.py
    python build_dataset.py --rebuild                      # redo crops
    python build_dataset.py --crop-mode fixed --fixed-size 96
    python build_dataset.py --test-boards 03,08 --val-boards 05

What it does
  1. Cuts one square crop per VOC box (same recipe as the notebooks).
  2. Reads the BASE BOARD id from the file name (01_spur_02.jpg -> board "01").
  3. Splits by base board (whole boards go to train / val / test). Board choice is
     automatic: it picks the boards whose class mix and size are closest to the
     global ones. Override with --test-boards / --val-boards.
  4. Audits the split (group leakage, near-duplicate crops across splits,
     bbox-size shortcut baseline) and writes everything to data/dataset_v2/.

Outputs (data/dataset_v2/)
  crops/<class>/*.png     the crops
  crops_manifest.csv      one row per crop, incl. board id and bbox metadata
  splits.csv              manifest + `split` column (train / val / test)  <- notebooks read this
  dataset_report.json     counts, chosen boards, audit numbers, split_id
"""
import argparse
import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


# ----------------------------------------------------------------------------- crops
def build_image_index(images_dir):
    index = {}
    for cls_dir in images_dir.iterdir():
        if not cls_dir.is_dir():
            continue
        for p in cls_dir.iterdir():
            if p.suffix.lower() in IMG_EXTS:
                index[(cls_dir.name.lower(), p.stem.lower())] = p
    return index


def crop_box(xmin, ymin, xmax, ymax, W, H, mode, scale, min_crop, fixed_size):
    """Square crop around the bbox, shifted (not squashed) to stay inside the image."""
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    if mode == "fixed":
        side = fixed_size
    else:
        side = max(max(xmax - xmin, ymax - ymin) * scale, min_crop)
    side = min(side, W, H)
    left = min(max(cx - side / 2, 0), W - side)
    top = min(max(cy - side / 2, 0), H - side)
    return int(left), int(top), int(left + side), int(top + side)


def base_board(stem):
    """'01_missing_hole_03' -> '01'"""
    m = re.match(r"(\d+)_", stem)
    return m.group(1) if m else None


def build_crops(a, root, out_dir, classes_cache):
    dataset = root / "dataset" / "PCB_DATASET"
    images_dir, annot_dir = dataset / "images", dataset / "Annotations"
    assert images_dir.exists() and annot_dir.exists(), f"Missing {images_dir} or {annot_dir}"

    classes = sorted(d.name.lower() for d in images_dir.iterdir() if d.is_dir())
    classes_cache.extend(classes)
    class_set = set(classes)
    index = build_image_index(images_dir)
    crops_dir = out_dir / "crops"
    if crops_dir.exists():
        shutil.rmtree(crops_dir)

    rows, n_img, n_missing, n_bad, n_noboard = [], 0, 0, 0, 0
    for xml_dir in sorted(p for p in annot_dir.iterdir() if p.is_dir()):
        folder_cls = xml_dir.name.lower()
        for xml_path in sorted(xml_dir.glob("*.xml")):
            root_xml = ET.parse(xml_path).getroot()
            img_path = index.get((folder_cls, xml_path.stem.lower()))
            if img_path is None:
                fname = Path(root_xml.findtext("filename", default="")).stem.lower()
                img_path = index.get((folder_cls, fname))
            if img_path is None:
                n_missing += 1
                continue
            board = base_board(img_path.stem)
            if board is None:
                n_noboard += 1
                continue

            with Image.open(img_path) as im:
                im = im.convert("RGB")
                W, H = im.size
                n_img += 1
                for k, obj in enumerate(root_xml.findall("object")):
                    bb = obj.find("bndbox")
                    if bb is None:
                        n_bad += 1
                        continue
                    xmin, ymin, xmax, ymax = (float(bb.findtext(t)) for t in ("xmin", "ymin", "xmax", "ymax"))
                    if xmax <= xmin or ymax <= ymin:
                        n_bad += 1
                        continue
                    name = (obj.findtext("name") or "").strip().lower()
                    label = name if name in class_set else folder_cls
                    if label not in class_set:
                        n_bad += 1
                        continue

                    box = crop_box(xmin, ymin, xmax, ymax, W, H,
                                   a.crop_mode, a.crop_scale, a.min_crop, a.fixed_size)
                    out_path = crops_dir / label / f"{img_path.stem}__{k:02d}.png"
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    im.crop(box).save(out_path)
                    rows.append({
                        "path": out_path.relative_to(root).as_posix(),
                        "label": label,
                        "source": f"{folder_cls}/{img_path.stem}",
                        "board": board,
                        "bbox_w": xmax - xmin, "bbox_h": ymax - ymin,
                        "crop_side": box[2] - box[0],
                    })
            if n_img % 100 == 0:
                print(f"  {n_img} board photos, {len(rows)} crops ...")

    print(f"Photos used: {n_img} | crops: {len(rows)} | XML without image: {n_missing} | "
          f"bad boxes: {n_bad} | files without a board number: {n_noboard}")
    assert n_noboard == 0, "Some file names have no leading board number - board split would be wrong."
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- split
def choose_boards(df, n_test, n_val, seed, classes):
    """Pick (test, val) boards whose class mix and size best match the global ones."""
    boards = sorted(df["board"].unique())
    n = len(df)
    glob = df["label"].value_counts(normalize=True).reindex(classes).fillna(0).values
    cnt = pd.crosstab(df["board"], df["label"]).reindex(index=boards, columns=classes, fill_value=0)
    nb = len(boards)

    def score(group, target_frac):
        c = cnt.loc[list(group)].sum(axis=0).values
        if (c == 0).any():
            return None                      # every class must exist in the split
        p = c / c.sum()
        return np.abs(p - glob).sum() + 2 * abs(c.sum() / n - target_frac)

    order = np.random.RandomState(seed).permutation(len(list(combinations(boards, n_test))))
    test_combos = list(combinations(boards, n_test))
    best, best_s = None, 1e9
    for ti in order:
        test = test_combos[ti]
        rest = [b for b in boards if b not in test]
        for val in combinations(rest, n_val):
            s_t, s_v = score(test, n_test / nb), score(val, n_val / nb)
            if s_t is None or s_v is None:
                continue
            if s_t + s_v < best_s:
                best, best_s = (list(test), list(val)), s_t + s_v
    assert best is not None, "No board combination gives every class in val and test."
    return best


# ----------------------------------------------------------------------------- audits
def dhash(path, size=16):
    with Image.open(path) as im:
        g = np.asarray(im.convert("L").resize((size + 1, size), Image.BILINEAR), dtype=np.float32)
    return (g[:, 1:] > g[:, :-1]).flatten().astype(np.float32)


def near_duplicate_audit(df, root):
    hashes = np.stack([dhash(root / p) for p in df["path"]])
    nbits = hashes.shape[1]
    split = df["split"].to_numpy()
    tr = np.where(split == "train")[0]
    out = {}
    for name in ("val", "test"):
        idx = np.where(split == name)[0]
        if len(idx) == 0 or len(tr) == 0:
            continue
        A, B = hashes[idx], hashes[tr]
        ham = nbits - (A @ B.T + (1 - A) @ (1 - B).T)
        mind = ham.min(axis=1)
        out[name] = {
            "n": int(len(idx)),
            "exact_match_in_train": int((mind == 0).sum()),
            "within_8_bits": int((mind <= 8).sum()),
            "median_min_distance_bits": float(np.median(mind)),
        }
    return out


def bbox_shortcut_audit(df):
    """Can the box size ALONE (no pixels) predict the class on unseen boards?"""
    from sklearn.ensemble import HistGradientBoostingClassifier
    feats = ["bbox_w", "bbox_h", "crop_side"]
    X = df[feats].assign(aspect=df["bbox_w"] / df["bbox_h"], area=df["bbox_w"] * df["bbox_h"])
    tr, te = df["split"] == "train", df["split"] == "test"
    clf = HistGradientBoostingClassifier(random_state=0).fit(X[tr], df.loc[tr, "label"])
    acc = float((clf.predict(X[te]) == df.loc[te, "label"]).mean())
    med = df.groupby("label")[["bbox_w", "bbox_h", "crop_side"]].median().round(1)
    return acc, med


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--out", default="data/dataset_v2")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--rebuild", action="store_true", help="re-cut crops even if a manifest exists")
    ap.add_argument("--crop-mode", choices=["scaled", "fixed"], default="scaled",
                    help="scaled: side = 2.5 x box (old recipe). fixed: same window for every defect")
    ap.add_argument("--crop-scale", type=float, default=2.5)
    ap.add_argument("--min-crop", type=int, default=64)
    ap.add_argument("--fixed-size", type=int, default=96)
    ap.add_argument("--test-boards", default="", help="comma list, e.g. 03,08 (default: automatic)")
    ap.add_argument("--val-boards", default="", help="comma list, e.g. 05 (default: automatic)")
    ap.add_argument("--n-test-boards", type=int, default=2)
    ap.add_argument("--n-val-boards", type=int, default=1)
    ap.add_argument("--drop-near-dupes", type=int, default=-1, metavar="BITS",
                    help="remove val/test crops within BITS (of 256) of a train crop. Off by default")
    a = ap.parse_args()

    root = Path(a.project_root).resolve()
    out_dir = root / a.out
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_csv = out_dir / "crops_manifest.csv"

    classes = []
    rebuilt = not (manifest_csv.exists() and not a.rebuild)
    if not rebuilt:
        df = pd.read_csv(manifest_csv, dtype={"board": str})
        classes = sorted(df["label"].unique())
        print(f"Loaded cached manifest ({len(df)} crops). Use --rebuild to re-cut.")
    else:
        df = build_crops(a, root, out_dir, classes)
        df.to_csv(manifest_csv, index=False)
    classes = sorted(df["label"].unique())
    assert len(df) > 0, "No crops produced."

    boards = sorted(df["board"].unique())
    print(f"{len(boards)} base boards: {boards}")
    if len(boards) < a.n_test_boards + a.n_val_boards + 1:
        raise SystemExit("Not enough base boards for this split.")

    # ---- board-level split
    if a.test_boards or a.val_boards:
        test_b = [b.strip() for b in a.test_boards.split(",") if b.strip()]
        val_b = [b.strip() for b in a.val_boards.split(",") if b.strip()]
        unknown = set(test_b + val_b) - set(boards)
        assert not unknown, f"Unknown boards: {unknown}"
    else:
        test_b, val_b = choose_boards(df, a.n_test_boards, a.n_val_boards, a.seed, classes)
    train_b = [b for b in boards if b not in test_b + val_b]
    assert not (set(test_b) & set(val_b)) and train_b, "Bad board assignment."

    df["split"] = np.where(df["board"].isin(test_b), "test",
                           np.where(df["board"].isin(val_b), "val", "train"))
    for x, y in (("train", "val"), ("train", "test"), ("val", "test")):
        assert not (set(df.loc[df.split == x, "board"]) & set(df.loc[df.split == y, "board"])), \
            f"Board leakage between {x} and {y}"
        assert not (set(df.loc[df.split == x, "source"]) & set(df.loc[df.split == y, "source"])), \
            f"Photo leakage between {x} and {y}"

    # ---- audits
    print("\nChecking near-duplicate crops across splits ...")
    dup = near_duplicate_audit(df, root)
    if a.drop_near_dupes >= 0:
        hashes = np.stack([dhash(root / p) for p in df["path"]])
        tr = np.where(df["split"] == "train")[0]
        drop = []
        for name in ("val", "test"):
            idx = np.where(df["split"] == name)[0]
            ham = hashes.shape[1] - (hashes[idx] @ hashes[tr].T + (1 - hashes[idx]) @ (1 - hashes[tr]).T)
            drop += list(idx[ham.min(axis=1) <= a.drop_near_dupes])
        print(f"Dropping {len(drop)} val/test crops within {a.drop_near_dupes} bits of a train crop")
        df = df.drop(index=drop).reset_index(drop=True)
        dup = near_duplicate_audit(df, root)

    print("Checking bbox-size shortcut ...")
    shortcut_acc, bbox_med = bbox_shortcut_audit(df)

    # ---- write
    df.to_csv(out_dir / "splits.csv", index=False)
    split_id = hashlib.sha1((out_dir / "splits.csv").read_bytes()).hexdigest()[:8]
    counts = pd.crosstab(df["split"], df["label"]).reindex(["train", "val", "test"])
    boards_by = {"train": train_b, "val": val_b, "test": test_b}

    report = {
        "split_id": split_id,
        "crop_mode": a.crop_mode if rebuilt else "cached (see earlier run)",
        "n_crops": int(len(df)),
        "boards": boards_by,
        "class_counts": {s: counts.loc[s].to_dict() for s in counts.index},
        "near_duplicates_vs_train": dup,
        "bbox_only_test_accuracy": round(shortcut_acc, 4),
        "chance": round(1 / len(classes), 4),
    }
    (out_dir / "dataset_report.json").write_text(json.dumps(report, indent=2))

    print("\n================ DATASET REPORT ================")
    print(f"split_id : {split_id}")
    print(f"boards   : train={train_b} | val={val_b} | test={test_b}")
    print("\nCrops per split and class:\n", counts.assign(total=counts.sum(axis=1)))
    print("\nNear-duplicate audit (val/test crops vs train crops, 256-bit dHash):")
    for k, v in dup.items():
        print(f"  {k}: {v}")
    print(f"\nMedian box size per class (px):\n{bbox_med}")
    print(f"\nBox-size-only classifier, test accuracy: {shortcut_acc:.3f}  (chance {1/len(classes):.3f})")
    if shortcut_acc > 0.5:
        print("  !! Box size alone predicts the class well. Pixels are not needed for much of the score.\n"
              "     Re-run with:  python build_dataset.py --rebuild --crop-mode fixed")
    print(f"\nWrote {out_dir / 'splits.csv'}")


if __name__ == "__main__":
    main()
