"""
Table detection service using img2table for school grade journals.
Handles detection of table structure, cells, and classification of regions.
"""

from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
from img2table.document import Image as Img2TableImage


class TableDetector:
    """
    Detects table structure in school journal images using img2table library.
    Classifies detected regions into headers, names, and grade cells.
    Uses img2table only for structure detection, not for OCR.
    """

    def __init__(self):
        """Initialize table detector."""
        pass

    def detect_table(self, image_path: str) -> Dict:
        """
        Detect table structure using img2table.

        Args:
            image_path: Path to the journal image

        Returns:
            Dictionary with detection results:
            {
                'success': bool,
                'tables': list of detected tables (if success),
                'cells': list of cell coordinates [(x, y, w, h), ...],
                'regions': {
                    'header_cells': [...],  # First row (dates)
                    'name_cells': [...],    # First column (names)
                    'grade_cells': [...]    # Main area (grades)
                },
                'error': str (if not success)
            }
        """
        try:
            # Load image with img2table
            doc = Img2TableImage(src=image_path)

            # Extract tables WITHOUT OCR (only structure detection)
            tables = doc.extract_tables(
                ocr=None,              # We'll use our own EasyOCR later
                implicit_rows=True,    # Detect rows without lines
                min_confidence=50      # Minimum confidence for table detection
            )

            if not tables:
                return {
                    'success': False,
                    'error': 'No tables detected in image'
                }

            # Get the largest table (main grade table)
            main_table = max(tables, key=lambda t: self._count_cells(t))

            # Extract and classify regions
            result = self._classify_regions(main_table)
            result['tables'] = tables
            result['main_table'] = main_table

            return result

        except Exception as e:
            return {
                'success': False,
                'error': f'Table detection failed: {str(e)}'
            }

    def _count_cells(self, table) -> int:
        """Count total number of cells in a table."""
        try:
            if hasattr(table, 'content') and table.content:
                return sum(len(row) for row in table.content if row)
            return 0
        except:
            return 0

    def _classify_regions(self, table) -> Dict:
        """
        Classify table cells into header, names, and grades regions.

        Args:
            table: Detected table object from img2table

        Returns:
            Dictionary with classified regions
        """
        try:
            content = table.content if hasattr(table, 'content') else []

            # Конвертируем в list если нужно
            if not isinstance(content, list):
                try:
                    content = list(content)
                except:
                    content = []

            if not content or len(content) == 0:
                return {
                    'success': False,
                    'error': 'Table has no content'
                }

            # First row = dates (header)
            header_cells = content[0] if len(content) > 0 else []

            # First column of each row (starting from row 1) = student names
            name_cells = []
            if len(content) > 1:
                for row in content[1:]:
                    if row and len(row) > 0:
                        name_cells.append(row[0])

            # Rest of the cells = grades (from row 1 onwards, from column 1 onwards)
            grade_rows = []
            if len(content) > 1:
                for row in content[1:]:
                    if isinstance(row, (list, tuple)) and len(row) > 1:
                        grade_rows.append(list(row[1:]))
                    else:
                        # Row has only name, no grades
                        grade_rows.append([])

            return {
                'success': True,
                'header_cells': list(header_cells) if header_cells else [],
                'name_cells': name_cells,
                'grade_rows': grade_rows,
                'raw_table': table,
                'total_rows': len(content),
                'total_cols': max(len(row) for row in content if isinstance(row, (list, tuple))) if content else 0
            }

        except Exception as e:
            import traceback
            return {
                'success': False,
                'error': f'Region classification failed: {str(e)}\n{traceback.format_exc()}'
            }

    def extract_cell_text(self, cell) -> str:
        """
        Extract text from a table cell.

        Args:
            cell: Cell object from img2table

        Returns:
            Extracted text as string
        """
        try:
            if hasattr(cell, 'value'):
                return str(cell.value).strip() if cell.value else ''
            elif isinstance(cell, str):
                return cell.strip()
            else:
                return str(cell).strip()
        except:
            return ''

    def get_cell_coordinates(self, table) -> List[Tuple[int, int, int, int]]:
        """
        Extract coordinates of all cells in the table.

        Args:
            table: Detected table object

        Returns:
            List of cell coordinates as (x, y, width, height) tuples
        """
        coordinates = []
        try:
            if hasattr(table, 'bbox'):
                # Table has bounding box information
                bbox = table.bbox
                coordinates.append((bbox.x1, bbox.y1, bbox.x2 - bbox.x1, bbox.y2 - bbox.y1))
        except:
            pass

        return coordinates
