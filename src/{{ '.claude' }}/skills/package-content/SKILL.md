---
name: package-content
description: Add, remove or fix the content a Corporate Memory package ships - graphs, project exports, images - and keep cpa-manifest.json in step with it. Use when a file is added to or removed from the package directory, when a build fails on the manifest, when a graph should register as a vocabulary, or when the package licence has to be declared.
---

# The manifest is the contract

Everything this package ships is declared in `cpa-manifest.json`, and `cmemc`
enforces the match in **both** directions:

- a file in the package directory that the manifest does not list fails the
  build with `PackageContentError: Some paths are not described in the manifests
  file_spec list`
- an entry that names a file which is not there fails with `Some file_spec paths
  are not present in the package`

There are no ignored extras. A `.DS_Store`, a leftover export sidecar or a
dangling symlink each fail the build, and the second message is what a broken
symlink looks like.

So adding content is always two edits: the file, and its `files[]` entry.

## Where the field reference lives

Do not learn the manifest format from this file - it does not repeat it, on
purpose, so there is nothing here to drift out of date.

When the `cmem-marketplace` MCP server is connected, it is authoritative:

- `manifest_schema` - the full schema
- `manifest_check` - validates a manifest; note it reads the manifest only and
  cannot see the directory, so it never catches an undeclared file
- `manifest_example` - a worked example
- `package_build_guide` - the build process end to end

Otherwise read the *Package Manifest* section of the template's README:
<https://github.com/eccenca/cmem-package-template>.

## Rules the build enforces on paths

- at most **one** directory level below the package directory
- lowercase path segments of 2-30 characters
- only `.ttl`, `.zip` and `.png`, plus the three literal filenames `README.md`,
  `CHANGELOG.md` and `LICENSE`

## The three kinds of entry, in short

- **graph** - `file_type: graph` with a `graph_iri`, optional `import_into`
  (the graphs that import *this* one - note the direction) and
  `register_as_vocabulary`.
- **project** - `file_type: project` with a `project_id` and a `.zip` path. The
  repository keeps the export unzipped so it is diffable; the manifest keeps
  naming the `.zip` and the build re-zips on the fly. See the `build-projects`
  skill if this package has one.
- **image** - `file_type: image` with `file_role: icon` or `marketplace`.
- **text** - `file_type: text` with `file_role: readme`, `changelog` or
  `license`. This is the entry the three literal filenames need, and it is easy
  to miss because they arrive as symlinks the template already declared. If you
  remove and later restore a `LICENSE` - see the licence matrix below - this is
  the shape to restore it with, not a `file_role: license` invented at the top
  level.

`register_as_vocabulary` is decided by content, not preference. It requires the
graph to declare an `owl:Ontology` **at the graph IRI**, carrying
`vann:preferredNamespacePrefix` and `vann:preferredNamespaceUri`. Registering a
shape catalog or a plain dataset silently registers no prefix.

## Listing a graph is what makes the package own it

Ownership is what makes uninstall clean. A graph that only a workflow creates
appears in no manifest, so uninstalling the package leaves it behind as an
orphan that nothing will ever remove.

**Ship every graph the package writes to**, even one with no content of its
own - a file holding nothing but the graph's own description is enough. The
graph is then created at install time and removed again on uninstall.

Two consequences follow, and both belong in `DOCUMENTATION.md` because they
are things a user has to do:

- installing creates that graph **empty**, so the populating workflow has to
  be run afterwards;
- re-installing with `--replace` resets it to the shipped state, so the
  workflow has to be run again.

For the graph layout a package shipping instance data wants, and what the
pipeline then has to assert for itself, see
`references/graph-architecture.md`.

## Dependencies have to cover every namespace the graphs use

A `dependency_type: marketplace-package` entry is needed for **every**
namespace the shipped graphs mention - `w3c-rdf-vocab`, `w3c-rdfs-vocab`,
`w3c-owl-vocab`, `w3c-xsd-vocab`, `w3c-sh-vocab`, `w3c-skos-vocab`,
`foaf-vocab` and so on. Without them the terms do not resolve on a bare
instance, which is the deployment this package will eventually meet.

**Prefer bundling to depending when the dependency is your own.** A package
that bundles its vocabulary installs standalone; one that depends on a sibling
cannot be installed without it, and cannot be uninstalled while anything else
still needs it. Depend on what somebody else maintains, bundle what you do.

## Exporting from an instance leaves files you must not ship

`cmemc graph export` writes sidecars next to each `.ttl`:

| Sidecar | Holds | Goes into | Written |
| --- | --- | --- | --- |
| `<name>.ttl.graph` | the graph IRI | `graph_iri` | always |
| `<name>.ttl.imports` | the graphs that import this one | `import_into` | only with `--include-import-statements` |

Neither extension is legal in a manifest, so **transcribe them into the entry
and then delete them**. Skipping that step is the single most common way a build
fails after an export.

Export with `--include-import-statements`, or no `.imports` file appears at all
and the absence looks exactly like "this graph has no importers". Getting that
wrong costs nothing at build time and everything at install time: the graph
ships without being wired into the graph that imports it, and nothing complains.

Read the direction of `.imports` carefully: a file listing
`https://example.org/integration/` means the integration graph imports *this*
graph, not the other way round.

## Declaring the licence

`metadata.license` accepts open source and open data identifiers plus the
`LicenseRef-scancode-unknown` sentinel. **None of them means proprietary.** The
marketplace additionally rejects a package that ships a `LICENSE` file while the
identifier is unspecified:

| `metadata.license` | `LICENSE` file shipped | Result |
| --- | --- | --- |
| a real SPDX identifier | yes | valid - and declares the content open |
| `LicenseRef-scancode-unknown`, or omitted | yes | **invalid** - `License file found but no license specified.` |
| `LicenseRef-scancode-unknown` | no | valid |

An internal package therefore declares `LicenseRef-scancode-unknown` and ships
**no** `LICENSE` file in the package directory - the notice stays at the
repository root. The `README.md` and `CHANGELOG.md` symlinks are unaffected.

Nothing technical stops an internal package from being published. Whether the
pipeline has a publish job at all depends on how `marketplace` was answered when
this package was generated; where it exists, publication happens on
`main`/`master`, so staying on `develop` is the control.

## The version is never written by hand

`package_version` in the manifest stays `0.0.0`. The real version comes from
`git describe --tags --always --dirty`: a `vX.Y.Z` tag passes through, anything
else becomes `v0.0.0-<describe>`. **Releasing is tagging.** `task build` has a
precondition on `git describe`, so the repository needs at least one commit.

## Two READMEs, and why

`DOCUMENTATION.md` at the repository root is what the marketplace frontend
renders; the package directory's `README.md` is a symlink to it, because the
marketplace expects that exact name inside the package. The repository's own
`README.md` faces whoever maintains this repository and is **not** shipped.
Prose written for users of the package belongs in `DOCUMENTATION.md`.

**Do not open `DOCUMENTATION.md` with the package name or a restatement of its
description.** The frontend already prints `package_name` and
`package_description` directly above it, so an opening line that repeats either
costs the reader the first thing they look at. Open with what the package
actually gives them.

`CHANGELOG.md` and, where present, `LICENSE` are symlinked the same way. Edit
the originals at the root, never the links.

## Checking without a Corporate Memory instance

`task check` needs a live deployment: it installs and uninstalls the package.
Two things run offline and catch most of what it would.

`task check:offline` runs the checks in `bin/` over the package directory -
dangling references, query placeholders, every `shacl:path` against the
vocabulary, and the shipped queries. It needs no instance and no credentials,
and `task check` and `task import` both run it first. Two of the mistakes it
catches are invisible until after an install, and one of them then reports
success.

A build into a temporary directory catches every manifest and content problem:

```bash
cmemc package build <package_dir> --output-dir /tmp/pkg-check --version v0.0.0-test --replace
```

**A clean build is not a validation pass.** `package build` checks the manifest
against the directory and ignores RDF syntax errors entirely - a `.ttl` that no
parser accepts builds happily and fails at install. `task check:offline` parses
every graph, so running it covers that gap too.
