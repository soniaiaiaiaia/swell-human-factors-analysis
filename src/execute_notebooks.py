from __future__ import annotations

import os
from pathlib import Path

import nbformat
from IPython.core.interactiveshell import InteractiveShell
from IPython.utils.capture import capture_output


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_DIR = ROOT / "notebooks"


def main() -> None:
    if "SWELL_DATA_PATH" not in os.environ:
        default = ROOT / "data" / "raw" / "Behavioral-features - per minute.xlsx"
        if not default.exists():
            raise FileNotFoundError("Set SWELL_DATA_PATH before executing notebook 01.")

    original_cwd = Path.cwd()
    os.chdir(NOTEBOOK_DIR)
    try:
        for path in sorted(NOTEBOOK_DIR.glob("0*.ipynb")):
            notebook = nbformat.read(path, as_version=4)
            shell = InteractiveShell.instance()
            shell.reset(new_session=True)
            execution_count = 0
            for cell in notebook.cells:
                if cell.cell_type != "code":
                    continue
                execution_count += 1
                with capture_output(display=True) as captured:
                    result = shell.run_cell(cell.source, store_history=False)
                error = result.error_before_exec or result.error_in_exec
                if error is not None:
                    raise RuntimeError(f"{path.name}, cell {execution_count}: {error}")

                outputs = []
                if captured.stdout:
                    outputs.append(nbformat.v4.new_output("stream", name="stdout", text=captured.stdout))
                if captured.stderr:
                    outputs.append(nbformat.v4.new_output("stream", name="stderr", text=captured.stderr))
                for rich_output in captured.outputs:
                    outputs.append(
                        nbformat.v4.new_output(
                            "display_data",
                            data=rich_output.data,
                            metadata=rich_output.metadata,
                        )
                    )
                cell.execution_count = execution_count
                cell.outputs = outputs
            nbformat.write(notebook, path)
            print(f"Executed {path.name}")
    finally:
        os.chdir(original_cwd)


if __name__ == "__main__":
    main()
