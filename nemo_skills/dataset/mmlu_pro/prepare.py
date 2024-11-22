import argparse
import json
from pathlib import Path
from datasets import load_dataset

# ds = load_dataset("TIGER-Lab/MMLU-Pro")

def save_data(split):
    data_dir = Path(__file__).absolute().parent
    data_dir.mkdir(exist_ok=True)
    output_file = str(data_dir / f"{split}.jsonl")

    ds = load_dataset("TIGER-Lab/MMLU-Pro")

    data = []
    for entry in ds[split]:
        sample = {
            'question': entry['question'],
            'expected_answer': entry['answer'],
            'subject': entry['category'],
        }

        for i, option in enumerate(entry['options']):
            sample[chr(ord('A') + i)] = option

        data.append(sample)

    with open(output_file, "wt", encoding="utf-8") as fout:
        for entry in data:
            fout.write(json.dumps(entry) + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--split",
        default="all",
        choices=("valiadtion", "test")
    )
    args = parser.parse_args()

    if args.split == "all":
        for split in ["validation", "test"]:
            save_data(split)
    else:
        save_data(args.split)
