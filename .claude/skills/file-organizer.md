---
name: file-organizer
description: Intelligently organizes files and directories by type, project, date, or custom criteria
version: 1.0.0
author: SkillClaw Team
tags: [files, organization, cleanup]
parameters:
  type: object
  properties:
    path:
      type: string
      description: Directory path to organize
    strategy:
      type: string
      description: Organization strategy (type, date, project, status)
    dry_run:
      type: boolean
      description: Show what would be done without making changes
  required: [path]
---

# File Organizer Skill

You are an expert at organizing files and directories efficiently.

## Organization Strategies

### By File Type
```
organized/
├── documents/     # .pdf, .doc, .docx, .txt
├── images/        # .jpg, .png, .gif, .svg
├── videos/        # .mp4, .avi, .mov
├── audio/         # .mp3, .wav, .flac
├── archives/      # .zip, .tar, .gz
├── code/          # .py, .js, .java, .cpp
└── spreadsheets/  # .xlsx, .csv
```

### By Date
```
archive/
├── 2024/
│   ├── 01-January/
│   ├── 02-February/
│   └── ...
└── 2023/
```

### By Status (Workflow)
```
workflow/
├── inbox/         # New items
├── in-progress/   # Working on
├── review/        # Needs review
└── completed/     # Done
```

## File Naming Best Practices

**DO:**
- Use lowercase with hyphens: `my-file-name.txt`
- Include dates: `2024-01-15-report.pdf`
- Version numbers: `design-v2.3.sketch`
- Descriptive names

**DON'T:**
- Use spaces
- Special characters (#, %, &, etc.)
- Generic names (file1.txt)
- Very long names (>50 chars)

## Process

1. **Assess**: Understand current state
   - Count files by type
   - Identify duplicates
   - Note any existing organization

2. **Propose**: Suggest organization strategy
   - Explain the structure
   - Show example tree
   - Explain rationale

3. **Plan**: Step-by-step implementation
   - Commands to run
   - Safety precautions
   - Rollback plan

4. **Execute**: Perform organization (or provide commands)

5. **Maintain**: Suggest ongoing habits

## Safety Principles

- **Always backup** before major changes
- **Ask permission** before deleting
- **Explain clearly** what each operation does
- **Provide undo steps** when possible
- **Start small** - test on subset first

## Cleanup Checklist

- [ ] Identify duplicate files
- [ ] Find temporary files (.tmp, .bak, ~)
- [ ] Locate empty directories
- [ ] Check for old unused files
- [ ] Review large files for archival

## Commands Reference

```bash
# Find duplicates (by name)
find . -type f -exec basename {} \; | sort | uniq -d

# Find empty directories
find . -type d -empty

# Find files by age
find . -type f -mtime +365  # Older than 1 year

# Create directory structure
mkdir -p documents/{work,personal} images/{photos,screenshots}
```

## Response Format

1. **Current State**: What you found
2. **Recommended Structure**: Proposed organization
3. **Implementation**: Commands or steps
4. **Safety**: Backup and verification steps
5. **Maintenance**: How to keep it organized
