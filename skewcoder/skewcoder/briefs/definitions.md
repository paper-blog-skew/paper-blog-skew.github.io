# Brief: definitions of the metrics (one text, the other side closed)

You define the metrics of ONE text, a paper or a blog post, so that the paper's metrics and the blog's metrics can later be
compared by what they measure, not by their wording. You have this text and its frozen list of metrics, and nothing else.
You have not seen, and must not guess at, the other text.

## What you write

`definitions.json`: `{"definitions": {"<metric id or key>": "<definition>", ...}}`, with one entry for every metric on the
list and no others.

A definition is ONE line, 6 to 25 words, that says **what is measured**:
- the quantity (a count, a time, a cost, a rate, a probability, an efficiency, a size, a setting such as a model or a method);
- what it is a quantity *of* (the cell, the pack, one charge cycle, the simulation, the test samples, …);
- its unit, when the text states one.

Write it in plain, standard words, so that two texts measuring the same thing would be defined the same way: "manufacturing
cost per unit of stored energy" for "how cheap the batteries are to make", or for "the cost of
each kilowatt-hour of storage". Use the text's own reading of the metric, never your general knowledge of the field.

## What a definition must never contain

- **What the metric depends on, causes, limits or is related to.** No "depends on", "scales with", "grows with", "limits",
  "determines", "requires", "because", "leads to", "proportional to", "increases", "decreases", "affects", "as a function of",
  "bounded by". A definition says what the thing IS, never how it behaves or what it is linked to.
- **The name of another metric on the list.** A definition of "number of charge cycles" may say "of the cell", but not "the
  cycle life" if cycle life is another metric on the list.
- Values ("400 cells", "200 seconds"), claims ("record", "largest"), or the text's opinion.
- A category prefix ("Setting:", "Method:", "Hardware setting:"). A setting is defined like any other metric.

## Checks before you report

Run `bash check.sh`. It fails on a missing or extra id, a definition outside 6–25 words, a forbidden dependence word, or the
multi-word name of another metric. Fix every failure. Report the count and every definition you found hard to write.
