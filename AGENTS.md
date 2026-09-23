# dynamical.org notebooks

This repo contains example Jupyter notebooks for the [dynamical.org](https://dynamical.org/catalog/) weather and climate dataset catalog. Each notebook demonstrates how to access and work with a specific dataset using the [`dynamical-catalog`](https://pypi.org/project/dynamical-catalog/) Python library, which loads datasets from S3-backed Icechunk stores as xarray datasets.

`README.md` is for notebook users, not developers. Keep developer and contributor instructions in this file.

## Organization

- **Root directory**: All notebooks live at the top level, following the pattern `<provider>-<dataset>-<variant>.ipynb`.
- **`.internal/`**: Internal tooling scripts (see below).
- **`pyproject.toml`**: Python dependencies managed with `uv`. Python 3.12+.
- **`environment.yml`**: Conda environment for SageMaker Studio Lab.

## Writing quickstart notebooks

A quickstart is the front door to one dataset: readers arrive from the catalog to decide whether
the dataset is useful to them. Assume they know weather data, xarray, and Zarr. Show what is
distinctive about this dataset; omit generic tooling lessons, storage internals, and chunking.

Keep the scope tight. Include only the most important examples, and vary the phenomena rather than
showing one event several ways. Early cells should read as dataset usage, not a matplotlib tutorial.

**Show, don't tell.** Prefer xarray's plotting and selection APIs so coordinates and metadata label
the result. Use xarray options such as `robust=True` and `center=False` before adding matplotlib
code. Keep stored units unless they are unfamiliar to most readers; set `long_name` and `units` on
derived fields so they label themselves. Keep cells small.

Avoid decorative markers, annotations, masks, and extra panels unless the result is unclear without
them. Keep the basemap features needed to interpret the data. Comment only context the code cannot
express, such as the event behind a timestamp.

**Prose.** Use two or three sentences per section to name the event and orient the reader, then let
the plot carry the finding. Do not repeat the catalog page or the `ds` repr, or compute values solely
to quote them in prose. Distinguish model fields from observations and make only claims supported by
the plot.

**Before writing**, read the closest notebooks: the same provider or model and the same dataset
shape (forecast or analysis, deterministic or ensemble, regional or global). Reuse their conventions
and domain knowledge, but choose different events. Research notable weather within the dataset's
verified coverage and verify dates and claims.

Most notebooks follow this shape: title and brief introduction (resolution, coverage, distinguishing
features, catalog link, and license where required); Colab install cell; open and display `ds`; a
structure note only if the repr is insufficient; short point-series and map examples; two or three
question-led sections; a `FuncAnimation` rendered with `HTML(anim.to_jshtml())`;
and a community challenge with genuinely open questions. Use one bullet per community challenge
question.

Use this structure for the introduction cell:

- Title: `Quickstart: <dataset name> - dynamical.org Icechunk Zarr`.
  For multiple datasets, combine their names unambiguously within the catalog, for example
  `Quickstart: UCSB CHC CHIRPS analysis, preliminary and final - dynamical.org Icechunk Zarr`.
- Documentation: `Dataset documentation: <full link>`. For multiple datasets, use one bullet per
  dataset with its name and full documentation link.
- Include a dataset license only when its terms are not solely CC BY 4.0.

Bound reads to fixed time slices and regions. Animations usually dominate file size, so shorten or
coarsen them as needed to keep the notebook under the repository limit.

## .internal/ tools

### `run_notebooks.py`

Executes notebooks to produce fresh outputs. Skips `pip install` cells during execution (restores them afterward).

**When to use**: After making logical code changes to a notebook. Only run the specific notebooks you changed — the underlying datasets update continuously, so re-running unchanged notebooks creates unnecessary output diffs.

**How to use**:
```
# Run specific notebooks (preferred):
uv run .internal/run_notebooks.py <notebook1.ipynb> [notebook2.ipynb ...]

# Run all notebooks (rarely needed):
uv run .internal/run_notebooks.py
```

## Notebook checks

Run and validate one notebook explicitly with:

```
uv run .internal/run_notebooks.py noaa-gfs-analysis.ipynb
uv run python tests/test_notebook_execution.py noaa-gfs-analysis.ipynb
```

CI divides the sorted notebook list into three deterministic shards:

```
uv run python .internal/test_notebooks.py --isolated --shard-index 0 --shard-count 3
uv run python .internal/test_notebooks.py --isolated --shard-index 1 --shard-count 3
uv run python .internal/test_notebooks.py --isolated --shard-index 2 --shard-count 3
```

Without `--isolated`, the coordinator runs the selected notebooks serially in the
repository environment and then validates their outputs. This default preserves
the convenient local workflow.

With `--isolated`, the runner creates an explicit temporary environment for each
dependency group. It contains only the packages named by the notebooks' install
line, their transitive dependencies, and the runner packages `nbclient`,
`nbformat`, and `ipykernel`; the execution tools also supply their dependencies (including IPython); it does not add other assumed Colab preinstalls. A missing
or ambiguous install line fails the check. Each group gets a fresh environment
and private Jupyter kernel, while uv caches downloaded packages rather than
persisting the environment. Within a shard, notebooks with the same install-line
dependencies are grouped and execute serially; the number of groups follows the
install lines rather than a fixed environment count. Validation receives the
same exact notebook paths after execution. CI runs the three shards in separate
jobs.

## Before committing

Always run `uv run .internal/run_notebooks.py` on any notebooks you changed before committing. Keep notebooks < 10MB.
