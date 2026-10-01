# Depictions

Give every class a `foaf:depiction`: an inline `data:image/svg+xml;base64` SVG
on a `viewBox="0 0 24 24"`.

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

**Hue carries the family.** Each top-level class owns one hue, and hues are
kept at least 60° apart on the wheel so no two top-level classes read as
related.

A subclass takes a **tone of its superclass's hue** - a lightness step,
optionally with a hue nudge of up to ±18° - never a hue of its own, because
sharing a hue is what tells the user the two classes belong together.
Conversely, a subclass tone must not drift into a neighbouring family's band.

Put the abstract superclass at the **mid** tone and the subclasses one step
darker and one step lighter. Two subclasses both darker than the parent do not
separate - they are indistinguishable at the size a form renders them.

A neutral (`currentColor`) is a good slot for a root entity, because no family
can collide with it.

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
