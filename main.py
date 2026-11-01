import argparse
import logging
import os
import re
import sys
import json
import yaml
from graphlib import TopologicalSorter, CycleError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ConfigDependencyChecker:
    """
    A tool to identify dependencies between configuration files.
    Analyzes included files or referenced variables within configurations to map out relationships.
    Highlights circular dependencies or missing dependencies that could lead to misconfigurations.
    """

    def __init__(self, config_files, format='auto', debug=False):
        """
        Initializes the ConfigDependencyChecker.

        Args:
            config_files (list): A list of configuration file paths.
            format (str, optional): The format of the configuration files ('yaml', 'json', or 'auto'). Defaults to 'auto'.
            debug (bool, optional): Enables debug logging if True. Defaults to False.
        """
        self.config_files = config_files
        self.format = format
        self.dependencies = {}  # {config_file: [dependent_config_file]}
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
            logging.debug("Debug mode enabled.")

    def _parse_config(self, config_file):
        """
        Parses the configuration file based on the specified format.

        Args:
            config_file (str): The path to the configuration file.

        Returns:
            dict: The parsed configuration data as a dictionary.

        Raises:
            ValueError: If the file format is not supported or if the file does not exist.
            Exception: If there is an issue parsing the content.
        """

        if not os.path.exists(config_file):
            raise ValueError(f"File not found: {config_file}")

        try:
            with open(config_file, 'r') as f:
                if self.format == 'yaml' or (self.format == 'auto' and config_file.endswith(('.yaml', '.yml'))):
                    try:
                        data = yaml.safe_load(f)
                        logging.debug(f"Successfully parsed {config_file} as YAML.")
                        return data
                    except yaml.YAMLError as e:
                        raise Exception(f"Error parsing YAML file {config_file}: {e}")
                elif self.format == 'json' or (self.format == 'auto' and config_file.endswith('.json')):
                    try:
                        data = json.load(f)
                        logging.debug(f"Successfully parsed {config_file} as JSON.")
                        return data
                    except json.JSONDecodeError as e:
                        raise Exception(f"Error parsing JSON file {config_file}: {e}")
                else:
                    raise ValueError(f"Unsupported file format for {config_file}. Specify 'yaml' or 'json'.")
        except FileNotFoundError:
            raise ValueError(f"File not found: {config_file}")
        except Exception as e:
            raise Exception(f"Error reading or parsing {config_file}: {e}")

    def _resolve_dependency(self, config_file, dep):
        if os.path.isabs(dep):
            return dep
        # I resolve a relative reference against the folder of the file
        # that names it, which is the only reading that makes nested
        # includes work. I do not normalise the result, so the same file
        # reached as ./b.yaml and as b.yaml stays two different strings
        # in the graph below.
        return os.path.join(os.path.dirname(config_file), dep)

    def _collect_dependencies(self, config_file, node, dependencies):
        """
        Walks a parsed configuration at any depth and collects dependencies:
        include and depends_on keys (a single string or a list), reference
        keys ($ref, ref, reference, config_ref) naming a config file, and
        variable references that name a config file, in the shapes
        ${...file.yaml} and {{ ref('file.yaml') }}.
        """
        if isinstance(node, dict):
            for key, value in node.items():
                # Every string under these keys is treated as a file path. That
                # is a real overreach for depends_on, which in plenty of config
                # formats names services rather than files: those names resolve
                # to paths that do not exist and get reported as missing below.
                # Reference keys further down are gated by file extension, and
                # these two keys are not, which is an inconsistency I keep visible.
                if key in ('include', 'depends_on'):
                    items = value if isinstance(value, list) else [value]
                    for item in items:
                        if isinstance(item, str):
                            dependencies.append(self._resolve_dependency(config_file, item))
                elif key in ('$ref', 'ref', 'reference', 'config_ref') and isinstance(value, str) \
                        and value.endswith(('.yaml', '.yml', '.json')):
                    dependencies.append(self._resolve_dependency(config_file, value))
                # I walk the value even when the key above already consumed it,
                # because an include can hold a nested structure. Nothing dedupes
                # the list, so a file named three times is reported three times
                # in the missing check later.
                self._collect_dependencies(config_file, value, dependencies)
        elif isinstance(node, list):
            for item in node:
                self._collect_dependencies(config_file, item, dependencies)
        elif isinstance(node, str):
            # This search never asks for the closing brace, so an unfinished
            # reference still yields a dependency. I would rather chase a
            # file a broken template pointed at than drop the reference.
            for match in re.finditer(r"\$\{[^}]*?([A-Za-z0-9_./-]+\.(?:yaml|yml|json))", node):
                dependencies.append(self._resolve_dependency(config_file, match.group(1)))
            for match in re.finditer(r"\{\{\s*ref\(\s*[\"']([^\"']+)[\"']\s*\)\s*\}\}", node):
                dependencies.append(self._resolve_dependency(config_file, match.group(1)))

    def _find_dependencies(self, config_file):
        """
        Finds dependencies (included files, referenced variables) within a configuration file.

        Args:
            config_file (str): The path to the configuration file.

        Returns:
            list: A list of config files that the given config_file depends on.

        Raises:
            Exception: A missing, unreadable, malformed, or empty file is
                raised to the caller. It is never treated as a file with no
                dependencies.
        """
        try:
            with open(config_file, 'r') as f:
                # I open the file here only to prove it is not empty, and then
                # _parse_config opens it again. Between the two reads nothing
                # checks that the file stayed the same.
                if not f.read().strip():
                    raise ValueError(f"Empty configuration file: {config_file}. Nothing was checked.")
        except FileNotFoundError:
            raise ValueError(f"File not found: {config_file}")

        config_data = self._parse_config(config_file)

        dependencies = []
        self._collect_dependencies(config_file, config_data, dependencies)
        return dependencies

    def build_dependency_graph(self):
        """
        Builds a dependency graph based on the configuration files.
        """
        for config_file in self.config_files:
            dependencies = self._find_dependencies(config_file)
            self.dependencies[config_file] = dependencies
            logging.debug(f"Dependencies for {config_file}: {dependencies}")

    def check_circular_dependencies(self):
        """
        Checks for circular dependencies in the configuration files.

        Returns:
            bool: True if circular dependencies are found, False otherwise.
        """
        # The sorter takes my mapping as given: keys are the paths as
        # they were passed in, values are the resolved paths from
        # _resolve_dependency. Where those two spellings disagree for
        # the same file, the sorter sees separate nodes and a cycle
        # through that file can slip past this check, while the missing
        # check below still passes it because the path exists on disk.
        ts = TopologicalSorter(self.dependencies)
        try:
            list(ts.static_order())  # Attempt to create a topological order
            return False # No circular dependencies found
        except CycleError as e:
            logging.error(f"Circular dependencies found: {e}")
            return True # Circular dependencies found

    def check_missing_dependencies(self):
        """
        Checks for missing dependencies in the configuration files.

        Returns:
            list: A list of missing dependency file paths.
        """
        missing_dependencies = []
        for config_file, dependencies in self.dependencies.items():
            for dependency in dependencies:
                # Three tests, and the first two mostly overlap, since after
                # build_dependency_graph the keys of self.dependencies are the
                # config files. The existence test is the one doing the real
                # work: a dependency that was never handed to me still counts
                # as present when it is on disk where the reference points.
                if dependency not in self.dependencies and dependency not in self.config_files and not os.path.exists(dependency):
                    missing_dependencies.append(dependency)
                    logging.warning(f"Missing dependency: {dependency} (required by {config_file})")
        return missing_dependencies

    def analyze(self):
        """
        Performs the dependency analysis and reports findings.

        Returns:
            bool: True when every input was checked and no issue was found,
            False when circular or missing dependencies were found. A file
            that cannot be checked raises instead.
        """
        # analyze can be called twice on one checker and the second run
        # adds to the graph the first run built instead of replacing it,
        # because build_dependency_graph never clears self.dependencies.
        # The command line path calls this once, so the stale entries
        # only appear for anyone reusing the class as a library.
        self.build_dependency_graph()

        circular_dependencies = self.check_circular_dependencies()
        missing_dependencies = self.check_missing_dependencies()

        if circular_dependencies:
            print("Error: Circular dependencies detected.")
        if missing_dependencies:
            print("Error: Missing dependencies detected:", missing_dependencies)

        if not circular_dependencies and not missing_dependencies:
            print("No dependency issues found.")
            return True
        return False


def setup_argparse():
    """
    Sets up the command-line argument parser.

    Returns:
        argparse.ArgumentParser: The argument parser.
    """
    parser = argparse.ArgumentParser(description="Identifies dependencies between configuration files.")
    parser.add_argument("config_files", nargs='+', help="List of configuration files to analyze.")
    parser.add_argument("-f", "--format", choices=['auto', 'yaml', 'json'], default='auto',
                        help="Specify the configuration file format ('yaml', 'json', or 'auto').")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging.")
    return parser


def main():
    """
    Main function to execute the configuration dependency checker.
    """
    parser = setup_argparse()
    args = parser.parse_args()

    try:
        checker = ConfigDependencyChecker(args.config_files, args.format, args.debug)
        if not checker.analyze():
            sys.exit(1)
    except ValueError as e:
        logging.error(f"Error: {e}")
        print(f"Error: Unchecked input: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error: {e}")
        print(f"Error: Unchecked input: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

# Usage Examples:
# 1. Basic usage:
#    python main.py config1.yaml config2.json
# 2. Specify the file format:
#    python main.py -f yaml config1.yaml config2.yaml
# 3. Enable debug mode:
#    python main.py -d config1.yaml config2.json
# 4. Configuration with include statements:
#   config1.yaml:
#       include: config2.yaml
#   config2.yaml:
#       value: "something"
#   Run: python main.py config1.yaml
# 5. Configuration with depends_on list:
#   config1.json:
#       depends_on: ["config2.yaml", "config3.json"]
#   config2.yaml:
#       value: "something"
#   config3.json:
#       value: "something"
#   Run: python main.py config1.json config2.yaml config3.json
# 6. Intentionally create a circular dependency:
#   config1.yaml:
#       include: config2.yaml
#   config2.yaml:
#       include: config1.yaml
#   Run: python main.py config1.yaml config2.yaml

# Offensive Tool Steps:
# 1. Fuzzing:  Supply malformed config files (e.g. very long include paths, special characters) to check for vulnerabilities.
# 2. Path Traversal: Try to include files outside the intended directory (e.g. include: ../../../etc/passwd) and check error handling.
# 3. Symbolic links:  Create symbolic links to sensitive files and include the link to check if it's followed.
# 4. Check for command injection: If any part of the configuration parsing involves executing commands, fuzz the input with shell metacharacters.
# 5.  Denial of Service:  Create a deeply nested or highly circular dependency graph that consumes excessive resources.