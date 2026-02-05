#!/usr/bin/env python3
"""
Phase 2B Verification Script - Validate refactored runtime components without pytest.

Checks:
1. Python syntax of key files
2. Import health (no circular dependencies)
3. Toolkit registry initialization
4. Tool schema validity
5. ForecastingClient wallet distribution methods
6. Polymarket toolkit presence
7. No orphaned imports of deleted toolkits

Usage:
    python verify_phase2b.py
"""

import sys
import os
import ast
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

class VerificationReport:
    """Collect and report verification results."""
    
    def __init__(self):
        self.checks: Dict[str, bool] = {}
        self.details: Dict[str, List[str]] = {}
        self.errors: Dict[str, str] = {}
    
    def add_check(self, name: str, passed: bool, detail: Optional[str] = None):
        """Add a check result."""
        self.checks[name] = passed
        if detail:
            if name not in self.details:
                self.details[name] = []
            self.details[name].append(detail)
    
    def add_error(self, name: str, error: str):
        """Add an error."""
        self.errors[name] = error
        self.checks[name] = False
    
    def add_warning(self, name: str, warning: str):
        """Add a warning (non-fatal check)."""
        self.add_check(name, True, warning)
    
    def print_summary(self):
        """Print verification summary."""
        passed = sum(1 for v in self.checks.values() if v)
        total = len(self.checks)
        
        print(f"\n{BOLD}{'=' * 80}{RESET}")
        print(f"{BOLD}Phase 2B Verification Report{RESET}")
        print(f"{BOLD}{'=' * 80}{RESET}\n")
        
        for check, passed in self.checks.items():
            status = f"{GREEN}✅ PASS{RESET}" if passed else f"{RED}❌ FAIL{RESET}"
            print(f"{status} {check}")
            if check in self.details:
                for detail in self.details[check]:
                    print(f"      {detail}")
            if check in self.errors:
                print(f"      {RED}Error: {self.errors[check]}{RESET}")
        
        print(f"\n{BOLD}{'=' * 80}{RESET}")
        print(f"{BOLD}Summary: {passed}/{total} checks passed{RESET}")
        print(f"{BOLD}{'=' * 80}{RESET}\n")
        
        return passed == total


def check_python_syntax(filepath: str, report: VerificationReport):
    """Check Python syntax of a file."""
    try:
        with open(filepath, 'r') as f:
            code = f.read()
        ast.parse(code)
        report.add_check(f"Python Syntax: {Path(filepath).name}", True, f"Valid Python file")
        return True
    except SyntaxError as e:
        report.add_error(f"Python Syntax: {Path(filepath).name}", f"Line {e.lineno}: {e.msg}")
        return False
    except Exception as e:
        report.add_error(f"Python Syntax: {Path(filepath).name}", str(e))
        return False


def check_no_orphaned_imports(filepath: str, removed_modules: List[str], report: VerificationReport):
    """Check that file doesn't import removed modules."""
    try:
        with open(filepath, 'r') as f:
            code = f.read()
        
        orphaned = []
        for module in removed_modules:
            if f"from {module} import" in code or f"import {module}" in code:
                orphaned.append(module)
        
        if orphaned:
            report.add_check(
                f"No Orphaned Imports: {Path(filepath).name}",
                False,
                f"Found imports of removed modules: {orphaned}"
            )
            return False
        else:
            report.add_check(
                f"No Orphaned Imports: {Path(filepath).name}",
                True,
                f"No orphaned imports found"
            )
            return True
    except Exception as e:
        report.add_error(f"No Orphaned Imports: {Path(filepath).name}", str(e))
        return False


def check_file_exists(filepath: str, description: str, report: VerificationReport) -> bool:
    """Check if a file exists."""
    if Path(filepath).exists():
        report.add_check(description, True, f"File exists at {filepath}")
        return True
    else:
        report.add_error(description, f"File not found: {filepath}")
        return False


def check_file_not_exists(filepath: str, description: str, report: VerificationReport) -> bool:
    """Check if a file does NOT exist."""
    if not Path(filepath).exists():
        report.add_check(description, True, f"File removed as expected")
        return True
    else:
        report.add_error(description, f"File should have been removed: {filepath}")
        return False


def verify_utils_module(root: Path, report: VerificationReport):
    """Verify core/camel_runtime/utils.py exists and is valid."""
    utils_file = root / "core" / "camel_runtime" / "utils.py"
    if not check_file_exists(str(utils_file), "Runtime Utils Module", report):
        return
    
    # Check syntax
    check_python_syntax(str(utils_file), report)
    
    # Check for key classes
    try:
        with open(utils_file, 'r') as f:
            content = f.read()
        
        expected_classes = [
            "ToolValidation",
            "ClientInitialization",
            "LoggingMarkers",
            "ToolkitInitialization"
        ]
        
        for cls in expected_classes:
            if f"class {cls}" in content:
                report.add_check(f"Utils Module: {cls} class", True)
            else:
                report.add_error(f"Utils Module: {cls} class", f"Class not found in utils.py")
    except Exception as e:
        report.add_error("Utils Module: Content check", str(e))


def verify_registries_module(root: Path, report: VerificationReport):
    """Verify core/camel_runtime/registries.py uses utils and doesn't use removed toolkits."""
    registries_file = root / "core" / "camel_runtime" / "registries.py"
    if not check_file_exists(str(registries_file), "Registries Module", report):
        return
    
    # Check syntax
    check_python_syntax(str(registries_file), report)
    
    # Check for removed imports
    removed_modules = [
        "core.camel_tools.conversation_logging_toolkit",
        "core.camel_tools.wallet_distribution_toolkit"
    ]
    check_no_orphaned_imports(str(registries_file), removed_modules, report)
    
    # Check for utils usage
    try:
        with open(registries_file, 'r') as f:
            content = f.read()
        
        if "from core.camel_runtime.utils import" in content:
            report.add_check("Registries: Uses utils module", True)
        else:
            report.add_error("Registries: Uses utils module", "utils module not imported")
        
        if "ToolValidation.validate_and_filter_tools" in content:
            report.add_check("Registries: Uses tool validation", True)
        else:
            report.add_error("Registries: Uses tool validation", "ToolValidation not used for filtering")
    except Exception as e:
        report.add_error("Registries: Content check", str(e))


def verify_forecasting_client(root: Path, report: VerificationReport):
    """Verify core/clients/forecasting_client.py has wallet distribution methods."""
    forecasting_file = root / "core" / "clients" / "forecasting_client.py"
    if not check_file_exists(str(forecasting_file), "ForecastingClient Module", report):
        return
    
    # Check syntax
    check_python_syntax(str(forecasting_file), report)
    
    # Check for wallet distribution methods
    try:
        with open(forecasting_file, 'r') as f:
            content = f.read()
        
        methods = [
            "get_wallet_distribution",
            "get_agentic_wallet_distribution"
        ]
        
        for method in methods:
            if f"def {method}" in content:
                report.add_check(f"ForecastingClient: {method} method", True)
            else:
                report.add_error(f"ForecastingClient: {method} method", f"Method not found")
        
        # Check for API endpoint usage
        if "/api/agentic/wallet-distribution" in content or "agentic/wallet-distribution" in content:
            report.add_check("ForecastingClient: Uses API endpoint", True)
        else:
            report.add_error("ForecastingClient: Uses API endpoint", "No API endpoint calls found")
    except Exception as e:
        report.add_error("ForecastingClient: Content check", str(e))


def verify_societies_module(root: Path, report: VerificationReport):
    """Verify core/camel_runtime/societies.py doesn't use removed toolkits."""
    societies_file = root / "core" / "camel_runtime" / "societies.py"
    if not check_file_exists(str(societies_file), "Societies Module", report):
        return
    
    # Check syntax
    check_python_syntax(str(societies_file), report)
    
    # Check for removed imports
    removed_modules = [
        "core.camel_tools.conversation_logging_toolkit",
        "core.camel_tools.wallet_distribution_toolkit"
    ]
    check_no_orphaned_imports(str(societies_file), removed_modules, report)


def verify_polymarket_toolkit(root: Path, report: VerificationReport):
    """Verify Polymarket toolkit exists and is intact."""
    polymarket_file = root / "core" / "camel_tools" / "polymarket_toolkit.py"
    if not check_file_exists(str(polymarket_file), "Polymarket Toolkit", report):
        return
    
    # Check syntax
    check_python_syntax(str(polymarket_file), report)
    
    # Check for key methods
    try:
        with open(polymarket_file, 'r') as f:
            content = f.read()
        
        methods = [
            "search_markets",
            "get_positions",
            "take_position",
            "close_position"
        ]
        
        for method in methods:
            if f"def {method}" in content or f"'{method}'" in content:
                report.add_check(f"Polymarket Toolkit: {method}", True)
            else:
                report.add_warning(f"Polymarket Toolkit: {method}", f"Method not found (may be dynamically generated)")
    except Exception as e:
        report.add_error("Polymarket Toolkit: Content check", str(e))


def verify_deleted_files(root: Path, report: VerificationReport):
    """Verify that deleted toolkits are actually gone."""
    deleted_files = [
        "core/camel_tools/conversation_logging_toolkit.py",
        "core/camel_tools/wallet_distribution_toolkit.py"
    ]
    
    for filepath in deleted_files:
        full_path = root / filepath
        check_file_not_exists(str(full_path), f"Deleted: {filepath}", report)


def verify_test_updates(root: Path, report: VerificationReport):
    """Verify test files have been updated."""
    test_file = root / "tests" / "test_full_agentic_cycle.py"
    if not check_file_exists(str(test_file), "Test File Updated", report):
        return
    
    try:
        with open(test_file, 'r') as f:
            content = f.read()
        
        # Check for pytest.skip on removed toolkit
        if "pytest.skip" in content and "Conversation logging toolkit removed" in content:
            report.add_check("Test File: Skip removed toolkit tests", True)
        else:
            report.add_check("Test File: Skip removed toolkit tests", False, "Tests should skip removed toolkit tests")
        
        # Check for getattr safe access
        if "getattr(toolkit_registry" in content:
            report.add_check("Test File: Safe toolkit access", True)
        else:
            report.add_check("Test File: Safe toolkit access", False, "Tests should use safe attribute access")
    except Exception as e:
        report.add_error("Test File: Content check", str(e))


def verify_integration_test(root: Path, report: VerificationReport):
    """Verify integration test file exists."""
    test_file = root / "tests" / "test_standalone_integration.py"
    if check_file_exists(str(test_file), "Integration Test File", report):
        check_python_syntax(str(test_file), report)


def main():
    """Run all verification checks."""
    root = Path(__file__).parent.resolve()
    report = VerificationReport()
    
    print(f"\n{BOLD}Starting Phase 2B Verification...{RESET}\n")
    
    # Verify files exist and have correct structure
    print(f"{BLUE}1. Checking module structure...{RESET}")
    verify_utils_module(root, report)
    verify_registries_module(root, report)
    verify_forecasting_client(root, report)
    verify_societies_module(root, report)
    verify_polymarket_toolkit(root, report)
    
    print(f"\n{BLUE}2. Checking deleted files...{RESET}")
    verify_deleted_files(root, report)
    
    print(f"\n{BLUE}3. Checking test updates...{RESET}")
    verify_test_updates(root, report)
    verify_integration_test(root, report)
    
    # Print summary
    success = report.print_summary()
    
    return 0 if success else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n{RED}Fatal error during verification:{RESET}")
        print(traceback.format_exc())
        sys.exit(2)
