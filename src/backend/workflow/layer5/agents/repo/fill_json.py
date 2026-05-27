import json
import logging
import argparse
import re
from pathlib import Path
import sys

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
INPUTS_DIR = BASE_DIR / "inputs"
OUTPUTS_DIR = BASE_DIR / "outputs"

# Add parent layer5 path for core configuration imports
sys.path.insert(0, str(BASE_DIR.parent.parent))

from core.config import MONGO_URI, MONGO_DB
import tool_repo as tr

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def load_dd_json(form_name: str) -> dict:
    """Load DD JSON with multiple fallbacks."""
    # 1. MongoDB
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        doc = db["dds"].find_one({"$or": [{"form_name": form_name}, {"screen_name": form_name}]}, {"_id": 0})
        client.close()
        if doc:
            logger.info("Loaded DD JSON from MongoDB.")
            return doc
    except Exception as e:
        logger.warning("MongoDB load_dd_json failed: %s", e)

    # 2. Local inputs directory fallback
    candidates = [
        INPUTS_DIR / f"{form_name}.json",
        INPUTS_DIR / f"{form_name}_dd.json",
        # Layer 4 DD directory fallback
        BASE_DIR.parent.parent.parent / "layer4" / "inputs" / "DD_json" / "form" / f"{form_name}.json"
    ]
    
    for path in candidates:
        if path.exists():
            logger.info("Loaded DD JSON from local path: %s", path)
            return json.loads(path.read_text(encoding="utf-8"))

    raise FileNotFoundError(f"DD JSON for '{form_name}' not found in MongoDB or local paths.")

def load_table_schemas_mongo() -> dict:
    """Load table schemas from MongoDB."""
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        tables = {}
        for doc in db["tables"].find():
            name = doc.get("name", doc.get("table_name", ""))
            if name:
                tables[name] = doc
        client.close()
        return tables
    except Exception as e:
        logger.warning("MongoDB tables load failed: %s. Proceeding with empty map.", e)
        return {}

def load_single_table_schema_mongo(table_name: str) -> dict | None:
    """Load a single table schema from MongoDB."""
    try:
        from pymongo import MongoClient
        import unicodedata
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        
        doc = db["tables"].find_one({"name": table_name}, {"_id": 0})
        if doc:
            client.close()
            return doc
            
        doc = db["tables"].find_one({"table_name": table_name}, {"_id": 0})
        if doc:
            client.close()
            return doc
            
        norm_input = unicodedata.normalize('NFKC', table_name)
        all_tables = db["tables"].find({}, {"name": 1, "table_name": 1, "_id": 0})
        actual_name = None
        for item in all_tables:
            cand = item.get("name") or item.get("table_name", "")
            if cand and unicodedata.normalize('NFKC', cand) == norm_input:
                actual_name = cand
                break
                
        if actual_name:
            doc = db["tables"].find_one({"$or": [{"name": actual_name}, {"table_name": actual_name}]}, {"_id": 0})
            client.close()
            return doc
            
        client.close()
        return None
    except Exception as e:
        logger.warning("Single MongoDB table fetch failed for %s: %s", table_name, e)
        return None

def generate_reference_json(form_name: str):
    logger.info("Processing repository reference JSON for form: %s", form_name)
    
    try:
        # Load configurations and data
        dd_json = load_dd_json(form_name)
        dd_queries = tr.extract_valid_queries(dd_json)
        config = tr.load_config()
        
        param_map = tr.extract_parameters(dd_json, dd_queries)
        vba_args_raw = [f"{k}: {v}" for k, v in param_map.items()]
        parsed_args = tr.parse_vba_args(vba_args_raw, config)
        
        tr.register_query_columns(dd_queries, config)
        table_queries, query_map, deps_map = tr.build_dependency_graph(dd_queries, config)
        
        # Combine table schemas
        tables_schemas_mongo = load_table_schemas_mongo()
        table_schemas = dd_json.get("table_schemas", [])
        schema_map = {}

        for s in table_schemas:
            tname = s.get("table_name", "")
            if tname:
                schema_map[tname] = tr.unify_schema_fields(s)
        
        for k, v in tables_schemas_mongo.items():
            if k not in schema_map:
                schema_map[k] = tr.unify_schema_fields(v)
                
        # ── Structures for Reference JSON ────────────────────────────────────────
        repositories_out = []
        dtos_out = {}
        entities_out = {}
        
        # Global form-level cache for deduplication
        output_dto_cache = {}
        input_dto_cache = {}
        
        def to_pascal(s):
            return s[0].upper() + s[1:] if s else "Unknown"

        # Process each physical root table and its associated queries
        for table_name, queries in table_queries.items():
            # Load or resolve schema
            schema = schema_map.get(table_name)
            if not schema:
                for k, v in schema_map.items():
                    if k in table_name or table_name in k:
                        schema = v
                        break
            
            if not schema or not schema.get("fields"):
                mongo_doc = load_single_table_schema_mongo(table_name)
                if mongo_doc:
                    schema = tr.unify_schema_fields(mongo_doc)
                    schema_map[table_name] = schema
                    
            schema = schema or {"table_name": table_name, "fields": []}
            entity_fields = schema.get("fields", [])
            
            # Base metadata
            table_en = tr.find_table_key(table_name, config)
            base_name = tr.sanitize_identifier(table_en)
            
            entity_class_name = f"{base_name}Entity"
            repo_class_name   = f"{base_name}Repository"
            
            entity_prop_names = {tr.get_csharp_prop_name(f.get("name", ""), config) for f in entity_fields}
            functions = []
            
            for i, q in enumerate(queries):
                q_name = q.get("query_name", "")
                method_name = tr.derive_method_name(q, i, len(queries), config)
                method_base_name = method_name[:-5] if method_name.endswith("Async") else method_name
                
                query_fields = tr.derive_fields_from_queries([q], config)
                
                def get_real_cs_type(f: dict) -> str:
                    for e_f in entity_fields:
                        if e_f.get("name") == f.get("name"):
                            return e_f.get("csharp_type") or tr.oracle_to_cs_type(e_f.get("type", "VARCHAR2"))
                    return f.get("csharp_type") or tr.oracle_to_cs_type(f.get("type", "VARCHAR2"))
                
                # ── Resolve Return Type and Output ───────────────────────────
                is_scalar = False
                ret_type_str = ""
                ret_name_str = ""
                ret_kind = ""
                
                if len(query_fields) == 1:
                    is_scalar = True
                    ret_kind = "scalar"
                    ret_type_str = get_real_cs_type(query_fields[0])
                    ret_name_str = query_fields[0].get("name", "")
                else:
                    q_dto_extra = []
                    q_seen_props = set()
                    for f in query_fields:
                        pname = tr.get_csharp_prop_name(f.get("name", ""), config)
                        if pname not in entity_prop_names and pname not in q_seen_props:
                            q_dto_extra.append(f)
                            q_seen_props.add(pname)
                    
                    has_extra_fields = len(q_dto_extra) > 0
                    
                    if has_extra_fields:
                        ret_kind = "dto"
                        for df in query_fields:
                            df["csharp_type"] = get_real_cs_type(df)
                        
                        dto_fields_sig_list = []
                        seen_props = set()
                        dto_fields_resolved = []
                        for f in query_fields:
                            jp_raw = f.get("name", "")
                            jp = jp_raw.split('.')[-1].replace('"', '').strip() if jp_raw else ""
                            cs_type = f.get("csharp_type")
                            pname = tr.get_csharp_prop_name(jp_raw, config)
                            if pname in seen_props:
                                continue
                            seen_props.add(pname)
                            dto_fields_sig_list.append((jp, cs_type))
                            dto_fields_resolved.append({
                                "name": pname,
                                "type": cs_type,
                                "description": jp
                            })
                        
                        dto_sig = tuple(sorted(dto_fields_sig_list))
                        if dto_sig in output_dto_cache:
                            dto_class_name = output_dto_cache[dto_sig]
                        else:
                            dto_class_name = f"{method_base_name}Dto"
                            output_dto_cache[dto_sig] = dto_class_name
                            dtos_out[dto_class_name] = dto_fields_resolved
                        
                        ret_type_str = "dto"
                        ret_name_str = dto_class_name
                    else:
                        ret_kind = "entity"
                        ret_type_str = "entity"
                        ret_name_str = entity_class_name
                
                # Build Outputs
                outputs = []
                if ret_kind == "dto":
                    outputs.append({
                        "name": ret_name_str,
                        "type": "dto",
                        "description": ""
                    })
                elif ret_kind == "entity":
                    outputs.append({
                        "name": ret_name_str,
                        "type": "entity",
                        "description": ""
                    })
                elif ret_kind == "scalar":
                    outputs.append({
                        "name": "",
                        "type": ret_type_str,
                        "description": ""
                    })
                
                # ── Resolve Parameters and Inputs ────────────────────────────
                raw_p = q.get("parameters", "")
                q_param_names = {p.strip() for p in raw_p.split(",") if p.strip()}
                for w in q.get("sql", {}).get("where", []):
                    cond = w.get("condition", "")
                    if cond:
                        for m in re.finditer(r":(\w+)", cond):
                            q_param_names.add(m.group(1))

                if dd_json:
                    detail_specs = dd_json.get("sheet_3_detail_specs", [])
                    q_name = q.get("query_name", "")
                    for spec in detail_specs:
                        for qmap in spec.get("query_mappings", []):
                            if qmap.get("logic_query_name") == q_name or qmap.get("sheet_name") == q.get("sheet_name_pattern"):
                                for p in qmap.get("parameters", []):
                                    pname = p.get("name")
                                    if pname:
                                        q_param_names.add(pname)
                            
                method_args = [
                    a for a in parsed_args 
                    if a['vba'] in q_param_names or a['jp_key'] in q_param_names or a['cs_name'] in q_param_names
                ]
                use_method_input_dto = len(method_args) > 3
                inputs = []
                
                if use_method_input_dto:
                    input_sig_list = []
                    input_fields_resolved = []
                    for a in method_args:
                        typ = a['cs_type']
                        name = a['cs_name']
                        prop = to_pascal(name)
                        input_sig_list.append((prop, typ))
                        input_fields_resolved.append({
                            "name": prop,
                            "type": typ,
                            "description": a.get("jp_key", "")
                        })
                    input_sig = tuple(sorted(input_sig_list))
                    
                    if input_sig in input_dto_cache:
                        resolved_input_dto_name = input_dto_cache[input_sig]
                    else:
                        resolved_input_dto_name = f"{method_base_name}InputDto"
                        input_dto_cache[input_sig] = resolved_input_dto_name
                        dtos_out[resolved_input_dto_name] = input_fields_resolved
                        
                    inputs.append({
                        "name": resolved_input_dto_name,
                        "type": "dto",
                        "description": ""
                    })
                else:
                    for a in method_args:
                        inputs.append({
                            "name": a["cs_name"],
                            "type": a["cs_type"],
                            "description": a.get("jp_key", "")
                        })
                        
                # ── Finalize Function Entry ──────────────────────────────────
                functions.append({
                    "function_name": method_name,
                    "query_name": q_name,
                    "sheet_query_name": q.get("sheet_name_pattern", ""),
                    "description": q.get("query_purpose", "").strip(),
                    "input": inputs,
                    "output": outputs
                })
                
            # Add to Repositories
            repositories_out.append({
                "repository_name": repo_class_name,
                "table_name": table_name,
                "function": functions
            })
            
            # Track Entities
            if entity_class_name not in entities_out:
                entity_fields_resolved = []
                for field in entity_fields:
                    jp_raw  = field.get("name", "")
                    jp = jp_raw.split('.')[-1].replace('"', '').strip() if jp_raw else ""
                    cs_type = field.get("csharp_type") or tr.oracle_to_cs_type(field.get("type", "VARCHAR2"))
                    prop = tr.get_csharp_prop_name(jp_raw, config)
                    entity_fields_resolved.append({
                        "name": prop,
                        "type": cs_type,
                        "description": jp
                    })
                entities_out[entity_class_name] = entity_fields_resolved

        # ── Convert Gathered DTOs & Entities ──────────────────────────────────
        final_dtos = [{"dto_name": name, "fields": fields} for name, fields in dtos_out.items()]
        final_entities = [{"entity_name": name, "fields": fields} for name, fields in entities_out.items()]
        
        # Final Structured Reference JSON
        result_json = {
            "form_name": form_name,
            "repository": repositories_out,
            "dto": final_dtos,
            "entity": final_entities
        }
        
        # Save to target location
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUTS_DIR / f"{form_name}.json"
        output_path.write_text(json.dumps(result_json, ensure_ascii=False, indent=4), encoding="utf-8")
        
        logger.info("✅ Successfully generated repository reference JSON!")
        logger.info("Saved to: %s", output_path)
        print(f"Saved reference JSON to: {output_path}")
        
    except Exception as e:
        logger.error("❌ Failed to generate repository reference JSON.", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fill data into repository reference JSON based on form_name.")
    parser.add_argument("form_name", help="Form name (e.g., F_Login)")
    args = parser.parse_args()
    generate_reference_json(args.form_name)
