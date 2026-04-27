#!/usr/bin/env python3
import json
import os
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.abspath(os.path.join(HERE, ".."))
MODULE_PATH = os.path.join(TASK_DIR, "resample-irregular-time-series-to-regular-grid-csv-csv.py")

def load_module(path):
    spec = importlib.util.spec_from_file_location("generated_task", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def main():
    params_path = os.path.join(HERE, "params.json")
    params = json.load(open(params_path, "r", encoding="utf-8"))

    input_path = os.path.join(HERE, os.path.basename("input_input_03_irregular.csv"))
    output_path = os.path.join(HERE, os.path.basename("output_output_03.csv"))

    mod = load_module(MODULE_PATH)
    mod.run(input_path, output_path, **params)
    print("Wrote:", output_path)

if __name__ == "__main__":
    main()
