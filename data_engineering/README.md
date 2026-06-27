# Data Engineering Pipeline

This directory contains the core technical components of the Perspectiverse data pipeline.

## Structure
- `config/`: Configuration files (YAML, etc.) for the pipeline.
- `scripts/`: Orchestration scripts to run the extraction and transformation processes.
- `data_sources/`: Source-specific extraction logic.

## Workflow
1. **Extraction**: Retrieve raw data from various sources.
2. **Transformation**: Process and format data into clean Markdown.
3. **Validation**: Ensure data quality and consistency.
4. **Output**: Move processed files to `data_final/`.
