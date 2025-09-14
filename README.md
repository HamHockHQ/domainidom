# domainidom

Domain and brand name ideation, availability research, and packaging.

## Quick start (Windows PowerShell)

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
```

Run API:

```powershell
uvicorn domainidom.api:app --reload
```

Run CLI:

```powershell
python -m domainidom.cli brainstorm --idea "AI travel planner for families" --tlds com io ai
```

Run tests:

```powershell
pytest -q
```
