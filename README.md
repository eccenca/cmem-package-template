<!-- markdownlint-disable MD012 MD013 MD024 MD033 -->
# Corporate Memory Package Template

[![workflow][build-shield-main]][github-actions]
[![workflow][build-shield-develop]][github-actions]
[![version][version-shield]][changelog]
[![poetry][poetry-shield]][poetry-link]
[![ruff][ruff-shield]][ruff-link]
[![copier][copier-shield]][copier]
[![eccenca Corporate Memory][cmem-shield]][cmem]

A [Copier](https://copier.readthedocs.io/) template for creating eccenca Corporate Memory packages.

## Prerequisites

- Python 3.8+
- Copier >= 9.0.0: `pip install copier` or `uv tool install copier`

## Usage

Create a new package from this template:

```bash
copier copy /path/to/package-template my-new-package
```

Or from a git repository:

```bash
copier copy git@gitlab.eccenca.com:eccenca.market/packages/package-template.git my-new-package
```

## Template Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `package_id` | Package ID (lowercase, hyphens allowed) | - |
| `package_name` | Human-readable name | - |
| `package_description` | Short description | - |
| `package_type` | Type: vocabulary, project | `vocabulary` |
| `python_dependencies` | Comma-separated Python package dependencies | - |
| `vocab_dependencies` | Comma-separated vocabulary/project dependencies | - |
| `license` | License of the package | `mit` |

## Generated Structure

```text
my-new-package/
├── .gitignore
├── .gitlab-ci.yml
├── LICENSE.json
├── LICENSE.txt
├── Taskfile.yaml
└── {package_id}/
    └── manifest.json
```

## Development Tasks

After generating the package, use [Task](https://taskfile.dev/) to run common operations:

```bash
task              # List available tasks
task build        # Build package archive
task check        # Run test suite
task import       # Import package to Corporate Memory
task export       # Export package from Corporate Memory
task publish      # Publish to marketplace
```

## Adding files

Add files (package contents) by copying those into the package folder (or respective sub-folder) and referencing them in the files section.

### Graphs

Add the following structure to add a graph. `register_as_vocabulary` and `import_into` are optional instructions. We suggest to organize graphs in a respective sub-folder (here `graphs/`), but this is up to you:

```json
"files": [
    …
    {
        "file_type": "graph",
        "file_path": "graphs/file.ttl",
        "graph_iri": "http://www.example.org/file/",
        "register_as_vocabulary": true,
        "import_into": [
            "http://www.example.org/integration_graph/"
        ]
    },
    …
]
```

### Projects

Add the following structure to add a project. We suggest to organize projects in a respective sub-folder (here `projects/`), but this is up to you:

```json
"files": [
    …
    { 
        "file_type": "project", 
        "file_path": "projects/product-integration-demo.zip", 
        "project_id": "product-integration-demo" 
    },
    …
]
```
