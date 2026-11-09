#!/usr/bin/env bash
# Installs the latest Azure DevOps MCP extension into Claude Desktop (macOS).
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/YOUR-GITHUB-USER/ado-mcp-server/main/install.sh | bash
set -euo pipefail

REPO="YOUR-GITHUB-USER/ado-mcp-server"
URL="https://github.com/$REPO/releases/latest/download/ado-mcp-server.mcpb"
FILE="$HOME/Downloads/ado-mcp-server.mcpb"

echo "Azure DevOps MCP - installer for Claude Desktop"
echo "Downloading latest version..."
if ! curl -fsSL -o "$FILE" "$URL"; then
  echo "Download failed. Get it manually from: https://github.com/$REPO/releases/latest"
  exit 1
fi
echo "Saved to: $FILE"

if [ -d "/Applications/Claude.app" ] || [ -d "$HOME/Applications/Claude.app" ]; then
  open -a "Claude" "$FILE"
  echo "The installer opened in Claude Desktop. Fill in the form:"
  echo "  - Server URL: https://server/Collection  or  https://dev.azure.com/YourOrg"
  echo "  - Personal Access Token, Access level: read (recommended to start)"
else
  echo "Claude Desktop not found. Install it from https://claude.ai/download, then open:"
  echo "  $FILE"
  open -R "$FILE" || true
fi
