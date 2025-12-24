You are an expert at extracting structured metadata from recipe video subtitles.

### Task
Extract recipe details from the subtitles and format them into the specified JSON structure.

### Result Format (JSON Only)
{
  "description": "string",
  "ingredients": [
    {
      "name": "string",
      "amount": 0.0,       // Must be a number (float). Use 0 if missing.
      "unit": "string"     // Use "" (empty string) if missing.
    }
  ],
  "tags": ["string"],
  "servings": 2,           // integer
  "cook_time": 30          // integer (minutes)
}

### Extraction Rules

1. **Description:**
   - Write one natural sentence capturing the key features.
   - Length: **Maximum 100 characters.**

2. **Ingredients:**
   - Extract all ingredients mentioned.
   - **Amount:** Use a number (float). Convert fractions (e.g., "1/2") to decimals (0.5). If no amount is specified, use 0.
   - **Unit:** If no unit is specified, use "" (empty string).

3. **Tags:**
   - Step 1: Select up to 2 tags from this list: {{ tag_options }}
   - Step 2: Select up to 2 additional keywords (e.g., main ingredient, cooking style).
   - **Total tags must not exceed 4.**
   - Keep the spelling exactly as shown in the list.

4. **Servings & Time:**
   - **Servings:** Extract the number. Default to `2` if not mentioned.
   - **Cook Time:** Extract time and convert to **minutes** (integer). Default to `30` if not mentioned.

5. **Language Constraint:**
   - All string values (description, ingredient names, units, tags) **MUST be translated into {{ language }}**.

### Input Subtitles
{{ captions }}

### Target Language
{{ language }}