# Widgets

An aggregate - a count, a per-year breakdown, a line-up table - is not a
property of the resource, so it does not belong in a property shape. It belongs
in a widget.

## The chain

```text
NodeShape ──shui:WidgetIntegration_integrate──▶ shui:WidgetIntegration
                                                  (rdfs:label, rdfs:comment, shacl:order)
   ├─ shui:WidgetIntegration_group ──▶ shacl:PropertyGroup
   └─ shui:WidgetIntegration_widget ─▶ shui:TableReport
                                          (shui:TableReport_hideHeader / _hideFooter)
                                          └─ shui:TableReport_query ─▶ shui:SparqlQuery
```

```turtle
gigos:widget-visitors-per-year a shui:WidgetIntegration ;
  rdfs:label "Visitors per year"@en ;
  rdfs:comment "How many gigs this band played each year, and how many people were there."@en ;
  shacl:order 63 ;
  shui:WidgetIntegration_group gigos:group-stats ;
  shui:WidgetIntegration_widget gigos:report-visitors-per-year .
```

## Two things the schema will not tell you

**`shui:WidgetIntegration_group` is optional in the schema and mandatory in
practice.** A widget without it belongs to no group, and the UI renders it
*above* the form instead of inside it. Only ten of the sixteen widget
integrations on a stock deployment set it, so an example copied from the global
catalog is as likely to teach the bug as the fix.

**`shui:TableReport_hideHeader` hides the search box and the column titles
together.** There is no search-specific property - a table report carries only
`hideHeader`, `hideFooter` and `query` - so the two cannot be separated. A
report worth searching keeps its header and tolerates the search field; a
single-value report hides both header and footer, because there is nothing to
search and a column title would only repeat the widget's label.

## The query

The query takes `{{shuiMainResource}}`, the resource whose page is open, and may
be a plain `SELECT … GROUP BY` returning aggregate literals - which is why a
widget needs no invented property to hang on.

Other widget types exist - `shui:ComplexResourceViewerWidget`,
`shui:SimpleResourceViewerWidget`, `shui:ChartVisualization`,
`shui:WorkflowTrigger`, and `shui:viewResourcesWithWidget` to attach one. A
table report is the one to reach for first because it is the most predictable.
