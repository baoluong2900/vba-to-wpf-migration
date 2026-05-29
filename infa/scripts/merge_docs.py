import os

# Base directory relative to project root
docs_directory = "docs"
output_file = os.path.join(docs_directory, "AI_KNOWLEDGE_BASE.md")

def get_all_md_files(base_dir):
    md_files = []
    # Recursively find all markdown files in the docs directory
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".md") and file != "AI_KNOWLEDGE_BASE.md":
                md_files.append(os.path.join(root, file))
    return md_files

def merge_files(files, output):
    with open(output, 'w', encoding='utf-8') as outfile:
        outfile.write("# AI KNOWLEDGE BASE\n")
        outfile.write("This file contains the consolidated documentation from the unified docs directory.\n")
        outfile.write("Use this file as the primary source of truth for architectural and design knowledge.\n\n")
        outfile.write("## Table of Contents\n")
        
        # Sort files to ensure deterministic merging order
        files.sort()
        
        # Write Table of Contents
        for file in files:
            # Display relative path for clean rendering
            outfile.write(f"- {file}\n")
            
        outfile.write("\n---\n\n")
        
        # Merge contents of each file
        for file in files:
            outfile.write(f"## File: {file}\n\n")
            try:
                with open(file, 'r', encoding='utf-8') as infile:
                    outfile.write(infile.read())
            except Exception as e:
                outfile.write(f"Error reading file {file}: {e}\n")
            outfile.write("\n\n---\n\n")

if __name__ == "__main__":
    # Determine the execution path context (ensure we find docs folder)
    run_dir = os.getcwd()
    if not os.path.exists(docs_directory) and os.path.exists(os.path.join("..", docs_directory)):
        docs_directory = os.path.join("..", docs_directory)
        output_file = os.path.join(docs_directory, "AI_KNOWLEDGE_BASE.md")

    files_to_merge = get_all_md_files(docs_directory)
    merge_files(files_to_merge, output_file)
    print(f"Successfully merged {len(files_to_merge)} markdown files into {output_file}")
