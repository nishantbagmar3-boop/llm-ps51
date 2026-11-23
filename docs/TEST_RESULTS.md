# Test Results — executed sample runs

- Date: 23 Nov 2026 10:19
- Model: `gemini-2.5-flash` (temperature 0)
- Every row below comes from a live run of scripts/run_samples.py — statuses are calculated by analysis/range_checker.py in Python, never by the LLM.

### test1_hemoglobin_low.txt

- Extracted **1** test(s) in 8.3s (model `gemini-2.5-flash`, two LLM calls: extraction + explanations)

| Test | Value | Reference (as printed) | Python status | Expected | OK |
|---|---|---|---|---|---|
| Hemoglobin | 10.5 g/dL | 12.0 - 16.0 | **LOW** | LOW | ✅ |

- Explanations returned for all 1 test(s). ✅
- Example explanation (*Hemoglobin*): “Hemoglobin is a protein found in your red blood cells. Its main job is to carry oxygen from your lungs to all the tissues and organs in your body. Your hemoglobin level is 10.5 g/dL. This value is below the reference range of 12.0 - 16.0 g/dL printed on your r…”


### test2_glucose_normal.txt

- Extracted **1** test(s) in 9.2s (model `gemini-2.5-flash`, two LLM calls: extraction + explanations)

| Test | Value | Reference (as printed) | Python status | Expected | OK |
|---|---|---|---|---|---|
| Fasting Glucose | 92 mg/dL | 70 - 100 | **NORMAL** | NORMAL | ✅ |

- Explanations returned for all 1 test(s). ✅
- Example explanation (*Fasting Glucose*): “This test measures the amount of sugar, also known as glucose, in your blood. It is taken after you have not eaten for several hours. Your Fasting Glucose level is 92 mg/dL. This value falls within the normal reference range of 70 - 100 mg/dL printed on your r…”


### test3_wbc_high.txt

- Extracted **1** test(s) in 9.0s (model `gemini-2.5-flash`, two LLM calls: extraction + explanations)

| Test | Value | Reference (as printed) | Python status | Expected | OK |
|---|---|---|---|---|---|
| Total WBC Count | 13.8 x10^3/uL | 4.0 - 11.0 | **HIGH** | HIGH | ✅ |

- Explanations returned for all 1 test(s). ✅
- Example explanation (*Total WBC Count*): “This test measures the total number of white blood cells in your blood. White blood cells are an important part of your body's immune system, helping to fight off infections and other diseases. Your Total WBC Count is 13.8 x10^3/uL, which is above the referenc…”


### test4_mixed_results.txt

- Extracted **4** test(s) in 16.2s (model `gemini-2.5-flash`, two LLM calls: extraction + explanations)

| Test | Value | Reference (as printed) | Python status | Expected | OK |
|---|---|---|---|---|---|
| Hemoglobin | 9.8 g/dL | 12.0 - 16.0 | **LOW** | LOW | ✅ |
| Total WBC Count | 12.2 x10^3/uL | 4.0 - 11.0 | **HIGH** | HIGH | ✅ |
| Platelet Count | 320 x10^3/uL | 150 - 450 | **NORMAL** | NORMAL | ✅ |
| Serum Calcium | 9.1 mg/dL | 8.5 - 10.5 | **NORMAL** | NORMAL | ✅ |

- Explanations returned for all 4 test(s). ✅
- Example explanation (*Hemoglobin*): “Hemoglobin is a protein found in your red blood cells. Its main job is to carry oxygen from your lungs to all parts of your body. Your hemoglobin level is 9.8 g/dL, which is below the reference range of 12.0 - 16.0 g/dL printed on your report. This means your …”


### test5_missing_range.txt

- Extracted **2** test(s) in 81.1s (model `gemini-2.5-flash`, two LLM calls: extraction + explanations)

| Test | Value | Reference (as printed) | Python status | Expected | OK |
|---|---|---|---|---|---|
| Vitamin D (25-OH) | 22.4 ng/mL | Not provided | **NOT EVALUATED** | NOT EVALUATED | ✅ |
| HbA1c | 5.4 % | 4.0 - 5.6 | **NORMAL** | NORMAL | ✅ |

- Explanations returned for all 2 test(s). ✅
- Example explanation (*Vitamin D (25-OH)*): “Vitamin D is important for bone health and other body functions. This test measures the level of vitamin D in your blood. Your Vitamin D (25-OH) result is 22.4 ng/mL. This value could not be evaluated automatically because a reference range was not provided on…”


### Error-path checks (no fabrication — executed now)

- Invalid PDF upload (random bytes): raised `PDFExtractionError` as expected ✅
- Empty text input: rejected with “No report text was provided. Please upload a file or paste your report.” ✅
- Scanned PDF without extractable text: detected, OCR message shown ✅
- Malformed LLM JSON (no repair available): raised `JSONParsingError` as expected ✅
- Missing API key: raised `GeminiClientError` as expected ✅

## Verdict

**All sample expectations and error-path checks passed.** ✅