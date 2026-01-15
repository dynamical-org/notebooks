"""
This script generates versions of our example notebooks modified to open the icechunk copy of the dataset.
"""

import json
from pathlib import Path

NOTEBOOKS = [
    {
        "name": "noaa-gfs-forecast.ipynb",
        "icechunk_s3_uri": "s3://dynamical-noaa-gfs/noaa-gfs-forecast/v0.2.7.icechunk/",
    },
    {
        "name": "noaa-hrrr-forecast-48-hour.ipynb",
        "icechunk_s3_uri": "s3://dynamical-noaa-hrrr/noaa-hrrr-forecast-48-hour/v0.1.0.icechunk/",
    },
    {
        "name": "noaa-hrrr-analysis.ipynb",
        "icechunk_s3_uri": "s3://dynamical-noaa-hrrr/noaa-hrrr-analysis/v0.1.0.icechunk/",
    },
    {
        "name": "ecmwf-ifs-ens-forecast-15-day-0-25-degree.ipynb",
        "icechunk_s3_uri": "s3://dynamical-ecmwf-ifs-ens/ecmwf-ifs-ens-forecast-15-day-0-25-degree/v0.1.0.icechunk/",
    },
]

ICECHUNK_OPEN_TEMPLATE = """import icechunk
import xarray as xr

storage = icechunk.s3_storage(bucket="{bucket}", prefix="{path}", region="us-west-2", anonymous=True)
repo = icechunk.Repository.open(storage)
session = repo.readonly_session("main")
ds = xr.open_zarr(session.store, chunks=None)
ds"""


def parse_s3_uri(s3_uri):
    """Parse S3 URI to extract bucket and path."""
    # Remove s3:// prefix
    if s3_uri.startswith("s3://"):
        s3_uri = s3_uri[5:]

    parts = s3_uri.split("/", 1)
    bucket = parts[0]
    path = parts[1] if len(parts) > 1 else ""

    return bucket, path


def get_cell_source(cell):
    """Get the source code from a notebook cell."""
    if "source" in cell:
        if isinstance(cell["source"], list):
            return "".join(cell["source"])
        return cell["source"]
    return ""


def set_cell_source(cell, source):
    """Set the source code for a notebook cell."""
    cell["source"] = source.splitlines(keepends=True) if source else []


def process_notebook(notebook_path, bucket, path):
    """Process a notebook to create an icechunk version."""
    # Read the notebook
    with open(notebook_path, "r", encoding="utf-8") as f:
        notebook = json.load(f)

    pip_cell_found = False
    dataset_cell_found = False
    title_cell_found = False

    # Process each cell
    for cell in notebook.get("cells", []):
        cell_source = get_cell_source(cell)
        cell_type = cell.get("cell_type", "")

        # Find and modify the first markdown cell with Quickstart title
        if (
            not title_cell_found
            and cell_type == "markdown"
            and cell_source.startswith("# Quickstart:")
            and "- dynamical.org Zarr" in cell_source
        ):
            # Replace "- dynamical.org Zarr" with "- dynamical.org Icechunk Zarr"
            new_source = cell_source.replace(
                "- dynamical.org Zarr", "- dynamical.org Icechunk Zarr"
            )
            set_cell_source(cell, new_source)
            title_cell_found = True

        # Find and modify the first pip install cell
        if (
            not pip_cell_found
            and "%pip install" in cell_source
            and "requests aiohttp" in cell_source
        ):
            # Replace "requests aiohttp" with "icechunk"
            new_source = cell_source.replace("requests aiohttp", "icechunk")
            set_cell_source(cell, new_source)
            pip_cell_found = True

        # Find and modify the first dataset opening cell
        if not dataset_cell_found and "xr.open_zarr" in cell_source:
            # Replace with the icechunk template
            new_source = ICECHUNK_OPEN_TEMPLATE.format(bucket=bucket, path=path)
            set_cell_source(cell, new_source)
            dataset_cell_found = True

        # Stop if all modifications are done
        if pip_cell_found and dataset_cell_found and title_cell_found:
            break

    return notebook, pip_cell_found, dataset_cell_found, title_cell_found


def main():
    """Main function to process all notebooks."""
    # Get the directory containing this script
    script_dir = Path(__file__).parent.parent

    for notebook_info in NOTEBOOKS:
        notebook_name = notebook_info["name"]
        s3_uri = notebook_info["icechunk_s3_uri"]

        # Parse S3 URI
        bucket, path = parse_s3_uri(s3_uri)

        # Construct paths
        notebook_path = script_dir / notebook_name
        output_name = notebook_name.replace(".ipynb", "-icechunk.ipynb")
        output_path = script_dir / output_name

        if not notebook_path.exists():
            print(f"Warning: Notebook {notebook_name} not found, skipping...")
            continue

        print(f"Processing {notebook_name}...")

        # Process the notebook
        try:
            notebook, pip_found, dataset_found, title_found = process_notebook(
                notebook_path, bucket, path
            )

            if not title_found:
                print(
                    f"  Warning: Could not find Quickstart title markdown cell in {notebook_name}"
                )
            if not pip_found:
                print(
                    f"  Warning: Could not find pip install cell with 'requests aiohttp' in {notebook_name}"
                )
            if not dataset_found:
                print(
                    f"  Warning: Could not find dataset opening cell in {notebook_name}"
                )

            # Write the modified notebook
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(notebook, f, indent=1, ensure_ascii=False)

            print(f"  Created {output_name}")

        except Exception as e:
            print(f"  Error processing {notebook_name}: {e}")


if __name__ == "__main__":
    main()
