# Backend - Layer 4 (SQL Migration)

## Purpose
Layer 4 is dedicated exclusively to **SQL Translation and Migration**. It handles the complex task of converting legacy Microsoft Access SQL queries (with Access-specific functions like `DLookup`, `IIf`, `#date#`) into modern SQL dialects (primarily PostgreSQL).

## Key Responsibilities
1. **Query Seeding (`/api/layer4/seed`):** 
   - Reads raw queries from the Layer 1 `queries` collection and seeds them into a specialized `queries_v2` collection for tracking migration status.
2. **AI SQL Conversion (`/api/layer4/convert`):** 
   - Uses LLMs to intelligently parse and rewrite Access SQL into PostgreSQL.
   - Handles the conversion of specific Access functions into standard SQL/PostgreSQL equivalents (e.g., `COALESCE`, `CASE WHEN`, `TO_DATE`).
3. **Human-in-the-Loop Validation (`/api/layer4/queries/{name}`):** 
   - Exposes REST endpoints to allow engineers to review AI-converted queries.
   - Allows manual overriding/updating of the `target_sql` result if the AI conversion is imperfect.
4. **Testing & Stats (`/api/layer4/test_query` & `/stats`):**
   - Tracks the conversion success rates and provides metrics on how many queries have been successfully migrated vs. how many require human intervention.

## Pipeline Position
- Sits between Layer 1 (Raw Data) and Layer 5 (C# Code Generation). 
- Once Layer 4 successfully converts all SQL statements, the C# Generators (Agent Repo / Agent Logic) in Layer 5 can inject these clean PostgreSQL SQL strings directly into Dapper repositories.
