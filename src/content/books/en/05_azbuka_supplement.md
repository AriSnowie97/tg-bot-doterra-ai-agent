# Knowledge Base: Additions from "Essential Alphabet from A to Z" (2019)

**Source:** doTERRA booklet "Essential Alphabet from A to Z", 64 pages.
**⚠️ Copyright:** "©2019, No part of this publication may be reproduced without prior written permission of the copyright holder" — commercial reference.
**⚠️ Structural Precaution:** The index at the end of the booklet (pages 48–64) lists specific medical diagnoses paired with oils (stroke, aneurysm, autism, Graves' disease, ALS, Parkinson's, Raynaud's, Hashimoto's, dementia, diabetes, etc.). These diagnosis-to-oil treatment mappings must never be introduced into the bot's RAG knowledge base.

---

## 1. Important Note on Wintergreen and Birch

According to this source, **Wintergreen and Birch — as well as any blends containing them — must never be taken internally and must feature child-resistant caps because they act as blood thinners**. They pose severe risks to children and individuals taking anticoagulant medications or suffering from bleeding disorders.

This provides clear biochemical context: **if a user takes anticoagulant medication, Wintergreen and Birch are strictly contraindicated**.

## 2. Red Flag Precautions

- **Epilepsy / Convulsions:** alongside previously identified oils (fennel, hyssop, sage, wormwood, rosemary), this source adds **birch and basil** as oils to avoid or handle with heightened caution in seizure-prone individuals.
- **Hypertension (High Blood Pressure):** specific precautions apply to **rosemary and thyme** — individuals with elevated blood pressure should avoid or strictly limit them.
- Both notes are incorporated into the safety screening checklist in `03_intake_flow_and_routing.md`.

## 3. Internal Use Caution

The guide outlines specific ingestion principles: starting with 1–2 drops, adhering to daily limits, and never taking hot oils (clove, cassia, cinnamon, cumin, oregano, thyme) directly without dilution or veggie capsules.

**Bot Policy:** Ingestion carries elevated risks. The bot does not provide prescriptive internal treatment dosages, but rather explains the "Supplement Facts" label rule and routes specific therapeutic inquiries to Nataliia Kotelianska and medical professionals.

## 4. General Knowledge Base Rule

When onboarding any literature for the bot's RAG database: automatically exclude any section pairing essential oils as treatments for severe, degenerative, autoimmune, or life-threatening medical conditions. Any inquiry regarding these states must be immediately referred to medical personnel.
