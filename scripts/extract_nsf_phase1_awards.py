#!/usr/bin/env python3
"""
Extract ALL NSF Phase I awards (every topic area) from the SBIR award_data.csv
and save the abstracts as a Grantentic training dataset.

Filter: Agency == 'National Science Foundation' AND Phase == 'Phase I'.
No topic-code restriction and no cap on the number of records — every NSF
Phase I award that has an abstract is included.
"""

import csv
import json
import sys
from pathlib import Path

# Output lands in the repo's training_data/ dir, derived from this script's
# location (scripts/ -> ../training_data), so it is independent of the working
# directory the script is launched from.
OUTPUT_DIR = Path(__file__).resolve().parent.parent / 'training_data'


def extract_nsf_phase1_awards(csv_file_path):
    """
    Filter the SBIR awards CSV for every NSF Phase I award across all topics.
    Returns a list of awards that have a non-empty abstract.
    """

    awards = []

    try:
        with open(csv_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Filter criteria: NSF, Phase I, all topic areas.
                if (row.get('Agency') == 'National Science Foundation' and
                        row.get('Phase') == 'Phase I'):

                    award = {
                        'company_name': row.get('Company', ''),
                        'award_title': row.get('Award Title', ''),
                        'award_year': row.get('Award Year', ''),
                        'award_amount': row.get('Award Amount', ''),
                        'topic_code': row.get('Topic Code', ''),
                        'abstract': row.get('Abstract', ''),
                    }

                    # Only include if abstract exists
                    if award['abstract'].strip():
                        awards.append(award)

        return awards

    except FileNotFoundError:
        print(f"Error: File not found at {csv_file_path}")
        print("\nDownload the CSV from:")
        print("https://data.www.sbir.gov/mod_awarddatapublic/award_data.csv")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)


def save_to_markdown(awards, output_file):
    """Save extracted awards to markdown for easy review"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# NSF Phase I Awards — All Topics (Training Dataset for Grantentic)\n\n")
        f.write(f"**Total awards extracted:** {len(awards)}\n\n")
        f.write("---\n\n")

        for i, award in enumerate(awards, 1):
            f.write(f"## Award {i}: {award['company_name']}\n\n")
            f.write(f"**Award Title:** {award['award_title']}\n\n")
            f.write(f"**Award Year:** {award['award_year']}\n\n")
            f.write(f"**Award Amount:** ${award['award_amount']}\n\n")
            f.write(f"**Topic Code:** {award['topic_code']}\n\n")
            f.write(f"**Abstract:**\n\n{award['abstract']}\n\n")
            f.write("---\n\n")

    print(f"[OK] Saved {len(awards)} awards to {output_file}")


def save_to_json(awards, output_file):
    """Save extracted awards to JSON for processing"""

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(awards, f, indent=2, ensure_ascii=False)

    print(f"[OK] Saved {len(awards)} awards to {output_file}")


def main():
    # Paths to check
    possible_paths = [
        Path.home() / 'Downloads' / 'award_data.csv',
        Path('/mnt/user-data/uploads') / 'award_data.csv',
        Path.cwd() / 'award_data.csv',
    ]

    csv_file = None
    for path in possible_paths:
        if path.exists():
            csv_file = path
            print(f"Found CSV at: {csv_file}")
            break

    if not csv_file:
        print("Could not find award_data.csv in expected locations:")
        for path in possible_paths:
            print(f"  - {path}")
        print("\nUsage: python3 extract_nsf_space_awards.py /path/to/award_data.csv")
        sys.exit(1)

    # Extract awards
    print("\nExtracting all NSF Phase I awards (all topics)...")
    awards = extract_nsf_phase1_awards(str(csv_file))

    if not awards:
        print("No NSF Phase I awards found in CSV")
        print("Check that file contains NSF awards and includes abstract column")
        sys.exit(1)

    print(f"[OK] Found {len(awards)} NSF Phase I awards with abstracts\n")

    # Save outputs to the repo's training_data/ directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_to_markdown(awards, OUTPUT_DIR / 'nsf_phase1_all_awards.md')
    save_to_json(awards, OUTPUT_DIR / 'nsf_phase1_all_awards.json')

    print("\nNext steps:")
    print("1. Review the .md file for abstract patterns")
    print("2. Compare to your Deep Space Dynamics rejection language")
    print("3. Identify key differences in successful vs rejected proposals")


if __name__ == '__main__':
    main()
