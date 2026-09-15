# Robust Automatic Mapping — Detailed Approach 1 and 5

## Implementation Scope Clarification

V1 will implement Approaches 1 and 5 together as one deterministic extraction pipeline: Markdown supplies textual structure, while PDF coordinates confirm and recover visual relationships. They are complementary parts of the same extraction request, not alternative modes, and implementing only one would not meet the main accuracy goal.

Approach 2 will not be active in v1. Only a disabled extension point will be reserved for a future selective LLM fallback, so the automatic v1 flow makes no LLM calls and incurs no model cost.

## Non-Negotiable Correctness Contract

No technology can perfectly recover structure from every arbitrary PDF. PDFs often store text as individually positioned characters without real rows, columns, fields, or tables.

The reliable promise should therefore be:

- Never silently shift a value into the wrong field or table column.
- Never invent a missing label or value.
- Preserve explicit empty cells.
- Accept a relationship only when structural evidence is strong.
- Put uncertain content in Review with its original source context.
- Use no document-specific field names or layouts.

The plan will be saved as `docs/automatic-field-mapping-plan.md`.

## Approach 1 — Fields Without a Printed Separator

Consider a line such as “Invoice No. INV-90211”. There is no colon or equals sign showing where the label ends.

The mapper will use the following evidence in order.

### 1. Markdown formatting boundaries

LiteParse may preserve separate formatting:

- Bold label followed by normal value.
- A heading-like label followed by ordinary text.
- Separate inline spans.
- List term followed by list content.
- Multiple spaces preserved inside a preformatted block.

A formatting boundary provides a possible label/value boundary even when there is no colon.

This is accepted only when the left part looks like a compact label and the right part looks like content.

### 2. Markdown block boundaries

The label and value may be emitted as separate blocks:

- One short text block.
- One immediately following value block.
- No heading, blank section, table, or competing label between them.

This becomes a candidate relationship.

Approach 5 must confirm it when the relationship is not structurally obvious from Markdown alone.

### 3. Table or list boundaries

A separator does not need to be a visible colon.

Structural boundaries also include:

- Two different table cells.
- A definition-list term and its description.
- A bullet label and its nested content.
- Two aligned columns retained in Markdown.
- A Markdown heading followed by one compact value.

The structure itself separates the label and value.

### 4. Consistent neighbouring patterns

Several nearby lines may follow the same shape.

For example, each line may contain:

- A short text prefix.
- A noticeable gap.
- A code, number, or date suffix.

The mapper can compare neighbouring lines and identify a repeated boundary.

This pattern is supporting evidence. It is not sufficient when both sides are ordinary words and no clear boundary survives.

### 5. Generic text-shape evidence

When a line is still unsplit, the mapper can examine possible boundaries.

Useful signals include:

- The left side is short and mostly words.
- The right side resembles a date, identifier, quantity, code, amount, email, or other value-shaped text.
- The same split pattern appears on nearby lines.
- Only one boundary has strong evidence.

This does not use invoice-specific labels or a fixed dictionary.

It must not split purely because the final token happens to contain a number.

### 6. Coordinate confirmation

If the text appears visually as two separate areas, approach 5 confirms the boundary using horizontal position and spacing.

This is the strongest solution for separator-free fields.

### When the field must remain unresolved

A plain line such as “Customer United States” may have:

- No separator.
- No formatting difference.
- No reliable spacing.
- No separate PDF text blocks.
- Two ordinary textual phrases.

There is no universal deterministic way to prove whether the intended split is:

- Customer → United States
- Customer United → States
- Or no field at all

The system must not guess. It preserves the line under Review.

An optional LLM may later interpret it, but deterministic v1 must remain honest.

## Separator-Free Field Decision Flow

For each possible line:

1. Check for explicit punctuation separators.
2. Check Markdown formatting and block boundaries.
3. Check table, list, or column structure.
4. Check repeated neighbouring layout patterns.
5. Check whether one text split is uniquely supported.
6. Ask coordinate mapping to confirm the relationship.
7. Accept only when the evidence passes the confidence threshold.
8. Otherwise preserve the complete unsplit text under Review.

## Approach 1 — Other Field Edge Cases

| Situation | Handling |
| --- | --- |
| Label and value are separate styled spans | Use the style boundary and confirm with ordering or coordinates |
| Label is above the value | Require adjacency and coordinate alignment |
| Value is left of the label | Do not reverse-pair without clear table or coordinate evidence |
| Value is normal text rather than a number/code | Require formatting, block, table, or coordinate separation |
| Several separator-free pairs share one line | Require preserved spans or coordinate groups; otherwise Review |
| One label has a multi-line value | Join only continued blocks with matching indentation and no intervening label |
| Same label repeats | Keep separate ordered occurrences |
| Label is printed but value is blank | Record an explicitly empty field |
| Text is a title or company name without a label | Preserve as unlabeled content |
| OCR merges label and value | Attempt coordinate/text segmentation; otherwise Review |
| OCR splits one word into several blocks | Rejoin strongly overlapping same-line fragments before mapping |
| A field contains a URL, time, or ratio | Do not treat internal punctuation as a new label boundary |

## Tables — Correct Handling of Missing Cells

### First principle: never compress a row

Suppose a table has four columns and a row contains a value only in column three.

The internal row must remain:

- Column one: empty
- Column two: empty
- Column three: printed value
- Column four: empty

The value must never be moved left simply because earlier cells are empty.

### Neutral grid first

Every table is initially stored as a grid with fixed row and column positions.

Interpretation as document fields or repeated records happens only after the grid has been reconstructed.

The grid retains:

- Total row count
- Total column count
- Explicit empty positions
- Cell row and column indexes
- Row and column spans
- Original cell text
- Cell page and coordinates
- Confidence and provenance

### When Markdown preserves empty cells

Markdown pipes identify cell positions.

A row with consecutive pipes contains an explicit empty cell.

The parser will:

1. Count the table’s expected columns.
2. Retain empty strings between delimiters.
3. Pad missing trailing positions only at the end.
4. Never remove empty cells.
5. Never shift later values into earlier columns.

### When Markdown loses the empty position

Sometimes malformed Markdown contains fewer cells but does not reveal which position was lost.

Approach 1 alone cannot safely decide whether the missing cell was at the beginning, middle, or end.

In that case:

- Do not left-shift values.
- Retrieve the Docling cell indexes and coordinates.
- Let approach 5 align the cell to the correct column.
- If coordinate evidence is insufficient, preserve the row as uncertain.

### Printed blank versus printed marker

These cases remain different:

- An empty cell means no printed value was found in that position.
- A printed dash is the value “-”.
- “N/A” is the printed value “N/A”.
- “Not tested” is the printed value “Not tested”.
- A cell covered by a merged cell is marked as covered, not empty.
- An unreadable OCR cell is uncertain, not empty.

The mapper must not treat these states as equivalent.

### Values that wrap onto another line

A wrapped cell value stays in the same cell when:

- Its text lies inside the same Docling cell box.
- Or it remains inside the same column band and row region.
- It does not overlap the next row.
- No horizontal separator or large vertical gap intervenes.

Wrapped text is joined without moving it into the next row or column.

### Merged cells

Docling’s start/end row and column offsets must be retained instead of reducing every cell to its top-left value.

For a merged cell:

- Store the value once in the anchor position.
- Mark other covered positions as part of the span.
- Do not duplicate the value across every covered cell.
- Preserve the span in JSON.
- Leave covered positions blank in plain CSV export.

### Multi-row headers

Headers may use two or more rows.

The mapper will:

1. Retain all header rows.
2. Use Docling’s header and span information when reliable.
3. Combine parent and child headings only for display/export.
4. Preserve the original header structure in JSON.
5. Use neutral column names when a final leaf column has no reliable heading.

It will not treat the second header row as document data.

### Rows containing only one value

The value is assigned using its original cell index when available.

If only coordinates are available:

- Compare the value’s horizontal range against the table’s column bands.
- Assign it to the column with the strongest horizontal overlap.
- Retain all other cells as empty.
- Reject the assignment if two columns have similar overlap.

### Repeated tables across pages

Tables are merged only when:

- Their column count agrees.
- Header structure agrees.
- Column positions are compatible.
- The second table is a clear page continuation.

Repeated page headers are removed only when they match the established header structure.

Otherwise, they remain separate tables.

## Approach 5 — Exact Coordinate Reconstruction

### 1. Retain complete Docling provenance

The existing code currently reduces Docling tables into simplified rows and columns.

The revised pipeline must retain:

- Cell row and column offsets
- Cell spans
- Cell bounding boxes
- Table bounding boxes
- Text-block bounding boxes
- Page dimensions and rotation
- Page numbers
- Item types and reading order

Simplifying this data must happen only after mapping is complete.

### 2. Normalize every page

Coordinates are converted into one page-relative system after applying page rotation.

This prevents different page dimensions or orientations from changing the matching logic.

### 3. Reconstruct rows

Text blocks belong to the same row when:

- Their vertical ranges substantially overlap.
- Their vertical centres are close relative to local text height.
- No table, column, or section boundary separates them.

Row grouping uses relative measurements based on nearby text size—not fixed pixels.

### 4. Reconstruct columns

Column bands are inferred from all rows together, not from one row.

The mapper uses:

- Header-cell positions
- Docling column indexes
- Repeated left and right cell edges
- Horizontal clustering across many rows
- Table boundaries

Using the entire table prevents a sparse row from redefining its columns.

### 5. Assign cells without shifting

For each cell or text block:

1. Measure horizontal overlap with every established column band.
2. Prefer the column with the greatest overlap.
3. Require assignments to progress from left to right within the row.
4. Permit skipped columns.
5. Preserve skipped positions as empty.
6. Detect a span when one cell strongly overlaps several columns.
7. Mark ambiguous overlap for Review.

This left-to-right constraint prevents two cells from being placed in the same column and allows missing cells anywhere in the row.

### 6. Use global row alignment

The mapper evaluates the complete row rather than assigning each cell independently.

It selects the ordered assignment that best fits:

- Horizontal overlap
- Left-to-right order
- Known column indexes
- Cell spans
- Expected table width
- Neighbouring row alignment

This is essential for ragged rows and missing middle cells.

### 7. Separator-free label/value coordinates

For normal form fields outside tables:

- Group text into visual lines.
- Identify compact label candidates.
- Search within the same visual container.
- Prefer a value on the same row to the right.
- Otherwise consider a value directly below with matching alignment.
- Stop at another label, column, box, heading, or large whitespace gap.

The relationship becomes stronger when:

- Label and value are separate PDF blocks.
- Their vertical ranges overlap.
- The horizontal gap is consistent with neighbouring field rows.
- Similar rows use the same label/value alignment.
- Markdown ordering agrees.

### 8. Do not rely only on nearest distance

The nearest text is not always the correct value.

The coordinate score must consider:

- Same row versus different row
- Direction from the label
- Shared table cell, row, box, or section
- Alignment with neighbouring fields
- Intervening labels or values
- Column boundaries
- Heading and footer boundaries
- Distance relative to text height
- Agreement with Markdown
- Competing candidates

A nearby value across a column boundary must lose to a slightly farther value inside the correct form group.

### 9. Resolve relationships together

Label/value relationships are selected for the complete local section.

This prevents:

- Reusing one value for several labels.
- Selecting a locally close pair that blocks a much stronger overall mapping.
- Moving values across repeated form rows.

Multiple possible solutions with similar total evidence are sent to Review.

### 10. Reconcile Docling and Markdown

For fields:

- Coordinates determine visual association.
- Markdown supplies structural association and source text.
- Agreement produces high confidence.
- A strong coordinate result with neutral Markdown can be accepted.
- Direct disagreement becomes unresolved.

For tables:

- Docling indexes and spans define the primary grid.
- Markdown provides an independent check on text and row order.
- Missing Markdown delimiters cannot override reliable Docling positions.
- Conflicting grids are preserved and flagged instead of silently repaired.

## Table Interpretation After Grid Reconstruction

Only after the grid is stable should it be interpreted.

### Field-pair view

Apply when rows contain independent label/value relationships.

Empty values remain attached to their printed labels.

### Repeated-record view

Apply when stable headers define the meaning of later columns.

A missing value remains empty under its correct header.

### Uncertain view

When neither interpretation is reliable:

- Preserve the neutral grid.
- Do not flatten it.
- Do not discard empty cells.
- Show it in Review.

## Approach 2 — Selective Fallback

The optional LLM will not receive the entire final Markdown by default.

It receives only:

- The unresolved source block
- Plausible labels and values
- The relevant section heading
- The relevant form row or complete table
- Nearby repeated patterns
- Coordinate relationships
- The reason deterministic matching failed

For a table problem, send the complete affected table rather than isolated cells because headers and neighbouring rows provide necessary context.

For an ordinary field problem, send only the local section.

The model chooses among supplied candidates. Every selection must still pass exact source and location validation.

## Required Tests Before Release

### Separator-free fields

Test:

- Numeric, date, code, and ordinary-word values
- Styled and unstyled labels
- Same-line and next-line values
- Multiple fields on one line
- Repeated aligned field rows
- Two-column forms
- Ambiguous all-text lines
- OCR-merged and OCR-split text

### Sparse tables

Generate tables where every possible column is blank in turn:

- Missing first cell
- Missing middle cell
- Missing last cell
- Multiple missing cells
- Only one populated cell
- Empty row
- Printed dash
- Printed “N/A”
- Wrapped value
- Merged cell
- Multi-row header
- Page continuation

Required invariant: removing a cell must leave a gap; it must never shift later cells.

### Layout variation

Test the same logical content with:

- Different page sizes
- Different column widths
- Different font sizes
- Rotated pages
- Multi-column documents
- Boxed and unboxed forms
- Large and small spacing
- Scanned/OCR documents

No test or production rule may depend on invoice-specific, certificate-specific, or sample-specific field names.

## Final Implementation Decision

- Use Approach 1 for clear Markdown structure.
- Use Approach 5 to resolve separator-free layouts and reconstruct sparse tables.
- Preserve the full neutral table grid before interpreting it.
- Never compress empty cells or left-shift later values.
- Never guess a separator-free textual boundary without unique structural evidence.
- Send unresolved cases to Review.
- Keep the selective LLM fallback disabled by default.

