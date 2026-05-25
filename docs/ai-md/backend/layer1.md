# Backend - Layer 1 (Parser)

## Purpose
Layer 1 is entirely responsible for Data Ingestion. It parses legacy Microsoft Access structures exported as raw JSON files and stores them reliably in a MongoDB database.

## Key Responsibilities
1. **Parsing Raw Export Data:** Reads `database_json` objects which represent raw Access properties (Forms, Reports, Macros, Modules, Queries, Tables).
2. **Data Normalization:** Normalizes the properties into structured NoSQL document formats.
3. **Database Population:** Inserts the cleaned data into corresponding MongoDB collections (e.g., `forms`, `reports`, `modules`, `macros`, `queries_v2`, `tables`, `dependency_graph`).

## Constraints
- **Unidirectional Flow:** Layer 1 is strictly a data provider. It only writes to MongoDB and NEVER calls Layer 2 APIs.
- **No LLM usage:** The parsing mechanism in Layer 1 is 100% deterministic code. No AI/LLM logic happens here.
