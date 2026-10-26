# TEST AGENT PROMPT – IMAGE INTEGRATION RULES
- Always use base64-encoded images for all tests and requests.
- Accepted formats: JPEG, PNG, WEBP only. No SVG/BMP/HEIC.
- Do not upload blank, solid-color, or uniform-variance images; every image must contain real visual features.
- Re-detect MIME after any transformation; animated images → first frame only.
- Resize large images to reasonable bounds.
