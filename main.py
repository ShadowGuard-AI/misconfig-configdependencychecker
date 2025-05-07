import argparse
import logging
import os
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

    def _find_dependencies(self, config_file):
        """
        Finds dependencies (included files, referenced variables) within a configuration file.

        Args:
            config_file (str): The path to the configuration file.

        Returns:
            list: A list of config files that the given config_file depends on.
            Returns an empty list if no dependencies are found or the file cannot be parsed.
        """

        dependencies = []
        try:
            config_data = self._parse_config(config_file)
        except Exception as e:
            logging.error(f"Error processing {config_file}: {e}")
            return [] # Return empty list in case of error

        # This is a basic example and needs to be adapted based on specific config file structure
        # and the method of including files or referencing variables.
        # Replace 'include' and 'depends_on' with actual keys used in your configuration files.
        if isinstance(config_data, dict):
            if 'include' in config_data and isinstance(config_data['include'], str):
                include_path = config_data['include']
                # Resolve relative paths relative to the current config file's directory
                include_path = os.path.join(os.path.dirname(config_file), include_path)
                dependencies.append(include_path)
            elif 'depends_on' in config_data and isinstance(config_data['depends_on'], list):
                for dep in config_data['depends_on']:
                    dep_path = dep
                    # Resolve relative paths relative to the current config file's directory
                    dep_path = os.path.join(os.path.dirname(config_file), dep_path)
                    dependencies.append(dep_path)

        return dependencies

    def build_dependency_graph(self):
        """
        Builds a dependency graph based on the configuration files.
        """
        for config_file in self.config_files:
            try:
                dependencies = self._find_dependencies(config_file)
                self.dependencies[config_file] = dependencies
                logging.debug(f"Dependencies for {config_file}: {dependencies}")
            except Exception as e:
                logging.error(f"Error building dependency graph for {config_file}: {e}")

    def check_circular_dependencies(self):
        """
        Checks for circular dependencies in the configuration files.

        Returns:
            bool: True if circular dependencies are found, False otherwise.
        """
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
                if dependency not in self.dependencies and dependency not in self.config_files and not os.path.exists(dependency):
                    missing_dependencies.append(dependency)
                    logging.warning(f"Missing dependency: {dependency} (required by {config_file})")
        return missing_dependencies

    def analyze(self):
        """
        Performs the dependency analysis and reports findings.
        """
        self.build_dependency_graph()

        circular_dependencies = self.check_circular_dependencies()
        missing_dependencies = self.check_missing_dependencies()

        if circular_dependencies:
            print("Error: Circular dependencies detected.")
        if missing_dependencies:
            print("Error: Missing dependencies detected:", missing_dependencies)

        if not circular_dependencies and not missing_dependencies:
            print("No dependency issues found.")


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
        checker.analyze()
    except ValueError as e:
        logging.error(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.exception("An unexpected error occurred:")
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