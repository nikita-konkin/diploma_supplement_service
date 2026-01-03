import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.parser import process_student_workbook


def test_local_files(scores_path: str, disciplines_path: str, output_path: str = "test_output.xlsx"):
    """
    Test the parser with local files.
    
    Args:
        scores_path: Path to student scores XLSX file
        disciplines_path: Path to disciplines XLSX file
        output_path: Path for output file (default: test_output.xlsx)
    """
    print(f"Reading scores from: {scores_path}")
    with open(scores_path, 'rb') as f:
        scores_bytes = f.read()
    
    print(f"Reading disciplines from: {disciplines_path}")
    with open(disciplines_path, 'rb') as f:
        disciplines_bytes = f.read()
    
    print("Processing...")
    df_raw_scores, df_report = process_student_workbook(scores_bytes, disciplines_bytes)
    
    print(f"Writing output to: {output_path}")
    import pandas as pd
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_report.to_excel(writer, sheet_name='Report', index=True)
        df_raw_scores.to_excel(writer, sheet_name='RawScores', index=True)
    
    print("✓ Success!")
    print(f"\nReport shape: {df_report.shape}")
    print(f"RawScores shape: {df_raw_scores.shape}")
    print(f"Number of students: {len(df_raw_scores.columns)}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_parser.py <scores_file.xlsx> <disciplines_file.xlsx> [output_file.xlsx]")
        print("\nExample:")
        print("  python test_parser.py data/scores.xlsx data/disciplines.xlsx result.xlsx")
        sys.exit(1)
    
    scores = sys.argv[1]
    disciplines = sys.argv[2]
    output = sys.argv[3] if len(sys.argv) > 3 else "test_output.xlsx"
    
    try:
        test_local_files(scores, disciplines, output)
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)