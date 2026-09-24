<!-- markdownlint-disable MD012 MD013 MD024 MD033 -->
# Corporate Memory Package Template

[![workflow][build-shield-main]][github-actions]
[![workflow][build-shield-develop]][github-actions]
[![version][version-shield]][changelog]
[![copier][copier-shield]][copier]
[![eccenca Corporate Memory][cmem-shield]][cmem]

A [Copier](https://copier.readthedocs.io/) template for creating [eccenca Corporate Memory (Marketplace) packages](https://go.eccenca.com/feature/marketplace-packages).

## Package Types

`package_type` is the first question the template asks, and it is more than a
label: it decides what the generated manifest declares, which further questions
you are asked, and which authoring skills the package receives.

### Vocabulary Package (`vocabulary`)

A vocabulary package ships a single RDFS/OWL ontology: the classes, properties
and annotations of one schema. Keeping it on its own is the point of this type -
other packages can then reuse exactly the ontology they need, instead of pulling
in a bloated all-in-one project that happens to carry it as well.

Its graph entry is declared with `register_as_vocabulary: true`, so installing
the package does not only load the graph, it registers it in the vocabulary
catalog of Corporate Memory, where it becomes available to the tools that build
on it. This is also why the graph needs an `owl:Ontology` declaration carrying
VANN namespace metadata, see [Graphs](#graphs).

A marketplace vocabulary package cannot declare dependencies at all, so the
template does not ask for `python_dependencies` or `vocab_dependencies` - an
answer would have nowhere to go in the manifest.

### Project Package (`project`)

A project package is the generic type, and the one without limitations: it
ships everything else a Corporate Memory setup could need, and several of them
at once - DataIntegration project exports (`.zip`), data and shape graphs,
images. If a package is not exactly one ontology, it is a project package.

Its graph entries are generated with `register_as_vocabulary: false`, because
they carry data rather than schema - a package that also wants to register a
vocabulary can still set the flag on an individual file entry.

A project package may depend on Python packages (typically cmem plugins,
installed from PyPI) and on other marketplace packages. The template asks for
both and turns the answers into the `dependencies` entries of the manifest -
this is where a vocabulary package is named, rather than its ontology copied
into this one.

### What the answer changes

Everything else is the same for both types - the repository layout, the
`Taskfile.yaml`, the CI pipeline and the build, install and publish workflow:

| | vocabulary | project |
|---|---|---|
| generated graph entry | `register_as_vocabulary: true` | `register_as_vocabulary: false` |
| dependency questions | not asked | `python_dependencies`, `vocab_dependencies` |
| shipped [skills](#generated-structure) | `package-content`, `template-feedback` | the same, plus `build-projects` and `shapes` |

## Prerequisites

- Python 3.10+
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
| `package_type` | Type: vocabulary, project - see [Package Types](#package-types) | `vocabulary` |
| `package_id` | Package ID (lowercase, hyphens allowed) | - |
| `package_name` | Human-readable name | - |
| `package_description` | Short description | - |
| `python_dependencies` | Comma-separated Python package dependencies (project packages only) | - |
| `vocab_dependencies` | Comma-separated vocabulary/project dependencies (project packages only) | - |
| `marketplace` | Publish this package to the marketplace? A no leaves the publish job out of `.gitlab-ci.yml` | `true` |
| `github_page` | Link to GitHub page of the package | - |

## Generated Structure

```text
your-new-vocabulary-package/
├── .claude/            (agent support: rules, skills and a session end check)
├── .copier-answers.env
├── .copier-answers.yml
├── .gitignore
├── .gitlab-ci.yml
├── CHANGELOG.md
├── CONTRIBUTING.md
├── DOCUMENTATION.md   (shipped with the package, shown in the marketplace)
├── LICENSE
├── README.md          (for the package maintainer, not shipped)
├── Taskfile.yaml
└── {package_id}/
    ├── README.md      (link to ../DOCUMENTATION.md)
    ├── LICENSE        (link to ../LICENSE)
    ├── CHANGELOG.md   (link to ../CHANGELOG.md)
    ├── example.ttl
    └── cpa-manifest.json
```

`.claude/` holds what an agent working in the generated package reads: rules
describing which files the template owns, a `settings.json` that registers a
session end check and pre-approves `task build`, `task check` and `task clean`,
and skills covering package content, build projects, the shape catalog and how
to report a finding back to this template. A vocabulary package receives fewer
skills than a project package, because a build project and a shape catalog are
things it does not have.

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

## Package Manifest

Packages describe themselves in the `cpa-manifest.json` file.
Some metadata has been asked during the `copier` process.
Further metadata can be added to the `cpa-manifest.json` file:

### Metadata

- `comment:` A maintainer or publisher comment - not processed or shown to users. A simple string:

  ``` json
  "comment": "This is a comment left by the package maintainer.",
  ```

#### Agents

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

#### URLs

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

#### Tags

- `tags:` List of package tags. An array of strings:

  ``` json
  "tags": [
      "example",
      "template",
      "eccenca"
  ]
  ```

### Adding files

Add files (package contents) by copying or linking those into the package folder (or respective sub-folder) and referencing them in the files section.

#### Graphs

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

##### Note:
When using `register_as_vocabulary`, ensure that your graph contains an ontology declaration (`owl:Ontology`) and the corresponding VANN namespace metadata. In particular, the ontology resource should define both `vann:preferredNamespacePrefix` and `vann:preferredNamespaceUri`.

Example:

```turtle
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix vann: <http://purl.org/vocab/vann/> .

<http://www.example.org/file/> a owl:Ontology ;
    vann:preferredNamespacePrefix "ex" ;
    vann:preferredNamespaceUri "http://www.example.org/file/" .
```

The ontology resource carries the same IRI as the `graph_iri` of the file entry above. These annotations allow the vocabulary to be registered correctly and provide consumers with the preferred namespace URI and prefix associated with the ontology.

#### Projects

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

#### Icons and Images

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

#### Text files

`README.md`, `CHANGELOG.md` and `LICENSE` are declared as `text` entries with a
`file_role`. The generated package ships all three as symlinks to the files at
the repository root, already declared; this is the shape to use if one of them
has to be restored after being removed.

``` json
"files": [
    …
    {
        "file_path": "README.md",
        "file_type": "text",
        "file_role": "readme"
    },
    {
        "file_path": "CHANGELOG.md",
        "file_type": "text",
        "file_role": "changelog"
    },
    {
        "file_path": "LICENSE",
        "file_type": "text",
        "file_role": "license"
    },
    …
]
```

Note that a package declaring no license identifier, or the
`LicenseRef-scancode-unknown` sentinel, must **not** ship a `LICENSE` file at
all - the marketplace rejects that combination.

[version-shield]: https://img.shields.io/github/v/tag/eccenca/cmem-package-template?label=version&sort=semver
[changelog]: https://github.com/eccenca/cmem-package-template/blob/main/CHANGELOG.md
[github-actions]: https://github.com/eccenca/cmem-package-template/actions
[build-shield-main]: https://img.shields.io/github/actions/workflow/status/eccenca/cmem-package-template/check.yml?logo=github&branch=main&label=main
[build-shield-develop]: https://img.shields.io/github/actions/workflow/status/eccenca/cmem-package-template/check.yml?logo=github&branch=develop&label=develop
[copier]: https://copier.readthedocs.io/
[copier-shield]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-purple.json
[cmem]: https://documentation.eccenca.com
[cmem-shield]: https://img.shields.io/endpoint?url=https://dev.documentation.eccenca.com/badge.json
