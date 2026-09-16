# Navigation

## `shui:managedClasses` decides what end users see

The property sits on the **graph** resource and says which classes the Explore
UI offers for that graph. It is curated, not derived, and it lists **root
classes only**:

```turtle
<https://isms.example.dev/> a void:Dataset ;
  shui:managedClasses ismo:Agent, ismo:Asset, sfso:FileSystemResource .
```

Never the subclasses. `ismo:Agent` stands for Person, Supplier and
BusinessUnit; `ismo:Asset` stands for the data, physical and software assets.

**Introducing a superclass therefore means adding it to this list and removing
the classes that just became its subclasses.** New subclasses are never added. A
root may be left out deliberately if end users have no business browsing it.

Each graph declares the kinds of resource it manages: a data graph names its
domain classes, a vocabulary graph names `owl:Class` and the property types, a
shape catalog names the `shacl:`/`shui:` shape types.

## Why root classes only

The navigation is a tree whose top-level entries are exactly the managed
classes. Each expands to its subclasses, and clicking any class - managed or not
- lists the resources of that class **together with those of all its
subclasses**. So a root class is the "everything below this" entry point, which
is what makes listing only roots the right call.

## Navigation lists are a different decision

`shui:navigationListQuery` sits on a **node shape** and defines the columns
shown when that class is listed. A class does not have to be managed to carry
one: navigation lists belong on whichever classes have distinct column sets, and
subclasses of a managed root routinely have their own.

## Related properties

- `shui:denyNewResources` - the UI lists the class but offers no create button
- `shui:usedClassForResourceCreation` - which concrete class a create action
  instantiates
- `shui:versioningGraph` - points a data graph at its `shui:VersioningGraph` of
  change records. That graph is a log written by the platform; never hand-edit
  it, and expect it to grow on every export.
