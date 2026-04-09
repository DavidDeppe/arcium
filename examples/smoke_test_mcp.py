"""
Smoke test: Verify all MCP projects tools work end-to-end.

Usage:
    poetry run python examples/smoke_test_mcp.py

Prerequisites:
    - poetry install
    - python scripts/setup_vault.py
    - cp config.json.example config.json  (update vault_path)
"""
import sys
import asyncio
from pathlib import Path

# Add src to path for development use without install
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def test_projects_tools():
    """Test the full projects tools cycle."""
    from arcium.mcp.server import (
        projects__create_structure,
        projects__write_file,
        projects__check_syntax,
        projects__check_dependencies,
        projects__run_tests,
        projects__list_files
    )

    slug = "mcp-test"
    print(f"Testing projects tools with slug: {slug}")
    print("=" * 60)

    # Test 1: Create structure
    print("\n1. Creating project structure...")
    result = projects__create_structure(slug)
    print(f"   Status: {result['status']}")
    print(f"   Created files: {len(result['created_files'])} files")
    for f in result['created_files']:
        print(f"     - {f}")

    # Test 2: Write a custom Python file
    print("\n2. Writing custom Python file...")
    hello_code = 'def hello():\n    return "world"\n'
    write_result = projects__write_file(slug, "src/mcp_test/hello.py", hello_code)
    print(f"   {write_result}")

    # Test 3: Check syntax
    print("\n3. Checking Python syntax...")
    syntax_result = projects__check_syntax(slug, "src/mcp_test/hello.py")
    print(f"   Status: {syntax_result['status']}")
    if syntax_result['status'] == 'error':
        print(f"   Errors: {syntax_result['errors']}")

    # Test 4: List files
    print("\n4. Listing project files...")
    files = projects__list_files(slug)
    print(f"   Total files: {len(files)}")
    py_files = [f for f in files if f.endswith('.py')]
    print(f"   Python files: {len(py_files)}")
    for f in py_files:
        print(f"     - {f}")

    # Test 5: Check dependencies
    print("\n5. Checking dependencies...")
    dep_result = projects__check_dependencies(slug)
    print(f"   Status: {dep_result['status']}")
    if dep_result['status'] == 'ok':
        print(f"   Message: {dep_result.get('message', 'OK')}")
    else:
        print(f"   Error: {dep_result.get('message', 'Unknown error')}")

    # Test 6: Run tests
    print("\n6. Running tests...")
    test_result = projects__run_tests(slug, timeout=30)
    print(f"   Status: {test_result['status']}")
    print(f"   Exit code: {test_result['exit_code']}")
    if test_result['stdout']:
        print(f"   Output:\n{test_result['stdout']}")
    if test_result['stderr']:
        print(f"   Errors:\n{test_result['stderr']}")

    print("\n" + "=" * 60)
    print("All projects tools smoke tests completed!")
    return True


if __name__ == "__main__":
    try:
        asyncio.run(test_projects_tools())
    except Exception as e:
        print(f"Smoke test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
