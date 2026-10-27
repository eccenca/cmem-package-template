# Depictions

Give every class a `foaf:depiction`: an inline `data:image/svg+xml;base64` SVG
on a `viewBox="0 0 24 24"`.

Only a class the package owns gets one. For a class from a vocabulary the
package does not own, the icon goes on the node shape of a project package's
shape catalog - see its `shapes` skill.

## Drawing them

- **Classes are filled. Node shapes are stroked** (`fill="none" stroke="…"
  stroke-width="1.6"`, round caps and joins) with the same artwork, so a class
  and its node shape are recognisably the same icon at different weights.
- **A family shares one container and differs by an inner glyph**, not by
  unrelated artwork.
- In a **filled** icon an inner glyph must be **cut out**, which means drawing
  it with the **opposite winding** to the container. Same winding merges it
  invisibly into the fill. Draw the container clockwise (`M… h+ v+ h- z`) and
  the glyph counter-clockwise (`M… v+ h+ v- z`). A glyph with curves can be
  punched out with `fill-rule="evenodd"` instead, which is simpler than
  reversing it.
- Keep the set line-art, not solid blocks. A solid coloured square reads as a
  swatch at 16 px, not as an icon.
- **An icon is always seen alone**, next to a class name in a form or a list.
  Encodings that only work with two icons side by side - left-versus-right
  position, an `A → B` reading - do not survive. Read every element against
  the icon's own fixed parts.
- Three elements in a 24-unit viewBox are all too small to identify. Prefer a
  silhouette carrying the identity plus one badge carrying the association.

## Colour

**Colours come from a fixed palette** - for eccenca packages the layout colours
of the eccenca palette, defined in `@eccenca/gui-elements`
(`src/configuration/_palettes.scss`, five tones per hue) - so packages installed
side by side look like one product. Take the values from there rather than
copying them. The palette's semantic colours (success, info, warning, danger, a
separate group in the same file) are reserved for badges and marks, and a class
hue keeps at least 26° away from them: a class drawn in the warning colour reads
as a warning. The 26° is a convention, not a measurement: it is the gap between
the palette's yellow and its warning colour, the smallest that keeps the yellow
usable for a class. Choose a wider gap if the palette leaves room.

**Hue carries the family.** A family is an independent top-level class, a class
that is merely related included. Not counted as families:

- at most one **neutral central class** per package, drawn black (the palette's
  darkest grey) - never `currentColor`, which changes colour on mouse-over
- **dependents** - classes whose instances cannot exist without their owner
  (deleting the owner deletes them: a receipt line, a copy of a work). They take
  the owner's hue, with the reason in a `skos:editorialNote`. "Part of" decides;
  a mandatory reference alone does not make a dependent. A dependent of the
  neutral class keeps a hue of its own.
- a graph's root resource, which takes the family of what it describes

**Families are spaced 360°/n apart**, n being their number, each taking the
palette hue nearest its target. When the palette cannot reach that spacing, use
every free hue once before two families share one, pick the set with the largest
smallest gap, and never leave a free hue unused while two families sit less than
26° apart. Only when there are more families than free hues - after checking
honestly that each one really is independent - do two families share a hue,
split by tone, paired so that they are far apart in meaning and the glyph tells
them apart.

**Within a family, tones of the one hue**, never a hue of its own: sharing a hue
is what tells the user two classes belong together. Put an abstract superclass
at the mid tone and the subclasses one step darker and one lighter - two
subclasses both darker than the parent are indistinguishable at form size.
Every drawn tone reaches at least 3:1 contrast against white (WCAG, non-text); a
tone that fails takes the next darker one. A family with three or more drawn
classes takes a hue whose lightest needed tone still passes; when none is free,
the extra class shares a tone with its sibling and the glyph tells them apart.
No colours outside the palette.

## Always look at an icon before committing it

Render candidates to PNG and view them. Do not reason about SVG path data:
mistakes caught only by looking include glyphs invisible from the wrong
winding, and a three-bar glyph that merged into a solid blob when stroked.

```sh
rsvg-convert -w 88 -h 88 candidate.svg -o candidate.png     # design check
rsvg-convert -w 24 -h 24 candidate.svg -o candidate_sm.png  # how the form shows it
```

Compose a contact sheet with `<image>` elements to compare a candidate against
its neighbours.

**Do not judge from a magnified small render.** Scaling a 24 px PNG up -
especially with `image-rendering="pixelated"` - exaggerates aliasing and makes
thin strokes look broken, which leads to over-thickening. Corporate Memory
antialiases at natural size, where a heavy stroke on a small viewBox goes
blurry instead of crisp. Keep stroked shapes at **1.6** on a 24-unit viewBox
and **2** on a 32-unit one, and verify in the running UI rather than in a
blown-up PNG.

## Property icons

The Business Knowledge Editor draws a property's `foaf:depiction` on its box,
so a drawing of the model can say what each relation and attribute is about
instead of showing one built-in icon for all. *A reviewer reading a drawing of
a competency question sees "located in" and "email" at a glance.*

- **A relation shows its kind and its direction**: an arrow into a glyph -
  `part-of`, `located-in`, `supplied-by`, `categorised-as`, `made-by`,
  `member-of`, `owned-by`, `in-series`, `copy-of`, `seen-on`,
  `record-elsewhere`, `set-aside-for`, `preceded-by` - or `range`, the range
  class's own icon behind the arrow, for a relation named after the role its
  range plays (`hasSupplier`). It takes the range class's colour. A relation
  you do not map keeps Corporate Memory's built-in icon: a glyph that
  contradicts the name is worse than none.
- **An attribute shows its meaning and never an arrow** - `email`, `name`,
  `address`, `title`, `identifier`, `amount`, `quantity`, `due-date` - and
  takes its domain class's colour, so a class and its attributes read as one
  unit. Every attribute gets one: where you map none, the kind of its value
  stands in, read from its range - `text`, `number`, `count`, `date`, `time`,
  `year`, `yes-no`, `link`, `location`.
- Map them in `icons/property-icons.json` (property IRI to glyph name, under
  `relations` and `attributes`) and run `task icons`: `bin/property_icons.py`
  writes each icon into the property's block as one line ending in
  `# property-icons: <glyph>`, and `task check:offline` fails when one is
  missing, stale or not drawing only. A depiction you drew by hand on a
  property stays, and the property gets none from the script.
- The shared glyphs are in `bin/glyphs/` and come with template updates, so the
  same meaning looks the same in every package. Draw a glyph of your own domain
  (flow rate, failure mode) into `icons/glyphs/relations/` or
  `icons/glyphs/attributes/` - stroked line art on a 24-unit viewBox in
  `currentColor`, a relation's glyph within x 10-22, right of the arrow. Every
  glyph must be drawing only: a script, an event handler or a reference outside
  the SVG is refused, because the icon is shown inside Corporate Memory's pages.
- Only the package's own properties get icons, as only its own classes do.

