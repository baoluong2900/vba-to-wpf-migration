# Feature: LLM Query Classification (SelQuery vs UpdQuery)

The user wants to add an LLM evaluation step that classifies whether a translated Oracle query is a `SelQuery` (SELECT) or an `UpdQuery` (UPDATE/INSERT/DELETE). This type should be properly evaluated and saved whenever a user manually saves their edits, or when the AI converts it.

## Proposed Changes

### [MODIFY] `backend/layer4/sql_migration/router.py`
1. Add a new `_llm_classify_query_type(sql, model_id)` function that uses the selected LLM to evaluate the SQL string and return `"SelQuery"` or `"UpdQuery"`.
2. Add `model: str = ""` to `SaveRequest` so the backend knows which LLM to use during save.
3. In `update_query` (Save endpoint), call the LLM classification function on `req.oracle_sql` and save it to the `query_type` field.
4. In `convert_query` (Convert endpoint), also call the LLM classification to immediately set `query_type` for the frontend.

### [MODIFY] `frontend/src/app/layer4/page.tsx`
1. Pass the `selectedModel` from the frontend to the save request payload (`model: selectedModel`). This ensures the user's chosen LLM is used to evaluate the query type.
2. The UI will then automatically display the updated `query_type` in the list and the details panel.

## Open Questions / Clarifications
- This will cause the "Save" action to make an API call to the LLM. It might take 1-2 seconds longer to complete saving. Is this acceptable? If yes, I'll proceed.
