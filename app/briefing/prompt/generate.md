# [Prompt]

The following is a JSON array of viewer comments from a YouTube recipe video. Based only on these comments, generate a recipe-related briefing.

---

## [Objectives]

- Summarize only content directly related to the recipe: actual cooking experiences (difficulty/time/success–failure points), reviews of taste/flavor/texture, concrete opinions such as substitute ingredients, cooking tips, storage/reheating advice.
- Must exclude: editing/creator compliments, ads/links, chit-chat/exclamations, unanswered questions, political/social/religious or otherwise irrelevant content.
- **Repeated or similar content must be prioritized**. Merge similar experiences/claims into one representative sentence.
- **Frequency-based summarization rule**:
  1. Identify the recipe-related topics most frequently mentioned
  2. Summarize each into one essential and generalizable sentence
  3. If slots remain, add less frequent but useful concrete tips for improving the recipe
- No speculation or invention. Use only information that actually appears in the comments.
- The result must consist of **2–5 concise Korean declarative sentences (List[str])**.
- Each sentence must be **at least 5 characters and at most 50 characters long**.
- Each sentence must end with the **Korean “~해요” style (polite ending)**, and should sound natural.
- If there are fewer than 2 valid recipe-related points, return an **empty array ([])**.

---

## [Output format]

- toolUse: emit_briefing
- input: {"items": ["Sentence1", "Sentence2", ...]}  
  // Korean, 2–5 items. If fewer than 2, return an empty array.

---

## [Writing guide]

- Reflect “what was most frequently mentioned” in the comments.  
  (Example: “Many comments said it was too salty” → “간이 강하니 소금/간장 양을 줄이라는 피드백이 많아요.”)
- Merge similar expressions, but if critical conditions (ingredients, ratios, time, tools, heat level, etc.) are repeatedly mentioned, include them.
- Prioritize reproducible tips/conditions over vague impressions.
- **All output must be written in Korean.**

---

## [Comments (JSON array)]

{{ comments_json }}
