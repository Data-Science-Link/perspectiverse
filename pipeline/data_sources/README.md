# Data Sources

This directory contains subdirectories for each data source integrated into the Perspectiverse pipeline.

## Structure
Each data source should have its own directory containing:
- `extract_{source}.py`: The main extraction script.
- `README.md`: Documentation specific to that data source.
- `raw/`: (Optional) Directory for raw source files (ignored by git).

## Adding a New Source
1. Create a new directory under `data_sources/`.
2. Implement the extraction logic in a Python script.
3. Add a `README.md` explaining the source and any prerequisites.
