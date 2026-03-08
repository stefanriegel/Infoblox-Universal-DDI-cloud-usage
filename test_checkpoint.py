#!/usr/bin/env python3
"""Test script for checkpoint functionality."""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from azure_discovery.discover import save_checkpoint, load_checkpoint


def test_checkpoint():
    """Test saving and loading checkpoint."""
    checkpoint_file = "test_checkpoint.json"

    # Mock args
    class MockArgs:
        def __init__(self):
            self.format = "txt"
            self.workers = 8
            self.subscription_workers = 4
            self.checkpoint_file = checkpoint_file

    args = MockArgs()

    # Mock data
    all_subs = ["sub1", "sub2", "sub3"]
    scanned_subs = ["sub1"]
    all_native_objects = [{"type": "vm", "name": "test"}]
    errors = ["sub2: timeout"]

    # Save
    save_checkpoint(checkpoint_file, args, all_subs, scanned_subs, all_native_objects, errors)
    print("Checkpoint saved.")

    # Load
    data = load_checkpoint(checkpoint_file)
    if data:
        print("Checkpoint loaded:")
        print(f"  Completed: {len(data['completed_subs'])}/{data['total_subs']}")
        print(f"  Objects: {len(data['all_native_objects'])}")
        print(f"  Errors: {len(data['errors'])}")
    else:
        print("Failed to load checkpoint.")

    # Cleanup
    if os.path.exists(checkpoint_file):
        os.remove(checkpoint_file)


if __name__ == "__main__":
    test_checkpoint()
