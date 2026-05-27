def convert_table_to_ddl(table: dict, target_db: str) -> str:
    """
    Deterministically converts an Access table schema (from MongoDB) 
    into a CREATE TABLE DDL for the specified target_db.
    No LLM used.
    """
    table_name = table.get("table_name", "UNKNOWN_TABLE")
    columns = table.get("columns", [])
    
    lines = [f"CREATE TABLE {table_name} ("]
    
    target_db_upper = target_db.upper()
    
    col_defs = []
    for col in columns:
        col_name = col.get("logical_name", "UNKNOWN_COL")
        access_type = col.get("data_type", "Text").lower()
        length = col.get("length", "")
        required = str(col.get("required", "False")).lower() == "true"
        
        # Mapping logic
        if target_db_upper == "ORACLE":
            if "text" in access_type:
                dt = f"VARCHAR2({length if length else 255})"
            elif "memo" in access_type:
                dt = "CLOB"
            elif "long" in access_type or "integer" in access_type or "byte" in access_type:
                dt = "NUMBER"
            elif "double" in access_type or "single" in access_type or "currency" in access_type:
                dt = "NUMBER"
            elif "date" in access_type or "time" in access_type:
                dt = "DATE"
            elif "boolean" in access_type or "yes/no" in access_type:
                dt = "NUMBER(1)"
            elif "ole" in access_type:
                dt = "BLOB"
            else:
                dt = "VARCHAR2(255)"
                
        elif target_db_upper == "POSTGRESQL":
            if "text" in access_type:
                dt = f"VARCHAR({length if length else 255})"
            elif "memo" in access_type:
                dt = "TEXT"
            elif "long" in access_type:
                dt = "BIGINT"
            elif "integer" in access_type:
                dt = "INTEGER"
            elif "byte" in access_type:
                dt = "SMALLINT"
            elif "double" in access_type or "single" in access_type:
                dt = "DOUBLE PRECISION"
            elif "currency" in access_type:
                dt = "NUMERIC(19, 4)"
            elif "date" in access_type or "time" in access_type:
                dt = "TIMESTAMP"
            elif "boolean" in access_type or "yes/no" in access_type:
                dt = "BOOLEAN"
            elif "ole" in access_type:
                dt = "BYTEA"
            else:
                dt = "VARCHAR(255)"
                
        elif target_db_upper == "SQL SERVER":
            if "text" in access_type:
                dt = f"VARCHAR({length if length else 255})"
            elif "memo" in access_type:
                dt = "VARCHAR(MAX)"
            elif "long" in access_type:
                dt = "BIGINT"
            elif "integer" in access_type:
                dt = "INT"
            elif "byte" in access_type:
                dt = "TINYINT"
            elif "double" in access_type or "single" in access_type:
                dt = "FLOAT"
            elif "currency" in access_type:
                dt = "MONEY"
            elif "date" in access_type or "time" in access_type:
                dt = "DATETIME"
            elif "boolean" in access_type or "yes/no" in access_type:
                dt = "BIT"
            elif "ole" in access_type:
                dt = "VARBINARY(MAX)"
            else:
                dt = "VARCHAR(255)"
                
        elif target_db_upper == "MYSQL":
            if "text" in access_type:
                dt = f"VARCHAR({length if length else 255})"
            elif "memo" in access_type:
                dt = "TEXT"
            elif "long" in access_type:
                dt = "BIGINT"
            elif "integer" in access_type:
                dt = "INT"
            elif "byte" in access_type:
                dt = "TINYINT"
            elif "double" in access_type or "single" in access_type:
                dt = "DOUBLE"
            elif "currency" in access_type:
                dt = "DECIMAL(19,4)"
            elif "date" in access_type or "time" in access_type:
                dt = "DATETIME"
            elif "boolean" in access_type or "yes/no" in access_type:
                dt = "BOOLEAN"
            elif "ole" in access_type:
                dt = "BLOB"
            else:
                dt = "VARCHAR(255)"
        
        else: # Default ANSI SQL
            if "text" in access_type:
                dt = f"VARCHAR({length if length else 255})"
            elif "long" in access_type or "integer" in access_type:
                dt = "INTEGER"
            elif "date" in access_type or "time" in access_type:
                dt = "TIMESTAMP"
            else:
                dt = "VARCHAR(255)"

        req_str = " NOT NULL" if required else ""
        col_defs.append(f"    {col_name} {dt}{req_str}")
        
    lines.append(",\n".join(col_defs))
    lines.append(");")
    
    return "\n".join(lines)
