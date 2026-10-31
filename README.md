![Banner](banner.png)

# misconfig-ConfigDependencyChecker
Identifies dependencies between configuration files. Analyzes included files or referenced variables within configurations to map out relationships. Highlights circular dependencies or missing dependencies that could lead to misconfigurations. Uses 'graphlib' (Python 3.9+) or constructs a simple graph data structure. - Focused on Check for misconfigurations in configuration files or infrastructure definitions

## Install
`git clone https://github.com/ShadowStrikeHQ/misconfig-configdependencychecker`

## Usage
`./misconfig-configdependencychecker [params]`

## Parameters
- `-h`: Show help message and exit
- `-f`: Specify the configuration file format (
- `-d`: Enable debug logging.

## What is checked
- `include` and `depends_on` keys at any depth in the file. Each one may hold a single path or a list of paths, and a file that carries both keys has both of them checked.
- Reference keys (`$ref`, `ref`, `reference`, `config_ref`) that name a `.yaml`, `.yml`, or `.json` file.
- Variable references that name a config file, in the shapes `${...file.yaml}` and `{{ ref('file.yaml') }}`.
- Paths are resolved against the directory of the file that names them. The tool prints paths only, never configuration values.

## Exit codes
- Exit 0: every input was read and checked, and no circular or missing dependency was found.
- Exit 1: circular or missing dependencies were found, or an input could not be checked at all. A missing file, a malformed file, and an empty file are each reported as an unchecked input at exit 1. They are never reported as "No dependency issues found."

## License
Copyright (c) ShadowStrikeHQ
