# Creepypasta darkness analysis

Choose **Creepypasta · darkness** when saving a manuscript revision or creating a chapter-workbench analysis snapshot. The private revision report includes a 0–5 darkness rating, chapter ratings, strongest passages, an expandable scale guide, and revision prompts. Select Darkness or a component in the existing signal inspector to see evidence; the timeline and CSV export also include these signals. Downloaded revision JSON preserves the rating and engine version.

| Level | Label |
| --- | --- |
| 0 | No clear signals |
| 1 | Unsettling |
| 2 | Eerie |
| 3 | Disturbing |
| 4 | Terrifying |
| 5 | Nightmarish |

The dimensions are creeping unease, creeping dread, uncanny events, psychological horror, and visceral horror. Psychological or uncanny horror can rank highly without graphic violence. Darkness estimates intensity, not quality; there is no target score, age classification, or automatic public content label.

## Method and limits

`studio/darkness.py` is a versioned, offline English lexical estimator. It sends no writing to an external service. It ignores Markdown headings and fenced code using the existing prose extractor; word boundaries avoid substring matches, and approximate negation excludes cues such as “no gore.” Evidence records both supported and excluded cues. Repetitions of the same cue count once per passage.

Each dimension uses `1 - exp(-unique_supported_cues / max(2, passage_words / 80))`. Passage darkness is 65% of the strongest dimension plus 35% of the mean of all five dimensions. Chapter and manuscript scores are word-weighted passage means, as in the existing narrative engine. Zero receives level 0; positive scores below .15, .35, .55, and .75 receive levels 1–4; scores at or above .75 receive level 5. Thresholds are editorial conventions, not empirically calibrated reader ratings. Dimension labels use the same scale.

Short samples below 100 words display a tentative-rating notice. Subtle implication, metaphor, irony, quoted discussion of horror, unusual vocabulary, other languages, and complex negation can be misread. Passage boundaries affect averaging. Inspect the quoted evidence and strongest passages instead of treating the draft average as a verdict. Revision prompts are optional craft suggestions, not generated judgments about missing material.

General fiction and River analysis remain unchanged. Existing saved revisions are not rescored or published. Select the new profile and save a new revision to use this engine. Migration 0013 adds the profile choice only; no manuscript data is rewritten. The repository has an Erotica reading channel but no steaminess scoring engine; this release adds the requested darkness counterpart independently.
