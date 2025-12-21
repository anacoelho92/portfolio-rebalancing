import os

# Get the secrets content from environment variable
secrets_content = os.getenv("SECRETS_TOML")

if secrets_content:
    # Ensure directory exists
    os.makedirs(".streamlit", exist_ok=True)
    
    # Write to file
    with open(".streamlit/secrets.toml", "w") as f:
        f.write(secrets_content)
    
    print("Successfully initialized .streamlit/secrets.toml from SECRETS_TOML env var.")
else:
    print("Warning: SECRETS_TOML environment variable not found. Skipping secrets initialization.")
