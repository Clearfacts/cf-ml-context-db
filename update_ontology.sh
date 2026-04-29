
set -e 

# Usage: ./update_ontology.sh path/to/source.yaml
check_args() {
    if [ "$#" -ne 1 ]; then
        echo "Usage: $0 path/to/source.yaml"
        exit 1
    fi
}
check_args "$@"

SOURCE_YAML=$1 

python agents/extraction_agent/orchestrate_run.py "$SOURCE_YAML" --agent-timeout 1800 -- copilot --allow-all --no-color -p "Read the instructions in {prompt_file}. Then perform the task exactly as specified. You must only modify {run_ontology}. Use {program} and {schema} as mandatory constraints and use {source_yaml} as source definition."
