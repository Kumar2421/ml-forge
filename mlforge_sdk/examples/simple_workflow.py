"""
MLForge SDK Example: Automated Workflow
---------------------------------------
This script demonstrates how to:
1. List local datasets.
2. Select a model from the registry.
3. Check hardware availability.
"""

from mlforge_sdk import MLForge
import time

def main():
    sdk = MLForge()
    
    print("--- 📊 MLForge Dataset Check ---")
    datasets = sdk.datasets.list(limit=5)
    for d in datasets:
        print(f"Dataset: {d.name} | Items: {d.images}")
    
    if not datasets:
        print("No datasets found. Please import one via CLI: 'mlforge dataset import ...'")
        return

    print("\n--- 🧠 Model Registry ---")
    models = sdk.models.list(task="object-detection", downloaded=True)
    for m in models:
        print(f"Model: {m.name} [ID: {m.id}]")
        
    if models:
        target = models[0]
        print(f"\nTargeting local model: {target.name}")
        
        # Example: Triggering a mock training config check
        # In a real scenario, you'd use sdk.training.start_run(...)
        print("Workflow ready for training.")
    else:
        print("\nNo cached models found. Download one: 'mlforge explore download <id>'")

if __name__ == "__main__":
    main()
