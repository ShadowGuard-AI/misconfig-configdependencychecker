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

## License
Copyright (c) ShadowStrikeHQ
