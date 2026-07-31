import importlib.metadata

packages = [
    "langchain",
    "langchain_core",
    "python-dotenv",
    "langchain_mcp_adapters",
    "mcp"
]

for pkg in packages:
    try:
        version = importlib.metadata.version(pkg)
        print(f"{pkg}: {version}")
    except importlib.metadata.PackageNotFoundError:
        print(f"{pkg}: Not installed")
