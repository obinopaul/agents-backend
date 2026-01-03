#!/bin/bash
# inject-skills.sh - Injects a skill folder's contents into workspace
#
# This script copies the CONTENTS of a skill folder (not the folder itself)
# into /workspace/.deepagents/skills/, creating a flat structure where
# each skill subfolder is directly under .deepagents/skills/
#
# Usage: inject-skills.sh <skill_folder>
# Examples:
#   inject-skills.sh basic           # Injects general skills
#   inject-skills.sh scientific_skills  # Injects scientific research skills
#   inject-skills.sh scientific_writer  # Injects academic writing skills
#
# Exit codes:
#   0 - Success
#   1 - Skill folder not found

set -e

SKILLS_SOURCE="/app/skills"
SKILLS_TARGET="/workspace/.deepagents/skills"
SKILL_FOLDER="${1:-basic}"  # Default to 'basic' if not specified

SOURCE_DIR="$SKILLS_SOURCE/$SKILL_FOLDER"

# Validate source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Error: Skill folder '$SKILL_FOLDER' not found at $SOURCE_DIR"
    echo "Available skill folders:"
    ls -la "$SKILLS_SOURCE" 2>/dev/null || echo "  (skills source not found)"
    exit 1
fi

# Create target directory with proper structure
mkdir -p "$SKILLS_TARGET"

# Copy contents (not the folder itself) to target - FLAT structure
# The /* glob copies all subdirectories from the skill folder
echo "Injecting skills from: $SKILL_FOLDER"
echo "Source: $SOURCE_DIR"
echo "Target: $SKILLS_TARGET"

# Count items before copy
ITEM_COUNT=$(ls -1 "$SOURCE_DIR" 2>/dev/null | wc -l)
echo "Copying $ITEM_COUNT skill items..."

# Use cp -r to recursively copy all contents
# The trailing /* ensures we copy contents, not the folder itself
cp -r "$SOURCE_DIR"/* "$SKILLS_TARGET/"

# Fix permissions for pn user (sandbox runtime user)
chown -R pn:pn /workspace/.deepagents 2>/dev/null || true
chmod -R 755 /workspace/.deepagents

echo ""
echo "Skills injected successfully to $SKILLS_TARGET"
echo ""
echo "Injected skills (first 20):"
ls -1 "$SKILLS_TARGET" 2>/dev/null | head -20

# Show total count
INJECTED_COUNT=$(ls -1 "$SKILLS_TARGET" 2>/dev/null | wc -l)
echo ""
echo "Total skills injected: $INJECTED_COUNT"
