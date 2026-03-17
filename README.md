# dynamical.org datasets example notebooks

Python jupyter notebooks demonstrating the use of dynamical.org datasets. Browse the dataset catalog at [dynamical.org/catalog](https://dynamical.org/catalog/).


# Getting started

We suggest using `uv` to install python and dependencies in a consistent, isolated way that won't impact any other python installations on your system.

1. Install uv: https://docs.astral.sh/uv/getting-started/installation/ (it's a one liner)
2. Run it
   * In your browser: In a terminal run `uv run --with jupyter jupyter lab` then follow the link jupyter will print to open these notebooks in your browser.
   * In your editor/IDE: In a terminal run `uv sync` then open this folder in your editor and when asked to select a python interpreter choose `.venv/bin/python` on macOS and Linux, or `.venv\Scripts\python` on Windows.

## Google Colab
Each notebook includes an install cell at the top. Run it to install dependencies. You can get a direct link to open any notebook in Colab from the examples section of each [dataset catalog entry](https://dynamical.org/catalog/).

## SageMaker Studio Lab
Clone this repository, then create a conda environment from the included `environment.yml`:
```
conda env create -f environment.yml
conda activate dynamical-notebooks
```
Then select the `dynamical-notebooks` kernel when opening a notebook.
