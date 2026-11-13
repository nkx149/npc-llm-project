"""export_review.py - turn a screening log (.jsonl) into a readable Excel workbook.

Usage (notebook):  import export_review as ex; ex.export_review(LOG_PATH, "LogOutputs/review")
Usage (terminal):  python export_review.py <log>.jsonl [out_dir]
Needs: pip install openpyxl
"""
from pathlib import Path

import pandas as pd 
from openpyxl import load_workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

# Main columns shown first (with widths); every other logged column follows after them.
SINGLE_COLS = [("model_id", 15), ("persona_id", 16), ("category", 13), ("prompt_id", 8),
               ("repeat", 7), ("player_input", 40), ("say", 70), ("word_count", 8),
               ("sentence_count", 9), ("hit_length_cap", 9), ("json_valid", 8),
               ("has_asterisks", 9), ("banned_hits", 14), ("decode_tok_s", 9), ("total_s", 8),
               ("failure_tags", 24), ("severity", 9), ("notes", 40)]
CONVO_COLS = [("model_id", 15), ("persona_id", 16), ("repeat", 7), ("turn", 6), ("purpose", 26),
              ("player_input", 40), ("say", 70), ("word_count", 8), ("repetition", 10),
              ("hit_length_cap", 9), ("json_valid", 8), ("has_asterisks", 9), ("banned_hits", 14),
              ("prompt_tokens", 9), ("decode_tok_s", 9), ("total_s", 8),
              ("failure_tags", 24), ("severity", 9), ("notes", 40)]
WRAP = {"player_input", "say", "purpose", "notes", "failure_tags"}
TAG_COLS = {"failure_tags", "severity", "notes"}
SEVERITY_HELP = "1 = minor, 2 = immersion-break, 3 = serious"


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    """Lists/dicts (banned_hits, failure_tags, options) -> readable text for Excel."""
    df = df.copy()
    for col in df.columns:
        if df[col].apply(lambda v: isinstance(v, (list, dict))).any():
            df[col] = df[col].apply(
                lambda v: ", ".join(map(str, v)) if isinstance(v, list)
                else ", ".join(f"{k}={x}" for k, x in v.items()) if isinstance(v, dict)
                else v)
    return df


def _ordered(df: pd.DataFrame, main_cols: list[tuple[str, int]]) -> tuple[pd.DataFrame, list[int]]:
    """Main columns first, then all remaining columns (minus empty ones)."""
    main = [c for c, _ in main_cols if c in df]
    rest = [c for c in df.columns if c not in main and df[c].notna().any()]
    widths = [w for c, w in main_cols if c in df] + [14] * len(rest)
    return df[main + rest], widths


def _format_sheet(ws, headers: list[str], widths: list[int]) -> None:
    header_fill = PatternFill("solid", fgColor="1F3864")
    tag_fill = PatternFill("solid", fgColor="FFF2CC")       # light yellow = "fill me in"
    wrap_cols = {i + 1 for i, h in enumerate(headers) if h in WRAP}
    tag_cols = {i + 1 for i, h in enumerate(headers) if h in TAG_COLS}

    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = width

    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    ws.row_dimensions[1].height = 32

    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=cell.column in wrap_cols, vertical="top")
            if cell.column in tag_cols:
                cell.fill = tag_fill

    ws.freeze_panes = "C2"            # header row + model/persona columns stay visible
    ws.auto_filter.ref = ws.dimensions


def _flag_rules(ws, headers: list[str]) -> None:
    """Red bold text for automatic flags so problems jump out."""
    red = Font(color="C00000", bold=True)
    rules = {"hit_length_cap": "{}=TRUE", "has_asterisks": "{}=TRUE", "json_valid": "{}=FALSE",
             "banned_hits": "LEN({})>0", "repetition": "AND(ISNUMBER({0}),{0}>0.5)",
             "error": "LEN({})>0"}
    for name, formula in rules.items():
        if name in headers:
            col = ws.cell(1, headers.index(name) + 1).column_letter
            ws.conditional_formatting.add(
                f"{col}2:{col}{ws.max_row}",
                FormulaRule(formula=[formula.format(f"{col}2")], font=red))


def _severity_dropdown(ws, headers: list[str]) -> None:
    if "severity" not in headers:
        return
    col = ws.cell(1, headers.index("severity") + 1).column_letter
    dv = DataValidation(type="list", formula1='"1,2,3"', allow_blank=True,
                        promptTitle="Severity", prompt=SEVERITY_HELP)
    ws.add_data_validation(dv)
    dv.add(f"{col}2:{col}{ws.max_row}")


def export_review(log_path, out_dir=".") -> Path:
    log_path, out_dir = Path(log_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = _flatten(pd.read_json(log_path, lines=True))

    # Singles: grouped by question, so each question's answers from every model sit together
    singles = df[df["type"] == "single"].sort_values(
        ["prompt_id", "persona_id", "model_id", "repeat"])

    # Conversations: completed attempts only, each read top-to-bottom in turn order
    complete = set(df.loc[df["type"] == "convo_complete", "attempt_id"])
    turns = df[(df["type"] == "convo_turn") & df["attempt_id"].isin(complete)].sort_values(
        ["model_id", "persona_id", "repeat", "turn"])

    sheets = {"Singles": _ordered(singles, SINGLE_COLS),
              "Conversations": _ordered(turns, CONVO_COLS),
              "All rows": _ordered(df, [])}

    out_path = out_dir / f"review_{log_path.stem}.xlsx"
    with pd.ExcelWriter(out_path, engine="openpyxl") as xw:
        for name, (data, _) in sheets.items():
            data.to_excel(xw, sheet_name=name, index=False)

    wb = load_workbook(out_path)
    for name, (data, widths) in sheets.items():
        ws, headers = wb[name], list(data.columns)
        _format_sheet(ws, headers, widths)
        _flag_rules(ws, headers)
        _severity_dropdown(ws, headers)
    wb.save(out_path)
    return out_path


if __name__ == "__main__":
    import sys
    print(export_review(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "."))
