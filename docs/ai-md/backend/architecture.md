# Backend Architecture

## Overview
The vba_brain project's backend is responsible for parsing legacy VBA/Access databases, processing the logic using AI agents, and generating modern C# WPF source code. It is structured into multiple layers to separate concerns.

## Layer 1: Parser
- Responsible for parsing raw Access JSON exports (database_json) and ingesting them into MongoDB collections (forms, reports, modules, macros, queries, tables).
- Data flows strictly from Layer 1 to MongoDB.

## Layer 2: LLM Engine (Core Agent Framework)
- Houses the FastAPI HTTP server running on port 8000.
- Coordinates the BD (Basic Design) and DD (Detail Design) agent pipelines.
- Reads source data from MongoDB, NOT directly from Layer 1.
- Output from the agents is ALWAYS written to `backend/layer2/output/` in structured JSON.

## Layer 3: Tools & Utilities
- Query tools and metadata services used by the agents during generation.

## Layer 5: C# Generators
- Uses the parsed DD/BD JSON files to instruct LLMs on generating C# ViewModels, Services, and Repositories.
- Includes specific agents like `agent_logic.py`, `agent_repo.py`, etc.
