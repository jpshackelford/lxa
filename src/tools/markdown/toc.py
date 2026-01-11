"""Table of Contents management for markdown documents."""

from .parser import MarkdownParser, Section


class TocManager:
    """Manages table of contents generation, updating, and removal."""

    def update(self, content: str, depth: int = 3) -> tuple[str, dict]:
        """Generate or update the table of contents.

        Args:
            content: The markdown content
            depth: Maximum heading depth to include (default 3 for ##, ###, ####)

        Returns:
            Tuple of (updated_content, observation_data)
        """
        parser = MarkdownParser()
        lines = content.split("\n")
        parser.parse_content(content)
        sections = parser.sections

        # Find existing TOC section
        toc_section = parser.get_toc_section()

        # Generate TOC content
        toc_lines = self._generate_toc_lines(sections, depth)

        if toc_section:
            # Update existing TOC
            new_lines = (
                lines[: toc_section.start_line + 1]  # Keep TOC header
                + [""]  # Blank line after header
                + toc_lines
                + [""]  # Blank line after TOC
                + lines[toc_section.end_line :]  # Rest of document
            )
            action = "updated"
        else:
            # Insert new TOC after document title
            insert_pos = self._find_toc_insert_position(lines)
            new_lines = (
                lines[:insert_pos]
                + ["## Table Of Contents", ""]
                + toc_lines
                + [""]
                + lines[insert_pos:]
            )
            action = "created"

        updated_content = "\n".join(new_lines)

        observation = {
            "command": "toc update",
            "depth": depth,
            "action": action,
            "entries": len(toc_lines),
        }

        return updated_content, observation

    def remove(self, content: str) -> tuple[str, dict]:
        """Remove the table of contents section.

        Args:
            content: The markdown content

        Returns:
            Tuple of (updated_content, observation_data)
        """
        parser = MarkdownParser()
        lines = content.split("\n")
        parser.parse_content(content)

        # Find TOC section
        toc_section = parser.get_toc_section()

        if not toc_section:
            observation = {"command": "toc remove", "result": "no_toc_found"}
            return content, observation

        # Remove TOC section and surrounding blank lines
        start_line = toc_section.start_line
        end_line = toc_section.end_line

        # Remove extra blank lines before and after TOC
        while start_line > 0 and lines[start_line - 1].strip() == "":
            start_line -= 1

        while end_line < len(lines) and lines[end_line].strip() == "":
            end_line += 1

        new_lines = lines[:start_line] + lines[end_line:]
        updated_content = "\n".join(new_lines)

        observation = {"command": "toc remove", "result": "success"}

        return updated_content, observation

    def _generate_toc_lines(self, sections: list[Section], max_depth: int) -> list[str]:
        """Generate table of contents lines.

        Args:
            sections: List of sections to include
            max_depth: Maximum heading depth to include

        Returns:
            List of TOC lines
        """
        toc_lines = []

        def add_section_to_toc(section: Section):
            # Skip TOC section itself and document title (level 1)
            if (
                section.level == 2
                and section.number is None
                and section.title.lower() in ["table of contents", "contents"]
            ):
                return

            if section.level <= max_depth and section.level >= 2:
                # Calculate indentation (level 2 = no indent, level 3 = 2 spaces, etc.)
                indent = "  " * (section.level - 2)

                # Format the TOC entry
                if section.number:
                    # Main sections (level 2) get a dot, subsections don't
                    if section.level == 2:
                        entry = f"{indent}- {section.number}. {section.title}"
                    else:
                        entry = f"{indent}- {section.number} {section.title}"
                else:
                    # Skip unnumbered sections except for special cases
                    if section.level == 2:
                        entry = f"{indent}- {section.title}"
                    else:
                        return

                toc_lines.append(entry)

            # Recursively add children
            for child in section.children:
                add_section_to_toc(child)

        for section in sections:
            add_section_to_toc(section)

        return toc_lines

    def _find_toc_insert_position(self, lines: list[str]) -> int:
        """Find the position to insert a new TOC.

        Args:
            lines: Document lines

        Returns:
            Line index where TOC should be inserted
        """
        # Insert after document title (h1) if it exists
        for i, line in enumerate(lines):
            if line.strip().startswith("# "):
                # Find next non-empty line after title
                j = i + 1
                while j < len(lines) and lines[j].strip() == "":
                    j += 1
                return j

        # If no title found, insert at beginning
        return 0

    def validate_toc(self, content: str) -> dict:
        """Validate that TOC matches current document structure.

        Args:
            content: The markdown content

        Returns:
            Validation results
        """
        parser = MarkdownParser()
        parser.parse_content(content)
        sections = parser.sections
        toc_section = parser.get_toc_section()

        if not toc_section:
            return {"valid": True, "has_toc": False, "issues": []}

        # Extract current TOC entries
        lines = content.split("\n")
        toc_lines = []
        for i in range(toc_section.start_line + 1, toc_section.end_line):
            line = lines[i]
            if line.strip().startswith("- "):
                toc_lines.append(line)

        # Generate expected TOC
        expected_toc = self._generate_toc_lines(sections, 3)

        # Compare
        missing_entries = []
        stale_entries = []

        for expected in expected_toc:
            if expected not in toc_lines:
                missing_entries.append(expected.replace("- ", ""))

        for actual in toc_lines:
            if actual not in expected_toc:
                stale_entries.append(actual.replace("- ", ""))

        is_valid = len(missing_entries) == 0 and len(stale_entries) == 0

        return {
            "valid": is_valid,
            "has_toc": True,
            "missing_entries": missing_entries,
            "stale_entries": stale_entries,
            "issues": missing_entries + stale_entries,
        }
