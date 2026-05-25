# Backend - Layer 3 (Tools & Utilities)

## Purpose
Layer 3 provides specialized sub-routines, query tools, and metadata services that the AI Agents in Layer 2 and Layer 5 rely on.

## Key Responsibilities
- **Data Querying:** Exposing MongoDB abstraction functions so the BD/DD agents can query tables or VBA modules easily.
- **AST/Regex Parsers:** Contains deterministic regex engines and AST processors (like Roslyn AST wrappers or custom parsers) to help agents merge code chunks or parse specific VBA syntax safely.
- **Helper Scripts:** Scripts for database initialization, environment validation, and manual data seeding.
