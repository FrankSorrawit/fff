

# PyMuPDF4LLM PDF Extractor - Production Ready
import os
import sys
import logging
from pathlib import Path
import json
import time
import re
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class PyMuPDF4LLMExtractor:
    """Production-ready PDF extractor using PyMuPDF4LLM."""
    
    def __init__(self, pdf_path: str, output_dir: Optional[str] = None):
        """
        Initialize the extractor.
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Output directory (optional, defaults to pdf_name_extracted)
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # Set output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = self.pdf_path.parent / f"{self.pdf_path.stem}_extracted"
        
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize results tracking
        self.results = {
            'images': [],
            'tables': [],
            'markdown_file': None,
            'extraction_stats': {},
            'success': False
        }
        
        logging.info(f"🎯 Initializing PyMuPDF4LLM Extractor")
        logging.info(f"📄 PDF: {self.pdf_path}")
        logging.info(f"📂 Output: {self.output_dir}")

    def extract_all(self, 
                   extract_images: bool = True,
                   extract_tables: bool = True,
                   image_format: str = "png",
                   high_quality: bool = True) -> Dict:
        """
        Extract images and tables from PDF using PyMuPDF4LLM.
        
        Args:
            extract_images: Whether to extract images
            extract_tables: Whether to extract tables  
            image_format: Format for extracted images (png, jpg)
            high_quality: Use high quality extraction
            
        Returns:
            Dictionary with extraction results
        """
        start_time = time.time()
        
        try:
            import pymupdf4llm
            logging.info("✅ PyMuPDF4LLM imported successfully")
        except ImportError:
            logging.error("❌ PyMuPDF4LLM not installed. Install: pip install pymupdf4llm")
            self.results['error'] = "PyMuPDF4LLM not installed"
            return self.results
        
        try:
            logging.info("🚀 Starting extraction with PyMuPDF4LLM...")
            
            # Configure extraction parameters for PyMuPDF4LLM
            extraction_params = {}
            
            if extract_images:
                extraction_params['write_images'] = True
                extraction_params['image_path'] = str(self.output_dir)
                extraction_params['image_format'] = image_format
            
            logging.info(f"📋 Extraction parameters: {extraction_params}")
            
            # Extract to markdown
            logging.info("📄 Extracting content to markdown...")
            if extraction_params:
                md_text = pymupdf4llm.to_markdown(str(self.pdf_path), **extraction_params)
            else:
                md_text = pymupdf4llm.to_markdown(str(self.pdf_path))
            
            # Save markdown file
            md_filename = f"{self.pdf_path.stem}_content.md"
            md_path = self.output_dir / md_filename
            
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_text)
            
            self.results['markdown_file'] = str(md_path)
            logging.info(f"✅ Markdown saved: {md_filename} ({len(md_text):,} chars)")
            
            # Analyze extracted content
            if extract_images:
                self._analyze_images()
            
            if extract_tables:
                self._analyze_tables(md_text)
            
            # Calculate extraction stats
            end_time = time.time()
            self.results['extraction_stats'] = {
                'total_time': round(end_time - start_time, 2),
                'markdown_size': len(md_text),
                'images_found': len(self.results['images']),
                'tables_found': len(self.results['tables']),
                'output_files': len(list(self.output_dir.glob("*")))
            }
            
            self.results['success'] = True
            logging.info("🎉 Extraction completed successfully!")
            
        except Exception as e:
            logging.error(f"❌ Extraction failed: {e}")
            self.results['error'] = str(e)
            self.results['success'] = False
        
        return self.results

    def _analyze_images(self):
        """Analyze extracted images."""
        logging.info("🔍 Analyzing extracted images...")
        
        # Look for image files in output directory
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff']
        image_files = []
        
        for ext in image_extensions:
            image_files.extend(self.output_dir.glob(f"*{ext}"))
        
        for img_file in sorted(image_files):
            try:
                # Get image info
                file_size = img_file.stat().st_size
                
                # Try to get image dimensions
                try:
                    from PIL import Image
                    with Image.open(img_file) as img:
                        width, height = img.size
                        mode = img.mode
                        dimensions = f"{width}x{height}"
                except ImportError:
                    dimensions = "unknown"
                    mode = "unknown"
                except Exception:
                    dimensions = "unknown"
                    mode = "unknown"
                
                image_info = {
                    'filename': img_file.name,
                    'path': str(img_file),
                    'size_bytes': file_size,
                    'size_readable': self._format_size(file_size),
                    'dimensions': dimensions,
                    'mode': mode
                }
                
                self.results['images'].append(image_info)
                logging.info(f"  📸 {img_file.name}: {dimensions}, {self._format_size(file_size)}")
                
            except Exception as e:
                logging.error(f"  ❌ Error analyzing {img_file.name}: {e}")
        
        logging.info(f"📊 Total images found: {len(self.results['images'])}")

    def _analyze_tables(self, md_text: str):
        """Analyze tables from markdown text."""
        logging.info("🔍 Analyzing extracted tables...")
        
        # Find tables in markdown (look for pipe-separated content)
        table_pattern = r'\|.*?\|.*?\n'
        table_matches = re.findall(table_pattern, md_text, re.MULTILINE)
        
        if not table_matches:
            logging.info("📊 No markdown tables found")
            return
        
        # Group consecutive table rows
        current_table = []
        table_count = 0
        
        lines = md_text.split('\n')
        in_table = False
        
        for i, line in enumerate(lines):
            if '|' in line and line.strip():
                if not in_table:
                    # Start of new table
                    if current_table:
                        self._save_table(current_table, table_count)
                        table_count += 1
                    current_table = []
                    in_table = True
                
                current_table.append(line.strip())
            else:
                if in_table:
                    # End of table
                    if current_table:
                        self._save_table(current_table, table_count)
                        table_count += 1
                    current_table = []
                    in_table = False
        
        # Handle last table
        if current_table:
            self._save_table(current_table, table_count)
        
        logging.info(f"📊 Total tables found: {len(self.results['tables'])}")

    def _save_table(self, table_lines: List[str], table_index: int):
        """Save table to CSV file."""
        try:
            import pandas as pd
            
            # Parse table lines
            rows = []
            for line in table_lines:
                if '|' in line:
                    # Split by | and clean up
                    cells = [cell.strip() for cell in line.split('|')]
                    # Remove empty cells at start/end
                    cells = [cell for cell in cells if cell]
                    if cells:
                        rows.append(cells)
            
            if not rows:
                return
            
            # Skip separator rows (rows with only dashes and |)
            clean_rows = []
            for row in rows:
                if not all(set(cell.strip()) <= {'-', ':', ' '} for cell in row):
                    clean_rows.append(row)
            
            if len(clean_rows) < 2:  # Need at least header + 1 data row
                return
            
            # Ensure all rows have same number of columns
            max_cols = max(len(row) for row in clean_rows)
            normalized_rows = []
            for row in clean_rows:
                while len(row) < max_cols:
                    row.append('')
                normalized_rows.append(row[:max_cols])
            
            # Create DataFrame
            if len(normalized_rows) >= 2:
                headers = normalized_rows[0]
                data = normalized_rows[1:]
                df = pd.DataFrame(data, columns=headers)
                
                # Save to CSV
                csv_filename = f"table_{table_index + 1}.csv"
                csv_path = self.output_dir / csv_filename
                
                df.to_csv(csv_path, index=False, encoding='utf-8')
                
                table_info = {
                    'filename': csv_filename,
                    'path': str(csv_path),
                    'dimensions': f"{df.shape[0]}x{df.shape[1]}",
                    'rows': df.shape[0],
                    'columns': df.shape[1],
                    'headers': list(df.columns)
                }
                
                self.results['tables'].append(table_info)
                logging.info(f"  📋 Table {table_index + 1}: {csv_filename} ({df.shape[0]}x{df.shape[1]})")
                
        except ImportError:
            logging.warning("pandas not available for CSV export")
        except Exception as e:
            logging.error(f"❌ Error saving table {table_index + 1}: {e}")

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def generate_report(self) -> str:
        """Generate extraction report."""
        if not self.results['success']:
            return "❌ Extraction failed. No report available."
        
        stats = self.results['extraction_stats']
        
        report = f"""
📊 PyMuPDF4LLM Extraction Report
{'='*50}

📄 Source PDF: {self.pdf_path.name}
📂 Output Directory: {self.output_dir}
⏱️  Extraction Time: {stats['total_time']} seconds

📈 Results Summary:
  🖼️  Images: {stats['images_found']} files
  📋 Tables: {stats['tables_found']} files
  📝 Markdown: {stats['markdown_size']:,} characters
  📁 Total Files: {stats['output_files']} files

🖼️  Image Details:
"""
        
        for i, img in enumerate(self.results['images'], 1):
            report += f"  {i}. {img['filename']}: {img['dimensions']}, {img['size_readable']}\n"
        
        if not self.results['images']:
            report += "  No images found\n"
        
        report += "\n📋 Table Details:\n"
        
        for i, table in enumerate(self.results['tables'], 1):
            report += f"  {i}. {table['filename']}: {table['dimensions']} (rows x columns)\n"
            report += f"     Headers: {', '.join(table['headers'][:5])}{'...' if len(table['headers']) > 5 else ''}\n"
        
        if not self.results['tables']:
            report += "  No tables found\n"
        
        report += f"\n✅ Extraction completed successfully!"
        
        return report

    def save_report(self, filename: str = "extraction_report.txt"):
        """Save extraction report to file."""
        report = self.generate_report()
        report_path = self.output_dir / filename
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logging.info(f"📄 Report saved: {filename}")
        return str(report_path)

def main():
    """Main function for command line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract images and tables from PDF using PyMuPDF4LLM")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("-o", "--output", help="Output directory")
    parser.add_argument("--no-images", action="store_true", help="Skip image extraction")
    parser.add_argument("--no-tables", action="store_true", help="Skip table extraction")
    parser.add_argument("--image-format", default="png", choices=["png", "jpg"], help="Image format")
    parser.add_argument("--report", action="store_true", help="Generate detailed report")
    
    args = parser.parse_args()
    
    if not Path(args.pdf_path).exists():
        logging.error(f"❌ PDF file not found: {args.pdf_path}")
        return 1
    
    try:
        # Initialize extractor
        extractor = PyMuPDF4LLMExtractor(args.pdf_path, args.output)
        
        # Run extraction
        results = extractor.extract_all(
            extract_images=not args.no_images,
            extract_tables=not args.no_tables,
            image_format=args.image_format
        )
        
        if results['success']:
            # Print summary
            print(extractor.generate_report())
            
            # Save detailed report if requested
            if args.report:
                extractor.save_report()
            
            logging.info("🎉 All done!")
            return 0
        else:
            logging.error(f"❌ Extraction failed: {results.get('error', 'Unknown error')}")
            return 1
            
    except Exception as e:
        logging.error(f"❌ Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    # Example usage when run as script
    if len(sys.argv) > 1:
        sys.exit(main())
    else:
        # Interactive example
        script_dir = Path(__file__).parent
        pdf_path = script_dir / "PVD5.pdf"
        
        if pdf_path.exists():
            print(f"🎯 Found PDF: {pdf_path}")
            print("Running extraction...")
            
            extractor = PyMuPDF4LLMExtractor(str(pdf_path))
            results = extractor.extract_all()
            
            if results['success']:
                print(extractor.generate_report())
            else:
                print(f"❌ Failed: {results.get('error')}")
        else:
            print("📋 Usage: python script.py path/to/pdf")
            print("📋 Or place t5.pdf in the same directory")
