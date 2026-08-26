# Workflow Visualization

Use this reference when someone provides a Mermaid flowchart for a Clay production
workflow and asks to visualize it in the current conversation. The diagram is an
input contract, not evidence that the depicted controls are implemented or tested.

## Output contract

- Use the host's native in-conversation visualization capability when available.
  Follow that capability's own file, rendering, accessibility, and response
  contract before creating the visual.
- Produce the visual in the current conversation. Do not create a website, app,
  slide, image, or repository artifact unless the user separately asks for one.
- Do not answer an explicit visualization request by merely echoing or restyling the
  Mermaid source. If the host cannot render an in-conversation visual, say so and
  return faithful Mermaid as the fallback.
- Keep the first view useful without interaction. Interaction may reveal detail or
  focus a stage, but it must not hide nodes or branches required to understand the
  governed path.

## Fidelity contract

Parse and preserve every meaningful element from the supplied Mermaid:

- flow direction;
- subgraph names, order, and stage boundaries;
- node identifiers, display labels, and shapes;
- directed edges and their labels;
- shared destinations and converging paths;
- success, hold, suppression, review, failure, and paused terminal outcomes;
- class assignments and the semantic categories their styles encode.

Translate Mermaid line breaks such as `<br/>` into readable visual labels. Keep
exact business values intact, including field names, thresholds, time windows,
campaign IDs, sequence length, and destination names. Never infer a missing edge,
rename a gate to make it sound implemented, or collapse multiple stop outcomes into
one generic failure when the source distinguishes them.

Before responding, compare the rendered model with the Mermaid and account for each
node and labeled edge. A polished visual with a missing fail-closed branch is wrong.

## Default composition

For a top-to-bottom governed outbound flow, use one compact route map:

- stages read in source order;
- gates look different from ordinary process steps;
- the main eligible path remains visually continuous;
- negative branches leave the main path toward their actual hold, suppression, or
  review outcome;
- destination fan-out and reconciliation fan-in remain explicit;
- the final paused or no-send state is prominent but not presented as a success
  metric.

For a dense workflow, a stage control or node selection may focus the map and expose
the selected label in a compact detail area. All controls must be keyboard accessible,
and the complete route must still be available without hover. Do not invent counts,
scores, readiness badges, or operational status.

Respect the host theme and keep the visual legible on narrow conversation widths.
Pair color with shape and text so source, gate, process, AI-assisted, stop,
destination, and safety meanings do not depend on color alone.

## Evidence boundary

Label the result as a visualization of the supplied design when only Mermaid is
available. Preserve claims such as “verified,” “deliverable,” or “remains paused” as
diagram labels, but do not restate them as observed facts.

If graph configuration, validation results, runs, or destination readbacks are also
available, keep the three evidence layers separate:

1. the Mermaid says what is intended;
2. executable configuration shows what is enforced;
3. runs and independent readbacks show what happened.

A visualization request is read-only. It does not authorize paid enrichment,
publishing, trigger activation, canaries, backfills, or external writes.
