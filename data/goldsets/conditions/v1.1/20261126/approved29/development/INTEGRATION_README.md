# Development goldset integration staging

This directory contains 29 human-approved notices and 112 conditions from the two existing ingest outputs. It is a partial approved set, not the final 30-notice development goldset.

After the remaining notice receives explicit human approval, update only its review packet, run the existing `tools/ingest_condition_gold_reviews.py` for `remaining25`, and regenerate this merged output and manifest from the two reviewed JSONL pairs. Validate 30 notices, 116 conditions, unique IDs, matching condition/logic notice sets, source spans and references before marking the development goldset final.
