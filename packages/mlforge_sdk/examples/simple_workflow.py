"""
MLForge SDK — Full Training Lifecycle Example

Demonstrates the complete ML workflow in under 50 lines:
  1. Discover models from the global registry
  2. Check local datasets
  3. Launch a training run
  4. Stream live metrics
  5. Run inference on a test image

Requirements:
  pip install mlforge-sdk
  mlforge start   # start the local engine first
"""

import time
import base64
from pathlib import Path
from mlforge_sdk import MLForge


def main():
    forge = MLForge()  # connects to local engine at 127.0.0.1:8005

    # ── 1. Find a detection model ─────────────────────────────────────────────
    print("📦 Checking local models...")
    models = forge.models.list(task="object-detection", downloaded=True)
    if not models:
        print("No local models found. Download one:")
        print("  mlforge explore download yolov8-nano-detection")
        return

    model = models[0]
    print(f"   Using: {model.name} ({model.size_label})")

    # ── 2. Find a dataset ─────────────────────────────────────────────────────
    print("\n📊 Checking datasets...")
    datasets = forge.datasets.list()
    if not datasets:
        print("No datasets found. Import one:")
        print("  mlforge dataset import roboflow --workspace myorg --project myproject --version 1")
        return

    dataset = datasets[0]
    print(f"   Using: {dataset.name} ({dataset.images} images)")

    # ── 3. Start training ─────────────────────────────────────────────────────
    print("\n🚀 Starting training run...")
    run = forge.train.start(
        model_id=model.id,
        dataset_id=dataset.id,
        task="detection",
        params={
            "epochs": 50,
            "batchSize": 16,
            "imgSize": 640,
            "lr": 0.01,
            "optimizer": "AdamW",
            "device": "auto",
        }
    )

    run_id = run["run_id"]
    print(f"   Run #{run['run_number']} started (ID: {run_id})")
    print("   Watching metrics... (Ctrl+C to stop watching, training continues)\n")

    # ── 4. Stream live metrics ────────────────────────────────────────────────
    try:
        while True:
            runs = forge.train.list_runs()
            current = next((r for r in runs if r.id == run_id), None)
            if not current:
                break

            history = forge.train.get_history(run_id)
            if history:
                latest = history[-1]
                epoch = latest.get("epoch", 0)
                map50 = latest.get("mAP50", 0)
                loss = latest.get("box_loss", 0)
                print(f"   Epoch {epoch:3d}/{current.total_epochs} | "
                      f"box_loss: {loss:.4f} | mAP@50: {map50:.4f} | "
                      f"status: {current.status}")

            if current.status in ("completed", "failed", "cancelled"):
                break

            time.sleep(10)

    except KeyboardInterrupt:
        print("\n   Stopped watching. Training continues in background.")
        return

    print(f"\n✅ Training complete! Final loss: {current.final_loss:.4f}")

    # ── 5. Quick inference test ───────────────────────────────────────────────
    test_images = list(Path(".").glob("*.jpg")) + list(Path(".").glob("*.png"))
    if not test_images:
        print("\n💡 Add a .jpg image to this directory and re-run for inference test.")
        return

    print(f"\n🔍 Running inference on {test_images[0].name}...")
    with open(test_images[0], "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    result = forge.inference.run(
        model_id=model.id,
        image_base64=b64,
        yolo_config={"confidence": 0.25, "iou_threshold": 0.45, "max_detections": 300, "class_filter": []},
    )

    detections = result.get("detections", [])
    print(f"   {len(detections)} objects detected in {result.get('total_ms', 0):.1f}ms")
    for det in detections[:5]:  # show top 5
        conf = det.get("confidence", 0)
        cls = det.get("class_name", "unknown")
        print(f"   [{cls}] confidence: {conf:.0%}")


if __name__ == "__main__":
    main()
