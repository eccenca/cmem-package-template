<!-- markdownlint-disable MD012 MD013 MD024 MD033 -->
# Corporate Memory Package Template

[![workflow][build-shield-main]][github-actions]
[![workflow][build-shield-develop]][github-actions]
[![version][version-shield]][changelog]
[![copier][copier-shield]][copier]
[![eccenca Corporate Memory][cmem-shield]][cmem]

A [Copier](https://copier.readthedocs.io/) template for creating [eccenca Corporate Memory (Marketplace) packages](https://go.eccenca.com/feature/marketplace-packages).

## Prerequisites

- Python 3.8+
- Copier >= 9.0.0: `pip install copier` or `uv tool install copier`

## Usage

Create a new package directory from this template:

``` sh
# create a new directory with the latest release of the template
copier copy gh:eccenca/cmem-package-template your-new-vocabulary-package
```

``` sh
# create a new directory with the latest develop snapshot of the template
copier copy -r develop gh:eccenca/cmem-package-template your-new-vocabulary-package
```

## Template Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `package_type` | Type: vocabulary, project | `vocabulary` |
| `package_id` | Package ID (lowercase, hyphens allowed) | - |
| `package_name` | Human-readable name | - |
| `package_description` | Short description | - |
| `python_dependencies` | Comma-separated Python package dependencies | - |
| `vocab_dependencies` | Comma-separated vocabulary/project dependencies | - |
| `github_page` | Link to GitHub page of the package | - |

## Generated Structure

```text
your-new-vocabulary-package/
├── .copier-answers.env
├── .copier-answers.yml
├── .gitignore
├── .gitlab-ci.yml
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── Taskfile.yaml
└── {package_id}/
    ├── README.md (link)
    ├── LICENSE (link)
    ├── CHANGELOG.md (link)
    ├── example.ttl (link)
    └── manifest.json
```

The default license we add is _Apache License 2.0 ([`Apache-2.0`](https://spdx.org/licenses/Apache-2.0.html))_, see <https://spdx.org/licenses/> if you need a different.

## Development Tasks

After generating the package, use [Task](https://taskfile.dev/) to run common operations:

``` bash
task              # List available tasks
task build        # Build package archive
task check        # Run test suite
task import       # Import package to Corporate Memory
task export       # Export package from Corporate Memory
task publish      # Publish to marketplace
```

## Package Metadata

Packages describe themselves in the `manifest.json` file.
Some metadata has been asked during the `copier copy` process.
Further metadata can be added to the `manifest.json` file:

- `comment:` A maintainer or publisher comment - not processed or shown to users. A simple string:

  ``` json
  "comment": "This is a comment left by the package maintainer.",
  ```

- `agents:` List of person and organizations. An array of agent objects,
  - valid values for `agent_type` are
    - `person` and
    - `organization`,
  - valid values for `agent_role` are
    - `publisher`,
    - `maintainer` or
    - `author`.

  ``` json
  "agents": [
      {
          "agent_type": "organization",
          "agent_role": "publisher",
          "agent_name": "eccenca GmbH",
          "agent_email": "info@eccenca.com",
          "agent_url": "https://eccenca.com"
      },
      {
          "agent_type": "person",
          "agent_role": "maintainer",
          "agent_name": "John Doe",
          "agent_email": "john.doe@example.com",
          "agent_url": "https://example.com"
      }
  ]
  ```

- `urls:` List of package URLs. An array of URL objects,
  - valid values for `url_role` are:
    - `homepage`,
    - `source`,
    - `documentation` and
    - `issues`.

  ``` json
  "urls": [
      {
          "url_ref": "https://documentation.eccenca.com",
          "url_role": "documentation"
      },
      {
          "url_ref": "https://eccenca.com",
          "url_role": "homepage"
      },
      {
          "url_ref": "https://github.com/eccenca/cmem-package-template",
          "url_role": "source"
      },
      {
          "url_ref": "https://github.com/eccenca/cmem-package-template/issues",
          "url_role": "issues"
    }
  ]
  ```

- `tags:` List of package tags. An array of strings:

  ``` json
  "tags": [
      "example",
      "template",
      "eccenca"
  ]
  ```

## Adding files

Add files (package contents) by copying or linking those into the package folder (or respective sub-folder) and referencing them in the files section.

### Graphs

The following adds a graph.
`register_as_vocabulary` and `import_into` are optional instructions.
We suggest to organize graphs in a respective sub-folder (here `graphs/`), but this is up to you:

``` json
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

The following adds a project.
We suggest to organize projects in a respective sub-folder (here `projects/`), but this is up to you:

``` json
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

### Icons and Images

The following adds an image and/or icon:

``` json
"files": [
    …
    {
        "file_path": "periodic-table.png",
        "file_type": "image",
        "file_role": "marketplace"
    },
    {
        "file_path": "icon.png",
        "file_type": "image",
        "file_role": "icon"
    },
    …
]
```

[version-shield]: https://img.shields.io/github/v/tag/eccenca/cmem-package-template?label=version&sort=semver
[changelog]: https://github.com/eccenca/cmem-package-template/blob/main/CHANGELOG.md
[github-actions]: https://github.com/eccenca/cmem-package-template/actions
[build-shield-main]: https://img.shields.io/github/actions/workflow/status/eccenca/cmem-package-template/check.yml?logo=github&branch=main&label=main
[build-shield-develop]: https://img.shields.io/github/actions/workflow/status/eccenca/cmem-package-template/check.yml?logo=github&branch=develop&label=develop
[copier]: https://copier.readthedocs.io/
[copier-shield]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-purple.json
[cmem]: https://documentation.eccenca.com
[cmem-shield]: https://img.shields.io/endpoint?url=https://dev.documentation.eccenca.com/badge.json
