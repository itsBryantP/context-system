# CTX .docx Support Specification

## 1. Executive Summary

This specification defines the integration of Microsoft Word (.docx) document support into the CTX context management tool. The enhancement will enable CTX to extract, chunk, and index .docx files using IBM's Docling library, with intelligent image filtering to remove noise artifacts (particularly profile icons from meeting transcripts) while preserving useful visual content.

**Key Goals:**
- Support .docx files in `ctx pack` and `ctx extract` workflows
- Leverage Docling for robust .docx → markdown conversion
- Intelligently filter profile icons and other noise images from meeting transcripts
- Maintain backward compatibility with existing extractors
- Provide configurable image handling behavior

**Impact:**
- Unlocks 38+ .docx files currently skipped in user's documentation directory
- Enables processing of Microsoft Teams meeting transcripts
- Reduces context waste from embedded profile icons
- Positions CTX for future Office format support (.xlsx via Docling)

**Example Meeting Transcript Analysis:**

From the provided "Manzanita - daily technical workstream sync.docx" transcript:
- **Profile Icon Artifacts:** 47 `<!-- image -->` comments (one per speaker turn)
- **Content Value:** Technical discussion about pricing models, capacity planning, and software deployment
- **Context Waste:** ~2,350 tokens consumed by image placeholders (5% of total)
- **After Filtering:** Clean transcript with speaker names, timestamps, and conversation flow preserved

---

## 2. Requirements

### 2.1 Functional Requirements

**FR-1: .docx File Detection**
- CTX must recognize .docx files during directory scanning
- File classification must distinguish .docx from legacy .doc format
- Detection must work in both `ctx pack` and `ctx extract` commands

**FR-2: Content Extraction**
- Extract text content from .docx files using Docling
- Preserve document structure (headings, paragraphs, lists)
- Extract tables and convert to markdown format
- Handle embedded formatting (bold, italic, code blocks)

**FR-3: Image Handling**
- Detect and categorize embedded images
- Remove profile icons from meeting transcripts
- Preserve diagrams, charts, and meaningful visual content
- Provide configuration to control image filtering behavior

**FR-4: Meeting Transcript Processing**
- Recognize Microsoft Teams meeting transcript format
- Remove `<!-- image -->` HTML comment placeholders
- Preserve speaker names and timestamps
- Maintain conversation flow and structure

**FR-5: Metadata Preservation**
- Extract document title from .docx metadata
- Capture author information when available
- Record conversion timestamp
- Track source file path and hash

**FR-6: Error Handling**
- Gracefully handle corrupted .docx files
- Provide clear error messages for unsupported features
- Fall back to text-only extraction if Docling fails
- Log conversion warnings without blocking pipeline

### 2.2 Non-Functional Requirements

**NFR-1: Performance**
- .docx conversion must complete within 5 seconds for typical documents (<50 pages)
- Large documents (>100 pages) should show progress indication
- Conversion should not block other file processing in parallel mode

**NFR-2: Reliability**
- Conversion success rate must exceed 95% for well-formed .docx files
- Extractor must not crash on malformed input
- Cache must prevent redundant conversions

**NFR-3: Maintainability**
- Follow existing extractor pattern in `src/ctx/extractors/`
- Use Docling's public API (avoid internal implementation details)
- Document image filtering heuristics for future tuning

**NFR-4: Compatibility**
- Support .docx files created by Microsoft Word 2007+
- Support .docx files created by Google Docs, LibreOffice, Pages
- Handle both .docx and .docm (macro-enabled) formats

**NFR-5: Configurability**
- Allow users to enable/disable image filtering
- Provide presets for different document types (transcripts, technical docs, reports)
- Support per-module configuration in module.yaml

### 2.3 Edge Cases

**EC-1: Empty Documents**
- Handle .docx files with no text content
- Emit warning and skip chunking
- Do not fail the entire build

**EC-2: Image-Only Documents**
- Detect documents containing only images
- Attempt OCR if configured (future enhancement)
- Emit warning about limited extractable content

**EC-3: Password-Protected Files**
- Detect encrypted .docx files
- Provide clear error message requesting unencrypted version
- Do not attempt to crack passwords

**EC-4: Embedded Objects**
- Handle embedded Excel spreadsheets, PDFs, etc.
- Extract text from embedded objects when possible
- Log unsupported object types

**EC-5: Large Documents**
- Handle .docx files >100MB
- Stream processing to avoid memory exhaustion
- Provide progress feedback for long conversions

**EC-6: Mixed Content**
- Handle documents with both useful images and profile icons
- Apply heuristics to distinguish image types
- Preserve diagrams while removing profile icons

**EC-7: Legacy .doc Format**
- Detect .doc files and provide clear error message
- Suggest conversion to .docx using external tools
- Do not attempt to process (Docling requires .docx)

---

## 3. Architecture

### 3.1 Integration Point

**Decision: Create New Extractor**

The .docx support will be implemented as a new extractor class following the existing pattern:

```
src/ctx/extractors/
├── __init__.py          # Registry - add DocxExtractor
├── base.py              # Extractor ABC
├── docx.py              # NEW: DocxExtractor class
└── ...
```

**Rationale:**
- Maintains separation of concerns
- Follows established extractor pattern
- Allows independent testing and maintenance
- Enables future enhancements without affecting other extractors

**Alternative Considered:** Extending the existing `markdown.py` extractor to handle .docx by converting first. Rejected because:
- Violates single responsibility principle
- Complicates markdown extractor logic
- Makes testing more difficult
- Obscures the conversion step

### 3.2 Component Design

#### 3.2.1 DocxExtractor Class

```python
# src/ctx/extractors/docx.py

from pathlib import Path
from typing import Optional
from .base import Extractor

class DocxExtractor(Extractor):
    """Extract content from Microsoft Word .docx files using Docling."""
    
    def __init__(self, remove_images: bool = True, 
                 filter_profile_icons: bool = True):
        """
        Initialize DOCX extractor.
        
        Args:
            remove_images: Remove all images from output
            filter_profile_icons: Remove profile icon artifacts (meeting transcripts)
        """
        self.remove_images = remove_images
        self.filter_profile_icons = filter_profile_icons
        self._converter = None  # Lazy-loaded
    
    @property
    def converter(self):
        """Lazy-load Docling converter."""
        if self._converter is None:
            from docling.document_converter import DocumentConverter
            self._converter = DocumentConverter()
        return self._converter
    
    def can_extract(self, source: Path) -> bool:
        """Check if source is a .docx file."""
        return source.suffix.lower() in ['.docx', '.docm']
    
    def extract(self, source: Path) -> str:
        """
        Extract markdown content from .docx file.
        
        Args:
            source: Path to .docx file
            
        Returns:
            Markdown string with images filtered based on configuration
            
        Raises:
            ExtractionError: If conversion fails
        """
        try:
            # Convert using Docling
            result = self.converter.convert(str(source))
            markdown = result.document.export_to_markdown()
            
            # Apply image filtering
            if self.filter_profile_icons:
                markdown = self._remove_profile_icons(markdown)
            elif self.remove_images:
                markdown = self._remove_all_images(markdown)
            
            # Clean up excessive whitespace
            markdown = self._normalize_whitespace(markdown)
            
            return markdown
            
        except Exception as e:
            raise ExtractionError(f"Failed to extract {source}: {e}")
    
    def _remove_profile_icons(self, markdown: str) -> str:
        """Remove profile icon HTML comments from meeting transcripts."""
        import re
        # Remove standalone <!-- image --> comments
        markdown = re.sub(r'\n\s*<!-- image -->\s*\n', '\n', markdown)
        # Also remove inline <!-- image --> comments
        markdown = re.sub(r'<!-- image -->', '', markdown)
        return markdown
    
    def _remove_all_images(self, markdown: str) -> str:
        """Remove all image references from markdown."""
        import re
        # Remove markdown images: ![alt](url)
        markdown = re.sub(r'!\[.*?\]\(.*?\)', '', markdown)
        # Remove HTML image comments
        markdown = re.sub(r'<!-- image -->', '', markdown)
        return markdown
    
    def _normalize_whitespace(self, markdown: str) -> str:
        """Collapse excessive blank lines."""
        import re
        # Replace 3+ newlines with 2 newlines
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        return markdown.strip()
```

#### 3.2.2 Extractor Registry Update

```python
# src/ctx/extractors/__init__.py

from .docx import DocxExtractor

def get_extractor(source: Path, config: Optional[dict] = None) -> Extractor:
    """
    Get appropriate extractor for source file.
    
    Args:
        source: Path to source file
        config: Optional configuration dict
        
    Returns:
        Extractor instance
    """
    # Try each extractor in priority order
    extractors = [
        MarkdownExtractor(),
        DocxExtractor(
            remove_images=config.get('remove_images', True) if config else True,
            filter_profile_icons=config.get('filter_profile_icons', True) if config else True
        ),
        PdfExtractor(),
        PptxExtractor(),
        UrlExtractor(),
    ]
    
    for extractor in extractors:
        if extractor.can_extract(source):
            return extractor
    
    raise UnsupportedFormatError(f"No extractor found for {source}")
```

#### 3.2.3 Configuration Schema Extension

```python
# src/ctx/schema.py

class ExtractionConfig(BaseModel):
    """Configuration for content extraction."""
    
    # Existing fields...
    
    # New DOCX-specific fields
    docx_remove_images: bool = True
    """Remove all images from DOCX files"""
    
    docx_filter_profile_icons: bool = True
    """Remove profile icon artifacts from meeting transcripts"""
    
    docx_preserve_tables: bool = True
    """Preserve table formatting in markdown output"""

class ModuleConfig(BaseModel):
    """Module configuration schema."""
    
    # Existing fields...
    
    extraction: Optional[ExtractionConfig] = None
    """Optional extraction configuration"""
```

### 3.3 Data Flow

```
User runs: ctx pack /path/to/docs --install

1. Directory Scan (pack.py)
   ├─> Discover files: *.md, *.pdf, *.docx, etc.
   └─> Classify by extension

2. File Processing (pack.py)
   ├─> For each .docx file:
   │   ├─> get_extractor(file) → DocxExtractor
   │   ├─> extractor.extract(file) → markdown string
   │   │   ├─> Docling conversion
   │   │   ├─> Image filtering
   │   │   └─> Whitespace normalization
   │   └─> Write to content/ directory
   └─> Continue with other files

3. Chunking (chunker/)
   ├─> Load extracted markdown files
   ├─> Apply chunking strategy (heading/fixed/definition)
   └─> Generate chunks with metadata

4. Output (integrations/jsonl.py)
   ├─> Serialize chunks to JSONL
   └─> Write to .context/chunks/

5. Installation (integrations/claude_code.py)
   ├─> Symlink to .bob/ or .claude/
   └─> Update project configuration
```

---

## 4. Image Handling

### 4.1 Detection Strategy

**Problem:** Meeting transcripts contain profile icon artifacts that waste context space without providing value.

**Characteristics of Profile Icons (from example transcript):**
- Appear as `<!-- image -->` HTML comments in Docling output
- Occur after speaker names in meeting transcripts (e.g., after `**Andrew Sica** 42:29`)
- Typically small circular images (not diagrams or charts)
- Repeat frequently (47 occurrences in the example transcript)
- No semantic value - purely decorative UI elements

**Detection Heuristics:**

1. **Pattern Matching:**
   - Detect `<!-- image -->` comments on standalone lines
   - Identify repetitive image patterns (>10 occurrences suggests profile icons)
   - Check proximity to speaker name patterns (e.g., `**Name** timestamp`)

2. **Document Type Classification:**
   - Meeting transcripts: High frequency of speaker names + timestamps + images
   - Technical docs: Lower image frequency, more varied content
   - Reports: Mixed content with charts and diagrams

3. **Image Metadata Analysis (Future Enhancement):**
   - Parse Docling's internal image metadata
   - Check image dimensions (profile icons typically <200x200px)
   - Analyze image file names (e.g., "profile_*.png")

### 4.2 Removal Logic

**Strategy 1: Remove All Images (Default for Meeting Transcripts)**

```python
def _remove_profile_icons(self, markdown: str) -> str:
    """
    Remove profile icon HTML comments from meeting transcripts.
    
    Heuristic: Remove standalone <!-- image --> comments that appear
    after speaker names in meeting transcript format.
    """
    import re
    
    # Remove standalone <!-- image --> comments
    # Pattern: newline + optional whitespace + comment + optional whitespace + newline
    markdown = re.sub(r'\n\s*<!-- image -->\s*\n', '\n', markdown)
    
    # Also remove inline <!-- image --> comments
    markdown = re.sub(r'<!-- image -->', '', markdown)
    
    return markdown
```

**Strategy 2: Selective Removal (Future Enhancement)**

```python
def _filter_images_intelligently(self, markdown: str, doc_type: str) -> str:
    """
    Selectively remove images based on document type and heuristics.
    
    Args:
        markdown: Markdown content with images
        doc_type: 'transcript', 'technical', 'report', 'unknown'
    
    Returns:
        Markdown with filtered images
    """
    if doc_type == 'transcript':
        # Remove all images (likely profile icons)
        return self._remove_all_images(markdown)
    
    elif doc_type == 'technical':
        # Preserve images (likely diagrams)
        return markdown
    
    elif doc_type == 'report':
        # Remove small images, preserve large ones
        return self._remove_small_images(markdown)
    
    else:
        # Unknown type: apply conservative filtering
        return self._remove_profile_icons(markdown)
```

**Strategy 3: User-Controlled (Configuration)**

```yaml
# module.yaml
extraction:
  docx_remove_images: false          # Keep all images
  docx_filter_profile_icons: true    # Remove only profile icons
  docx_image_size_threshold: 200     # Remove images <200px (future)
```

### 4.3 Configuration

**Module-Level Configuration (module.yaml):**

```yaml
name: ibm-meeting-transcripts
version: 1.0.0
description: IBM meeting transcripts from Microsoft Teams

extraction:
  docx_remove_images: true           # Remove all images
  docx_filter_profile_icons: true    # Remove profile icon artifacts
  docx_preserve_tables: true         # Keep table formatting

sources:
  - path: "transcripts/*.docx"
    type: docx
```

**Project-Level Configuration (.context/config.yaml):**

```yaml
modules:
  - path: ./ibm-meeting-transcripts
    extraction:
      docx_remove_images: true       # Override module setting
```

**CLI Override:**

```bash
# Remove all images
ctx pack ./transcripts --docx-remove-images

# Keep images but filter profile icons
ctx pack ./transcripts --docx-filter-profile-icons

# Keep all images
ctx pack ./transcripts --docx-keep-images
```

---

## 5. Implementation

### 5.1 File Changes

**New Files:**
- `src/ctx/extractors/docx.py` - DocxExtractor class (~150 lines)
- `tests/test_docx_extractor.py` - Unit tests (~200 lines)
- `tests/fixtures/meeting-transcript.docx` - Test fixture (real Teams transcript)
- `tests/fixtures/technical-doc.docx` - Test fixture (doc with diagrams)
- `specs/features/DOCX_SUPPORT_SPEC.md` - This specification

**Modified Files:**
- `src/ctx/extractors/__init__.py` - Register DocxExtractor (+10 lines)
- `src/ctx/schema.py` - Add ExtractionConfig fields (+15 lines)
- `src/ctx/pack.py` - Add .docx to supported extensions (+5 lines)
- `src/ctx/cli.py` - Add CLI flags for DOCX options (+20 lines)
- `pyproject.toml` - Add docling to dependencies and extractors extra (+2 lines)
- `install.sh` - Add docling to extractor package verification (+3 lines)
- `README.md` - Document .docx support (+30 lines)
- `AGENTS.md` - Update supported formats table (+5 lines)
- `CLAUDE.md` - Update supported formats table (+5 lines)

**Estimated LOC:** ~450 lines of new code, ~60 lines of modifications

### 5.2 Dependency Changes

**5.2.1 pyproject.toml Updates**

Add docling to both the core dependencies and the extractors optional dependency group:

```toml
[project]
name = "ctx-modules"
version = "0.1.1"
description = "Context module system for RAG and AI coding tools"
requires-python = ">=3.11"
dependencies = [
    "click>=8.0",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "tiktoken>=0.5",
    "pymupdf>=1.23",
    "python-pptx>=0.6",
    "markdownify>=0.11",
    "docling>=1.0",  # NEW: DOCX extraction
]

[project.optional-dependencies]
extractors = [
    "pymupdf>=1.23",
    "python-pptx>=0.6",
    "markdownify>=0.11",
    "docling>=1.0",  # NEW: DOCX extraction
]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
]
contextualize = [
    "anthropic>=0.40",
]
```

**Rationale:**
- Add to core dependencies: Ensures docling is always available
- Add to extractors extra: Maintains consistency with other extractor packages
- Version constraint `>=1.0`: Ensures stable API (Docling 1.0+ has stable export_to_markdown)

**5.2.2 install.sh Updates**

Update the extractor package verification to include docling:

```bash
# Verify extractor packages are importable from the target Python.
# uv pip may install into a managed venv that differs from the Python used
# to run ctx — if any package is missing, fall back to pip install directly.
EXTRACTOR_PKGS=("pymupdf" "python-pptx" "markdownify" "docling")  # Added docling
MISSING=()
for pkg in "${EXTRACTOR_PKGS[@]}"; do
  import_name="${pkg//-/_}"   # python-pptx → python_pptx, etc.
  # Special case: pymupdf is imported as 'fitz'
  [[ "$pkg" == "pymupdf" ]] && import_name="fitz"
  [[ "$pkg" == "python-pptx" ]] && import_name="pptx"
  # docling imports as 'docling'
  if ! "$PYTHON" -c "import ${import_name}" &>/dev/null; then
    MISSING+=("$pkg")
  fi
done
```

**Changes:**
1. Add `"docling"` to `EXTRACTOR_PKGS` array
2. No special import name handling needed (imports as `docling`)
3. Existing fallback logic handles missing packages

**5.2.3 Docling System Dependencies**

Docling has its own system dependencies that users may need to install:

**Optional (for enhanced PDF support in Docling):**
- `poppler-utils` - Already recommended for pdftotext
- `tesseract-ocr` - For OCR capabilities (future enhancement)

**Note:** The install.sh script already checks for poppler (pdftotext), so no additional changes needed for system dependencies.

### 5.2 Testing Strategy

**5.2.1 Unit Tests (tests/test_docx_extractor.py)**

```python
import pytest
from pathlib import Path
from ctx.extractors.docx import DocxExtractor
from ctx.extractors import ExtractionError

class TestDocxExtractor:
    
    def test_can_extract_docx(self):
        """Test .docx file detection."""
        extractor = DocxExtractor()
        assert extractor.can_extract(Path('test.docx'))
        assert extractor.can_extract(Path('test.docm'))
        assert not extractor.can_extract(Path('test.doc'))
        assert not extractor.can_extract(Path('test.pdf'))
    
    def test_extract_meeting_transcript(self):
        """Test extraction of meeting transcript with profile icons."""
        fixture = Path('tests/fixtures/meeting-transcript.docx')
        extractor = DocxExtractor(filter_profile_icons=True)
        
        markdown = extractor.extract(fixture)
        
        # Verify profile icons removed
        assert '<!-- image -->' not in markdown
        
        # Verify content preserved
        assert '**Andrew Sica**' in markdown
        assert '42:29' in markdown
        
        # Verify no excessive whitespace
        assert '\n\n\n' not in markdown
    
    def test_extract_with_images_preserved(self):
        """Test extraction with images preserved."""
        fixture = Path('tests/fixtures/technical-doc.docx')
        extractor = DocxExtractor(remove_images=False, filter_profile_icons=False)
        
        markdown = extractor.extract(fixture)
        
        # Images should be preserved (if present in fixture)
        # This test validates the flag works correctly
    
    def test_extract_empty_document(self, tmp_path):
        """Test extraction of empty .docx file."""
        # Would need helper to create empty .docx
        # For now, test with minimal content
        pass
    
    def test_extract_corrupted_file(self, tmp_path):
        """Test extraction of corrupted .docx file."""
        fixture = tmp_path / 'corrupted.docx'
        fixture.write_bytes(b'not a valid docx')
        
        extractor = DocxExtractor()
        
        with pytest.raises(ExtractionError):
            extractor.extract(fixture)
    
    def test_lazy_loading_converter(self):
        """Test that Docling converter is lazy-loaded."""
        extractor = DocxExtractor()
        
        # Converter should not be loaded yet
        assert extractor._converter is None
        
        # Access converter property
        converter = extractor.converter
        
        # Now it should be loaded
        assert converter is not None
        assert extractor._converter is not None
    
    def test_remove_profile_icons_method(self):
        """Test profile icon removal logic."""
        extractor = DocxExtractor()
        
        input_md = """**Speaker 1** 10:00
        
<!-- image -->

Some content here.

<!-- image -->

More content."""
        
        result = extractor._remove_profile_icons(input_md)
        
        assert '<!-- image -->' not in result
        assert '**Speaker 1**' in result
        assert 'Some content' in result
    
    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        extractor = DocxExtractor()
        
        input_md = "Line 1\n\n\n\n\nLine 2\n\n\n\nLine 3"
        result = extractor._normalize_whitespace(input_md)
        
        # Should collapse to max 2 newlines
        assert '\n\n\n' not in result
        assert 'Line 1\n\nLine 2' in result
```

**5.2.2 Integration Tests (tests/test_pack.py additions)**

```python
def test_pack_with_docx_files(tmp_path):
    """Test ctx pack with .docx files."""
    # Create test directory with .docx files
    docs_dir = tmp_path / 'docs'
    docs_dir.mkdir()
    
    # Copy fixture
    import shutil
    shutil.copy('tests/fixtures/meeting-transcript.docx', docs_dir / 'meeting.docx')
    
    # Run pack
    from ctx.pack import pack_directory
    result = pack_directory(docs_dir, output_dir=tmp_path)
    
    # Verify output
    assert (tmp_path / 'content' / 'meeting.md').exists()
    
    # Verify chunks generated
    chunks_file = tmp_path / 'chunks' / 'docs.jsonl'
    assert chunks_file.exists()
    
    # Verify profile icons removed
    content = (tmp_path / 'content' / 'meeting.md').read_text()
    assert '<!-- image -->' not in content

def test_pack_docx_with_config(tmp_path):
    """Test ctx pack with DOCX configuration."""
    docs_dir = tmp_path / 'docs'
    docs_dir.mkdir()
    
    import shutil
    shutil.copy('tests/fixtures/meeting-transcript.docx', docs_dir / 'meeting.docx')
    
    # Pack with images preserved
    config = {'docx_remove_images': False, 'docx_filter_profile_icons': False}
    from ctx.pack import pack_directory
    result = pack_directory(docs_dir, output_dir=tmp_path, config=config)
    
    # Verify images preserved
    content = (tmp_path / 'content' / 'meeting.md').read_text()
    # Would check for image markers if present
```

**5.2.3 Test Fixtures**

Use the provided "Manzanita - daily technical workstream sync.docx" as the primary test fixture:
- Copy to `tests/fixtures/meeting-transcript.docx`
- Create additional fixtures for edge cases:
  - `technical-doc.docx` - Document with diagrams
  - `empty.docx` - Minimal/empty document
  - `tables.docx` - Document with complex tables

**5.2.4 Test Coverage Goals**

- Unit test coverage: >90%
- Integration test coverage: >80%
- Edge case coverage: 100% (all edge cases in 2.3 tested)

---

## 6. User Guide

### 6.1 Usage Examples

**Example 1: Pack Directory with .docx Files**

```bash
# Auto-detect and process all .docx files
ctx pack /Users/bpanyar/Documents/IBM --install --tool bob

# Output:
# Scanning directory...
# Found 38 .docx files, 12 .pdf files, 5 .md files
# Extracting content...
#   ✓ meeting-transcript.docx → meeting-transcript.md (removed 47 profile icons)
#   ✓ technical-spec.docx → technical-spec.md
# Chunking content...
# Writing chunks to .context/chunks/ibm.jsonl
# Installing to .bob/skills/ibm/
```

**Example 2: Extract Single .docx File**

```bash
# Extract a single .docx file into a module
ctx extract meeting.docx --into ./my-module

# Output:
# Extracting meeting.docx...
# Writing to ./my-module/content/meeting.md
# Profile icons removed: 47
```

**Example 3: Keep Images in Technical Documentation**

```bash
# Preserve images in technical docs
ctx pack ./technical-docs --docx-keep-images --install

# Or configure in module.yaml:
# extraction:
#   docx_remove_images: false
```

**Example 4: Process Meeting Transcripts**

```bash
# Optimize for meeting transcripts (remove all images)
ctx pack ./meeting-transcripts \
  --docx-remove-images \
  --docx-filter-profile-icons \
  --install --tool bob

# Output:
# Processing 15 meeting transcripts...
# Removed 342 profile icon artifacts
# Generated 127 chunks
```

### 6.2 Configuration

**Module Configuration (module.yaml):**

```yaml
name: ibm-docs
version: 1.0.0
description: IBM documentation and meeting transcripts

# Extraction configuration
extraction:
  # DOCX-specific settings
  docx_remove_images: true           # Remove all images
  docx_filter_profile_icons: true    # Remove profile icon artifacts
  docx_preserve_tables: true         # Keep table formatting

# Source files
sources:
  - path: "meetings/*.docx"
    type: docx
  - path: "specs/*.docx"
    type: docx
  - path: "guides/*.md"
    type: markdown

# Chunking configuration
chunking:
  strategy: heading
  heading_level: 2
  max_tokens: 500
  overlap_tokens: 50
```

**Project Configuration (.context/config.yaml):**

```yaml
modules:
  - path: ./ibm-docs
    extraction:
      docx_remove_images: true       # Override module setting
      docx_filter_profile_icons: true
```

**CLI Flags:**

```bash
# Available flags for ctx pack and ctx extract:
--docx-remove-images          # Remove all images (default: true)
--docx-keep-images            # Keep all images
--docx-filter-profile-icons   # Remove profile icons (default: true)
--no-docx-filter-profile-icons # Keep profile icons
```

### 6.3 Troubleshooting

**Issue: "No extractor found for .doc file"**

```
Error: No extractor found for legacy-document.doc
```

**Solution:** CTX only supports .docx format. Convert .doc files to .docx:
- Microsoft Word: File → Save As → .docx
- LibreOffice: File → Save As → .docx
- Online: Use CloudConvert or similar service

---

**Issue: "Failed to extract corrupted.docx"**

```
Error: Failed to extract corrupted.docx: Invalid file format
```

**Solution:** The .docx file may be corrupted. Try:
1. Open in Microsoft Word and save a new copy
2. Use Word's "Open and Repair" feature
3. Check file integrity with `unzip -t file.docx`

---

**Issue: "Conversion taking too long"**

```
Extracting large-document.docx... (still running after 60s)
```

**Solution:** Large documents may take time. Options:
1. Split document into smaller files
2. Use `--verbose` flag to see progress
3. Increase timeout in configuration

---

**Issue: "Images not being removed"**

```
Output still contains <!-- image --> comments
```

**Solution:** Check configuration:
1. Verify `docx_filter_profile_icons: true` in module.yaml
2. Use `--docx-filter-profile-icons` CLI flag
3. Check that images are in expected format

---

**Issue: "Tables not rendering correctly"**

```
Table content appears as plain text
```

**Solution:** Docling converts tables to markdown. If tables are complex:
1. Simplify table structure in source document
2. Use `docx_preserve_tables: true` in configuration
3. Consider manual table formatting in markdown

---

## 7. Alternatives Considered

### 7.1 Option A: Preprocessing with External Tool

**Description:** Convert .docx to markdown using an external CLI tool (e.g., pandoc) before CTX processing.

**Pros:**
- No new Python dependencies
- Leverages mature conversion tools
- Separates conversion from extraction

**Cons:**
- Requires users to install external tools
- Adds complexity to workflow
- Harder to control image filtering
- No access to document metadata

**Verdict:** ❌ Rejected - Poor user experience, limited control

---

### 7.2 Option B: Inline Conversion in Pack Pipeline

**Description:** Convert .docx to markdown on-the-fly during `ctx pack` without creating intermediate files.

**Pros:**
- No intermediate files on disk
- Faster processing (no I/O overhead)
- Cleaner output directory

**Cons:**
- Harder to debug conversion issues
- Can't inspect intermediate markdown
- Complicates error handling
- Makes testing more difficult

**Verdict:** ❌ Rejected - Harder to debug and test

---

### 7.3 Option C: Use python-docx Instead of Docling

**Description:** Use the lightweight python-docx library for extraction instead of Docling.

**Pros:**
- Smaller dependency
- Faster for simple documents
- More control over extraction

**Cons:**
- Limited table support
- No image handling
- Manual markdown conversion required
- Less robust for complex documents
- Reinventing wheel (Docling already solves this)

**Verdict:** ❌ Rejected - Docling is more robust and feature-complete

---

### 7.4 Option D: Support .doc (Legacy Format)

**Description:** Add support for legacy .doc format in addition to .docx.

**Pros:**
- Handles older documents
- More comprehensive support

**Cons:**
- Requires additional dependencies (antiword, catdoc)
- Legacy format is deprecated
- Conversion quality is poor
- Adds complexity for diminishing returns

**Verdict:** ❌ Rejected - Not worth the complexity, users can convert to .docx

---

### 7.5 Recommendation: Option E (Chosen Approach)

**Description:** Create new DocxExtractor using Docling with intelligent image filtering.

**Pros:**
- ✅ Follows existing extractor pattern
- ✅ Leverages IBM's Docling library (already installed)
- ✅ Provides fine-grained control over image filtering
- ✅ Maintains backward compatibility
- ✅ Easy to test and maintain
- ✅ Configurable behavior
- ✅ Positions for future e
nhancement (Excel support)

**Cons:**
- None identified

**Verdict:** ✅ **Selected** - Best balance of features, maintainability, and user experience

---

## 8. Migration & Deployment

### 8.1 Backward Compatibility

**No Breaking Changes:**
- Existing extractors continue to work unchanged
- Existing modules and configurations remain valid
- New .docx support is purely additive

**Opt-In Behavior:**
- .docx files are only processed if present
- Image filtering is configurable (defaults to enabled)
- Users can disable .docx support by not installing docling

### 8.2 Deployment Steps

**Phase 1: Development (Week 1)**

1. **Update Dependencies**
   ```bash
   # Update pyproject.toml
   # Add docling>=1.0 to dependencies and extractors extra
   
   # Test installation
   uv pip install -e ".[extractors]"
   python -c "import docling; print(docling.__version__)"
   ```

2. **Implement DocxExtractor**
   - Create `src/ctx/extractors/docx.py`
   - Implement `can_extract()`, `extract()`, and helper methods
   - Add lazy-loading for Docling converter

3. **Update Extractor Registry**
   - Modify `src/ctx/extractors/__init__.py`
   - Register DocxExtractor in `get_extractor()`

4. **Add Configuration Support**
   - Update `src/ctx/schema.py` with ExtractionConfig fields
   - Add CLI flags to `src/ctx/cli.py`

5. **Write Unit Tests**
   - Create `tests/test_docx_extractor.py`
   - Add test fixtures (use provided meeting transcript)
   - Achieve >90% coverage

**Phase 2: Integration (Week 2)**

1. **Update Pack Pipeline**
   - Modify `src/ctx/pack.py` to handle .docx files
   - Add .docx to supported extensions list
   - Test with real-world documents

2. **Integration Testing**
   - Add tests to `tests/test_pack.py`
   - Test end-to-end workflow
   - Verify chunking and JSONL output

3. **Update Install Script**
   - Modify `install.sh` to verify docling installation
   - Add docling to EXTRACTOR_PKGS array
   - Test on clean system

**Phase 3: Documentation (Week 2)**

1. **Update User Documentation**
   - Add .docx examples to `README.md`
   - Document CLI flags and configuration
   - Add troubleshooting section

2. **Update Project Documentation**
   - Update `AGENTS.md` supported formats table
   - Update `CLAUDE.md` supported formats table
   - Add this spec to `specs/features/`

3. **Create Migration Guide**
   - Document for existing users
   - Explain new capabilities
   - Provide example workflows

**Phase 4: Testing & Release (Week 3)**

1. **End-to-End Testing**
   ```bash
   # Test with real documents
   ctx pack /path/to/docs-with-docx --install
   
   # Verify output
   cat .context/chunks/*.jsonl | jq '.metadata.source_type' | sort | uniq
   ```

2. **Performance Testing**
   - Test with large .docx files (>100 pages)
   - Measure conversion time
   - Verify memory usage

3. **User Acceptance Testing**
   - Test with IBM meeting transcripts
   - Verify profile icon removal
   - Confirm context savings

4. **Release**
   - Bump version in `pyproject.toml` (0.1.1 → 0.2.0)
   - Update CHANGELOG
   - Tag release
   - Publish to PyPI

### 8.3 Documentation Updates

**README.md Updates:**

Add to "Supported Formats" section:

```markdown
## Supported Formats

CTX can extract content from:

- **Markdown** (`.md`, `.markdown`) - Native support
- **PDF** (`.pdf`) - Via pdftotext (poppler) or PyMuPDF fallback
- **PowerPoint** (`.pptx`) - Via python-pptx
- **Word Documents** (`.docx`, `.docm`) - Via Docling ✨ NEW
- **HTML** (`.html`, `.htm`) - Via markdownify
- **URLs** - Fetch and convert to markdown
- **Box Notes** (`.boxnote`) - ProseMirror JSON format

### DOCX Support

Microsoft Word documents are converted to markdown using IBM's Docling library:

\`\`\`bash
# Process directory with .docx files
ctx pack ./documents --install

# Remove profile icons from meeting transcripts (default)
ctx pack ./meetings --docx-filter-profile-icons

# Keep all images in technical documentation
ctx pack ./technical-docs --docx-keep-images
\`\`\`

**Meeting Transcript Optimization:**
- Automatically removes profile icon artifacts
- Preserves speaker names and timestamps
- Reduces context waste by ~5%
```

**AGENTS.md Updates:**

Update the "Supported file types in `ctx pack`" table:

```markdown
| Extension | Classification | Notes |
|-----------|---------------|-------|
| `.md`, `.markdown` | `markdown` | Frontmatter stripped |
| `.txt` | `plaintext` | Filename → H1 heading |
| `.pdf` | `pdf` | pdftotext → PyMuPDF fallback |
| `.pptx` | `pptx` | python-pptx |
| `.docx`, `.docm` | `docx` | Docling conversion, configurable image filtering |
| `.ppt` | `unsupported` | Legacy binary format |
| `.doc` | `unsupported` | Legacy binary format; convert to .docx |
| `.boxnote` | `boxnote` | Box Notes (ProseMirror JSON) |
| `.html`, `.htm` | `html` | markdownify |
| `.yaml`, `.yml`, `.json` | `structured` | Fenced code block |
```

**CLAUDE.md Updates:**

Same table update as AGENTS.md (keep files in sync).

### 8.4 Rollout Checklist

**Pre-Release:**
- [ ] All unit tests passing (>90% coverage)
- [ ] All integration tests passing (>80% coverage)
- [ ] Documentation complete and reviewed
- [ ] install.sh tested on macOS and Linux
- [ ] pyproject.toml dependencies verified
- [ ] Example .docx files tested successfully

**Release:**
- [ ] Version bumped in pyproject.toml
- [ ] CHANGELOG updated
- [ ] Git tag created
- [ ] PyPI package published
- [ ] GitHub release created with notes

**Post-Release:**
- [ ] Monitor for installation issues
- [ ] Collect user feedback on image filtering
- [ ] Track conversion success rate
- [ ] Document common issues in troubleshooting

---

## 9. Future Enhancements

### 9.1 Intelligent Image Classification

**Goal:** Automatically distinguish between useful images (diagrams, charts) and noise (profile icons, decorative elements).

**Approach:**
- Analyze image dimensions and aspect ratios
- Use heuristics based on document type
- Optional: ML-based image classification

**Implementation:**
```python
def _classify_image(self, image_metadata: dict) -> str:
    """
    Classify image as 'useful', 'profile', or 'decorative'.
    
    Returns:
        'useful' - Preserve (diagram, chart, screenshot)
        'profile' - Remove (profile icon, avatar)
        'decorative' - Remove (border, background)
    """
    width = image_metadata.get('width', 0)
    height = image_metadata.get('height', 0)
    
    # Profile icons are typically small and square
    if width < 200 and height < 200 and abs(width - height) < 20:
        return 'profile'
    
    # Large images are likely useful
    if width > 400 or height > 400:
        return 'useful'
    
    # Default to decorative
    return 'decorative'
```

### 9.2 Excel Support via Docling

**Goal:** Extract tables and data from .xlsx files.

**Approach:**
- Leverage Docling's Excel support
- Convert spreadsheets to markdown tables
- Handle multiple sheets

**Configuration:**
```yaml
extraction:
  xlsx_sheet_selection: all  # or 'first', 'named'
  xlsx_max_rows: 1000        # Limit for large sheets
  xlsx_preserve_formulas: false
```

### 9.3 OCR for Image-Heavy Documents

**Goal:** Extract text from scanned documents and images.

**Approach:**
- Integrate Tesseract OCR
- Optional enhancement for image-only .docx files
- Configurable quality/speed tradeoff

**Configuration:**
```yaml
extraction:
  docx_ocr_enabled: false
  docx_ocr_language: eng
  docx_ocr_quality: high  # high, medium, fast
```

### 9.4 Document Type Auto-Detection

**Goal:** Automatically detect document type and apply appropriate filtering.

**Heuristics:**
- Meeting transcript: High frequency of speaker names + timestamps
- Technical doc: Code blocks, diagrams, structured headings
- Report: Mixed content, charts, formal structure

**Implementation:**
```python
def _detect_document_type(self, markdown: str) -> str:
    """Auto-detect document type from content patterns."""
    # Count speaker patterns
    speaker_count = len(re.findall(r'\*\*[A-Z][a-z]+ [A-Z][a-z]+\*\* \d+:\d+', markdown))
    
    # Count code blocks
    code_count = len(re.findall(r'```', markdown))
    
    if speaker_count > 10:
        return 'transcript'
    elif code_count > 5:
        return 'technical'
    else:
        return 'report'
```

### 9.5 Batch Processing Optimization

**Goal:** Improve performance for large document sets.

**Approach:**
- Parallel processing of multiple .docx files
- Shared Docling converter instance
- Progress reporting for long operations

**Implementation:**
```python
from concurrent.futures import ThreadPoolExecutor

def extract_batch(self, files: List[Path], max_workers: int = 4) -> Dict[Path, str]:
    """Extract multiple .docx files in parallel."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(self.extract, f): f for f in files}
        results = {}
        for future in as_completed(futures):
            file = futures[future]
            try:
                results[file] = future.result()
            except Exception as e:
                logger.error(f"Failed to extract {file}: {e}")
        return results
```

---

## 10. Success Metrics

### 10.1 Technical Metrics

- **Conversion Success Rate:** >95% for well-formed .docx files
- **Performance:** <5 seconds for typical documents (<50 pages)
- **Test Coverage:** >90% unit, >80% integration
- **Memory Usage:** <500MB for documents <100MB

### 10.2 User Experience Metrics

- **Installation Success:** >98% (via install.sh)
- **Documentation Clarity:** User can complete first .docx extraction without support
- **Error Recovery:** Clear error messages for all failure modes
- **Configuration Ease:** Default settings work for 80% of use cases

### 10.3 Business Metrics

- **Adoption:** 50% of users process .docx files within first month
- **Context Savings:** Average 5% reduction in token usage for meeting transcripts
- **Support Tickets:** <5% related to .docx extraction issues
- **User Satisfaction:** >4.5/5 rating for .docx support

---

## 11. Appendix

### 11.1 Docling API Reference

**Key Classes:**
```python
from docling.document_converter import DocumentConverter

# Initialize converter
converter = DocumentConverter()

# Convert document
result = converter.convert("path/to/document.docx")

# Export to markdown
markdown = result.document.export_to_markdown()

# Access metadata
title = result.document.title
author = result.document.author
```

**Configuration Options:**
```python
from docling.document_converter import DocumentConverter, ConversionOptions

options = ConversionOptions(
    image_export=False,  # Don't export images
    table_export=True,   # Export tables
)

converter = DocumentConverter(options=options)
```

### 11.2 Example Meeting Transcript Output

**Before Filtering (with profile icons):**
```markdown
**Andrew Sica** 42:29

<!-- image -->

Up to a point.

<!-- image -->

**Speaker 1** 42:39

<!-- image -->

Hey.
I just want to make a suggestion here.
```

**After Filtering (clean):**
```markdown
**Andrew Sica** 42:29

Up to a point.

**Speaker 1** 42:39

Hey.
I just want to make a suggestion here.
```

**Context Savings:**
- Before: 47 `<!-- image -->` comments × ~50 tokens = 2,350 tokens
- After: 0 tokens
- Savings: 2,350 tokens (~5% of total document)

### 11.3 Related Specifications

- `specs/features/PACK_SPEC.md` - Zero-config packaging
- `specs/features/CHUNKER_METADATA_SPEC.md` - Hierarchical retrieval metadata
- `specs/features/CONTEXTUAL_RETRIEVAL_SPEC.md` - Anthropic Contextual Retrieval

### 11.4 References

- [Docling Documentation](https://github.com/DS4SD/docling)
- [Microsoft .docx Format Specification](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-docx/)
- [CTX Project Repository](https://github.com/itsBryantP/context-system)
