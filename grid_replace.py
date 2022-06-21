""" Simple script which remaps grid values based on rock type

 @Author:Terry Hannant <thannant@metafu.net>

 https://github.com/TerryHannant/eclipse-grid-scripts
"""
import sys
import re


# This could go in mapping toml for more flexibility
mapping_block_name = "SATNUM"

# Quick and dirty toml parser to avoid dependency or python 3.11
# Very error prone but ok for our file simple format
# TODO replace with more robust lib version
def parse_toml(reader):
    result = {}
    current_key = ""
    for line in reader:
        line = line.strip()
        if not line or line.isspace() or line.startswith("#"):
            pass
        elif line.startswith("[") and line.endswith("]"):
            current_key = line[1:-1]
            result[current_key] = {}
        else:
            parts = line.split("=")
            if len(parts) != 2:
                pass
            else:
                result[current_key][parts[0]] = parts[1]
    return result


# Initial pass of file to find mapping names
def find_mappings(reader, block_name):
    result = {}
    # First skip header comments
    for line in reader:
        if not line.startswith("--"):
            break

    preamble = []
    skip_block = False
    for line in reader:
        if skip_block:
            if line.startswith("/"):
                preamble = []
                skip_block = False
        elif line.startswith("--") and line.endswith("--\n"):
            preamble.append(line.strip()[3:-2])
        elif line.startswith("\n"):
            pass
        elif not line.startswith(block_name):
            skip_block = True
        else:
            # Just in case of duplicate blocks with same name
            result = {}
            # Create mapping id->name
            for l in preamble:
                parts = l.split(" = ")
                result[parts[1]] = parts[0]

    return result


if __name__ == "__main__":
    # TODO Use arg parse
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} input_file map_file output_file")
        exit(1)

    reader = None
    writer = None
    source_mappings = None
    mappings = None

    input_file = sys.argv[1]

    # Read mapping file
    # Note file only uses type->block->value in toml file as its more intuitive for the user
    try:
        with open(sys.argv[2]) as map_file:
            source_mappings = parse_toml(map_file)
    except IOError as x:
        print(f"Unable to read mapping file {sys.argv[2]} : {x}")
        exit(1)

    try:
        reader = open(sys.argv[1])
    except IOError as x:
        print(f"Unable to read input file {sys.argv[1]} : {x}")
        exit(1)

    file_mappings = find_mappings(reader, mapping_block_name)
    if not file_mappings:
        print(f"Unable to find mapping block {mapping_block_name}")

    # Swap the dict for easu error messages
    rev_file_mappings = dict((v, k) for k, v in file_mappings.items())

    # Rejig the mappings to block->type->value where type is the ID instead of name
    mappings = {}
    for s, maps in source_mappings.items():
        for k, v in maps.items():
            if k not in mappings:
                mappings[k] = {}
            if (
                s in file_mappings.keys()
            ):  # If the type name is not present in file then ignore it
                mappings[k][file_mappings[s]] = v

    # Reset reader
    reader.seek(0)

    # Reopen source data file a second time to read types
    # Could have read the types in list on first pass but the number of entries (10M+)
    # could be quite large so more safe just to reread the file
    try:
        lookup_reader = open(sys.argv[1])
    except IOError as x:
        print(f"Unable to read input file {sys.argv[1]} : {x}")
        exit(1)

    ##Fast forward file to start of mapping block
    line = lookup_reader.readline()
    while line:
        if line.startswith(mapping_block_name):
            break
        line = lookup_reader.readline()
    mapping_start_position = lookup_reader.tell()

    try:
        writer = open(sys.argv[3], "x")
    except IOError as x:
        print(f"Unable to open output file {sys.argv[2]} : {x}")
        exit(1)

    errors = set()
    # Read and rewrite the file
    remapped_block = False
    block_name = ""
    block_map = None
    for line in reader:
        if remapped_block:
            if line.startswith("/"):
                writer.write(line)
                remapped_block = False
                lookup_reader.seek(mapping_start_position)
            else:
                lookup_line = lookup_reader.readline()
                lookups = lookup_line.split()
                source_values = line.split()
                if len(source_values) != len(lookups):
                    print("Value count/types mismatch")
                else:
                    for v in lookups:
                        if v in block_map.keys():
                            writer.write(f" {block_map[v]}")
                        else:
                            writer.write(f" 0")
                            errors.add(
                                f"Mapping {rev_file_mappings[v]} - {block_name} missing"
                            )
                    writer.write("\n")
        elif line.startswith("--") or not line.strip():
            writer.write(line)
        elif line.strip() in mappings.keys():
            writer.write(line)
            remapped_block = True
            block_name = line.strip()
            block_map = mappings[block_name]

            lookup_reader.seek(mapping_start_position)
        else:
            writer.write(line)

    for error in sorted(errors):
        print(error)
