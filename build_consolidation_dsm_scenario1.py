"""
Consolidation Potential DSM — Scenario 1: AI Center of Excellence
==================================================================
Builds the γ (gamma) matrix for the MDL clustering validation study.

Required input files (same folder as this script):
  - Communication_matrix__Relationship_work_effort_-_Frequency__Avg__.xlsx
  - time-utilization-insights.xlsx

Output:
  - consolidation_potential_DSM_scenario1_SA<n>_FTE<n>_<timestamp>.xlsx

Dependencies:
  pip install pandas openpyxl
"""

import pandas as pd
import numpy as np
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from collections import defaultdict
from pathlib import Path
from datetime import datetime

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURABLE THRESHOLDS
# A sub-unit pair is marked 1 (consolidation potential) if EITHER condition met:
#   Condition A: shared activity count >= THRESHOLD_SHARED_ACTIVITIES
#   Condition B: combined FTE in shared activities >= THRESHOLD_COMBINED_FTE
# ══════════════════════════════════════════════════════════════════════════════
THRESHOLD_SHARED_ACTIVITIES = 4    # minimum number of shared AI-candidate activities
THRESHOLD_COMBINED_FTE      = 2  # minimum combined FTE across shared activities

# ── Sensitivity analysis ranges ───────────────────────────────────────────────
# All integer values in [SA_MIN, SA_MAX] are tested for shared-activity threshold.
# All float values stepping by SA_FTE_STEP in [FTE_MIN, FTE_MAX] are tested for FTE.
SA_MIN          = 1      # shared-activity threshold: range start (inclusive)
SA_MAX          = 7      # shared-activity threshold: range end   (inclusive)
SA_FTE_MIN      = 0.0    # combined-FTE threshold: range start
SA_FTE_MAX      = 5.0    # combined-FTE threshold: range end
SA_FTE_STEP     = 0.5    # combined-FTE threshold: step size

# ── File paths ────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
FREQ_FILE  = BASE / "Communication_matrix_Relationship_work_effort_-_Frequency_Avg.xlsx"
TIME_FILE  = BASE / "time-utilization-insights.xlsx"

_ts  = datetime.now().strftime("%Y-%d-%m-%H:%M").replace(":", "h")
_fte = str(THRESHOLD_COMBINED_FTE).replace(".", "_")
OUTPUT = BASE / f"consolidation_potential_DSM_scenario1_SA{THRESHOLD_SHARED_ACTIVITIES}_FTE{_fte}_{_ts}.xlsx"

# ── Sub-unit → parent function mapping ───────────────────────────────────────
UNIT_TO_FUNCTION = {
    "Medical Evaluation Unit 1":                "MAU",
    "Medical Evaluation Unit 2":                "MAU",
    "Medical Evaluation Unit 3":                "MAU",
    "Medical Excellence Office":                "ME",
    "Medical Excellence Team":                  "ME",
    "Medical Communications Office":            "MSIC",
    "Medical Scientific Information Center":    "MSIC",
    "Scientific Information Center":            "MSIC",
    "Regulatory Affairs Unit 1":                "PMS",
    "Regulatory Affairs Unit 2":                "PMS",
    "Regulatory Affairs Unit 3":                "PMS",
    "Strategic Management Office 1":            "PMS",
    "Strategic Management Office 2":            "PMS",
    "Strategic Management Office 3":            "PMS",
    "Strategic Management Team 1":              "PMS",
    "Strategic Management Team 2":              "PMS",
    "Strategic Management Team 3":              "PMS",
    "Post-Marketing Study Strategy Management": "PMS",
    "Operational Effectiveness":                "PMS",
    "Operational Excellence":                   "PMS",
    "Clinical Research Division":               "MRE",
    "Clinical Strategy Division":               "MRE",
    "Clinical Strategy Group":                  "MRE",
    "Medical Research Evaluation":              "MRE",
    "Product Management Review":                "MRE",
    "Strategic Medical Excellence":             "SME",
    "Medical Governance Office":                "SME",
    "Medical Governance Unit":                  "SME",
    "Medical Innovation Group":                 "SME",
    "New Product Value Planning":               "SME",
    # External — excluded from DSM
    "Marketing Operations":     "External",
    "Global Program Management":"External",
    "Global Program Strategy":  "External",
    "Supply Chain Division":    "External",
    "Supply Chain Operations":  "External",
}

# ── Scenario 1: AI CoE candidate activities ───────────────────────────────────
AI_ACTIVITIES = [
    "Collection of latest scientific information, expert meetings, and insight reporting",
    "Review and management of promotional and non-promotional materials",
    "Planning and management of database, survey, and literature review studies",
    "Development and execution of publication and conference presentation strategies",
    "Application, approval, and publication of re-examination results",
    "Publication of post-marketing study results and disclosure to tracking systems",
    "Promotion of data and digital projects",
]

# Short display labels (A1–A7) for column headers
ACT_LABELS = {a: f"A{i+1}: {a[:45]}…" if len(a) > 45 else f"A{i+1}: {a}"
              for i, a in enumerate(AI_ACTIVITIES)}

# Function label as it appears in the Activity Coverage sheet → function code
FUNC_LABEL_MAP = {
    "(ME) Medical Engagement Team":                                             "ME",
    "(MSIC) Medical Scientific Information Center":                             "MSIC",
    "(PMS) Post-Marketing Study Management":                                    "PMS",
    "(PMS) Post-Marketing Study Management - ethical drug access and compassionate use program management": "PMS",
    "(MRE) Medical Research Leadership":                                        "MRE",
    "(MRE) Medical Research Leadership -":                                      "MRE",
    "(SME) Strategic Medical Excellence":                                       "SME",
    "(MAU) Medical Affairs Division":                                           "MAU",
}

# ── Styling constants ─────────────────────────────────────────────────────────
FUNC_BG   = {"MAU":"C6EFCE", "ME":"FFEB9C", "MRE":"BDD7EE",
              "MSIC":"E2EFDA", "PMS":"FCE4D6", "SME":"EAD1DC"}
FUNC_FG   = {"MAU":"375623", "ME":"7F6000", "MRE":"1F4E79",
              "MSIC":"375623", "PMS":"833C00", "SME":"4C1130"}
NAVY      = "1F4E79"
MID_BLUE  = "2E75B6"
RED_FILL  = PatternFill("solid", fgColor="C00000")
DARK_FILL = PatternFill("solid", fgColor="404040")
WHITE_FILL= PatternFill("solid", fgColor="FFFFFF")
GRAY_FILL = PatternFill("solid", fgColor="F5F5F5")

thin_side = Side(style="thin", color="CCCCCC")
THIN_BORDER = Border(left=thin_side, right=thin_side,
                     top=thin_side,  bottom=thin_side)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Load data
# ══════════════════════════════════════════════════════════════════════════════
print("Loading data files…")
df_cells = pd.read_excel(FREQ_FILE, sheet_name="Matrix cells")
df_time  = pd.read_excel(TIME_FILE, sheet_name="Activity Coverage")
print(f"  Frequency matrix: {len(df_cells):,} dyads")
print(f"  Activity coverage: {len(df_time)} activities")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Infer employee-level AI activity participation from dyad data
#
# Rationale: each dyad row has an "Activities" field listing the activities
# the collaboration concerns. If an AI CoE activity appears in any dyad
# for employee X, we infer X participates in that activity.
# ══════════════════════════════════════════════════════════════════════════════
print("Inferring employee activity participation from dyad data…")
emp_unit       = {}   # employee name → sub-unit name
emp_activities = defaultdict(set)  # employee name → set of AI activities

for _, row in df_cells.iterrows():
    re, ru = row["Row Employee"],    row["Row Unit"]
    ce, cu = row["Column Employee"], row["Column Unit"]
    emp_unit[re] = ru
    emp_unit[ce] = cu

    acts_raw = str(row["Activities"]) if pd.notna(row["Activities"]) else ""
    for act in AI_ACTIVITIES:
        if act in acts_raw:
            emp_activities[re].add(act)
            emp_activities[ce].add(act)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Aggregate to sub-unit level
# ══════════════════════════════════════════════════════════════════════════════
print("Aggregating to sub-unit level…")
internal_units = sorted(
    u for u, f in UNIT_TO_FUNCTION.items() if f != "External"
)

unit_ai_acts = defaultdict(set)   # sub-unit → set of AI activities present

for emp, unit in emp_unit.items():
    if UNIT_TO_FUNCTION.get(unit) == "External":
        continue
    for act in emp_activities[emp]:
        unit_ai_acts[unit].add(act)

# FTE per (function_code, activity) from Activity Coverage sheet
fte_map = {}
for _, row in df_time[df_time["Activity"].isin(AI_ACTIVITIES)].iterrows():
    func_code = FUNC_LABEL_MAP.get(row["Function"])
    if func_code:
        fte_map[(func_code, row["Activity"])] = row["FTE Coverage"]

# Which sub-units within each function are active for each activity?
func_to_units = defaultdict(list)
for u in internal_units:
    func_to_units[UNIT_TO_FUNCTION[u]].append(u)

def unit_fte(unit, activity):
    """FTE share: function FTE divided equally across active sub-units."""
    func = UNIT_TO_FUNCTION[unit]
    total = fte_map.get((func, activity), 0.0)
    active = [u for u in func_to_units[func] if activity in unit_ai_acts[u]]
    if not active or unit not in active:
        return 0.0
    return total / len(active)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Compute pairwise overlap and build matrices
# ══════════════════════════════════════════════════════════════════════════════
print("Computing pairwise overlap scores…")
n = len(internal_units)
dsm_binary  = np.zeros((n, n), dtype=int)
dsm_count   = np.zeros((n, n), dtype=int)
dsm_fte     = np.zeros((n, n), dtype=float)

for i, ui in enumerate(internal_units):
    for j, uj in enumerate(internal_units):
        if i == j:
            continue
        shared = unit_ai_acts[ui] & unit_ai_acts[uj]
        cnt    = len(shared)
        fte    = sum(unit_fte(ui, a) + unit_fte(uj, a) for a in shared)

        # Threshold rule (see THRESHOLD_* variables at top of script)
        binary = 1 if (cnt >= THRESHOLD_SHARED_ACTIVITIES
                       or fte >= THRESHOLD_COMBINED_FTE) else 0

        dsm_count[i][j]  = cnt
        dsm_fte[i][j]    = round(fte, 2)
        dsm_binary[i][j] = binary

# Symmetrize: if either direction is marked, mark both
dsm_binary = np.maximum(dsm_binary, dsm_binary.T)
dsm_count  = np.maximum(dsm_count,  dsm_count.T)
dsm_fte    = np.maximum(dsm_fte,    dsm_fte.T)

total_marked_pairs = int(dsm_binary.sum() // 2)
print(f"  {total_marked_pairs} unique pairs marked (out of {n*(n-1)//2} possible)")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Build Excel workbook
# ══════════════════════════════════════════════════════════════════════════════
print("Building Excel workbook…")

wb = openpyxl.Workbook()

ROW_OFF = 5   # data starts at row 5 (rows 1–4 used for titles + headers)
COL_OFF = 3   # data starts at column 4 (cols 1–3 = index, function, unit label)


def write_row_col_headers(ws):
    """Write the function + sub-unit headers shared by the DSM sheets."""
    ws.row_dimensions[3].height = 14
    ws.row_dimensions[4].height = 80
    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 7
    ws.column_dimensions["C"].width = 32

    ws["B3"] = "Func"
    ws["B3"].font = Font(name="Arial", bold=True, size=8)
    ws["C3"] = "Sub-unit"
    ws["C3"].font = Font(name="Arial", bold=True, size=8)

    # Column headers
    for j, uj in enumerate(internal_units):
        col = COL_OFF + 1 + j
        fj  = UNIT_TO_FUNCTION[uj]
        ws.column_dimensions[get_column_letter(col)].width = 4.5

        c3 = ws.cell(row=3, column=col, value=fj)
        c3.fill      = PatternFill("solid", fgColor=FUNC_FG[fj])
        c3.font      = Font(name="Arial", bold=True, size=8, color="FFFFFF")
        c3.alignment = Alignment(horizontal="center", vertical="center")
        c3.border    = THIN_BORDER

        c4 = ws.cell(row=4, column=col, value=uj)
        c4.fill      = PatternFill("solid", fgColor=FUNC_BG[fj])
        c4.font      = Font(name="Arial", bold=True, size=8)
        c4.alignment = Alignment(horizontal="center", vertical="bottom",
                                 text_rotation=90, wrap_text=True)
        c4.border    = THIN_BORDER

    # Row headers
    for i, ui in enumerate(internal_units):
        row = ROW_OFF + i
        fi  = UNIT_TO_FUNCTION[ui]
        ws.row_dimensions[row].height = 14

        c = ws.cell(row=row, column=1, value=i + 1)
        c.font = Font(name="Arial", size=8, color="888888")
        c.alignment = Alignment(horizontal="center")

        cf = ws.cell(row=row, column=2, value=fi)
        cf.fill      = PatternFill("solid", fgColor=FUNC_FG[fi])
        cf.font      = Font(name="Arial", bold=True, size=8, color="FFFFFF")
        cf.alignment = Alignment(horizontal="center", vertical="center")
        cf.border    = THIN_BORDER

        cu = ws.cell(row=row, column=3, value=ui)
        cu.fill      = PatternFill("solid", fgColor=FUNC_BG[fi])
        cu.font      = Font(name="Arial", size=9)
        cu.alignment = Alignment(horizontal="left", vertical="center")
        cu.border    = THIN_BORDER


# ── Sheet 1: Binary DSM ───────────────────────────────────────────────────────
ws1 = wb.active
ws1.title = "Binary DSM (γ matrix)"

ws1["A1"] = "Consolidation Potential DSM — Scenario 1: AI Center of Excellence"
ws1["A1"].font = Font(name="Arial", bold=True, size=13, color=NAVY)
ws1["A2"] = (
    f"Binary matrix (1 = consolidation potential). "
    f"Criterion: ≥{THRESHOLD_SHARED_ACTIVITIES} shared AI activities "
    f"OR ≥{THRESHOLD_COMBINED_FTE} combined FTE in shared activities."
)
ws1["A2"].font = Font(name="Arial", size=9, italic=True, color="555555")

write_row_col_headers(ws1)

for i in range(n):
    for j in range(n):
        row = ROW_OFF + i
        col = COL_OFF + 1 + j
        fi  = UNIT_TO_FUNCTION[internal_units[i]]
        fj  = UNIT_TO_FUNCTION[internal_units[j]]
        c   = ws1.cell(row=row, column=col)
        c.border = THIN_BORDER

        if i == j:
            c.fill = DARK_FILL
        elif dsm_binary[i][j] == 1:
            c.value = 1
            c.fill  = RED_FILL
            c.font  = Font(name="Arial", bold=True, size=9, color="FFFFFF")
            c.alignment = Alignment(horizontal="center", vertical="center")
        else:
            c.fill = GRAY_FILL if fi == fj else WHITE_FILL

# Legend
leg = ROW_OFF + n + 2
ws1.cell(row=leg, column=1, value="Legend:").font = Font(name="Arial", bold=True, size=9)
lc = ws1.cell(row=leg, column=2, value="  1 = Consolidation potential (γ mark)")
lc.fill = RED_FILL
lc.font = Font(name="Arial", bold=True, size=9, color="FFFFFF")
ws1.cell(row=leg, column=3, value="Blank = No consolidation potential").font = Font(name="Arial", size=9)
ws1.cell(row=leg+1, column=1,
         value=f"Total marks: {total_marked_pairs} unique pairs").font = Font(name="Arial", size=9, italic=True)


# ── Sheet 2: Activity Overlap Count ──────────────────────────────────────────
ws2 = wb.create_sheet("Activity Overlap Count")
ws2["A1"] = "Activity Overlap Count — number of shared AI-candidate activities between sub-unit pairs"
ws2["A1"].font = Font(name="Arial", bold=True, size=12, color=NAVY)
ws2["A2"] = "Cells show how many of the 7 AI CoE activities (A1–A7) both sub-units have employees participating in."
ws2["A2"].font = Font(name="Arial", size=9, italic=True, color="555555")

write_row_col_headers(ws2)

count_colors = ["FFFFFF","DEEBF7","C6DBEF","9ECAE1","6BAED6","3182BD","08519C","08306B"]

for i in range(n):
    for j in range(n):
        row = ROW_OFF + i
        col = COL_OFF + 1 + j
        c   = ws2.cell(row=row, column=col)
        c.border = THIN_BORDER
        if i == j:
            c.fill = DARK_FILL
        else:
            val = int(dsm_count[i][j])
            c.value     = val if val > 0 else None
            c.fill      = PatternFill("solid", fgColor=count_colors[min(val, 7)])
            c.font      = Font(name="Arial", size=9, bold=(val >= 2),
                               color="FFFFFF" if val >= 5 else "000000")
            c.alignment = Alignment(horizontal="center", vertical="center")


# ── Sheet 3: Combined FTE Overlap ────────────────────────────────────────────
ws3 = wb.create_sheet("Combined FTE Overlap")
ws3["A1"] = "Combined FTE Overlap — sum of FTE in shared AI-candidate activities across both sub-units"
ws3["A1"].font = Font(name="Arial", bold=True, size=12, color=NAVY)
ws3["A2"] = "FTE distributed equally across active sub-units within each function. Higher = stronger consolidation signal."
ws3["A2"].font = Font(name="Arial", size=9, italic=True, color="555555")

write_row_col_headers(ws3)

max_fte = dsm_fte.max()

def fte_fill(val, max_val):
    if val <= 0:
        return WHITE_FILL
    if val < 1.0:
        return PatternFill("solid", fgColor="FCE4D6")
    if val < 3.0:
        return PatternFill("solid", fgColor="F4B183")
    return PatternFill("solid", fgColor="C55A11")

for i in range(n):
    for j in range(n):
        row = ROW_OFF + i
        col = COL_OFF + 1 + j
        c   = ws3.cell(row=row, column=col)
        c.border = THIN_BORDER
        if i == j:
            c.fill = DARK_FILL
        else:
            val = float(dsm_fte[i][j])
            if val > 0:
                c.value     = round(val, 2)
                c.fill      = fte_fill(val, max_fte)
                c.font      = Font(name="Arial", size=9, bold=(val >= 1),
                                   color="FFFFFF" if val >= 3 else "000000")
                c.alignment = Alignment(horizontal="center", vertical="center")
            else:
                c.fill = WHITE_FILL


# ── Sheet 4: Sub-unit Activity Participation ──────────────────────────────────
ws4 = wb.create_sheet("Sub-unit Activity Participation")
ws4["A1"] = "AI CoE Activity Participation by Sub-unit — building block for the γ matrix"
ws4["A1"].font = Font(name="Arial", bold=True, size=12, color=NAVY)
ws4["A2"] = ("✓ = sub-unit has at least one employee participating. "
             "FTE share = function FTE divided equally across active sub-units.")
ws4["A2"].font = Font(name="Arial", size=9, italic=True, color="555555")

act_short_labels = [ACT_LABELS[a] for a in AI_ACTIVITIES]
headers    = ["#", "Function", "Sub-unit"] + act_short_labels + ["# AI Acts", "Total FTE share"]
col_widths = [4, 7, 32] + [18]*7 + [10, 13]

for c_idx, (h, w) in enumerate(zip(headers, col_widths), 1):
    cell = ws4.cell(row=3, column=c_idx, value=h)
    cell.fill      = PatternFill("solid", fgColor=NAVY)
    cell.font      = Font(name="Arial", bold=True, size=9, color="FFFFFF")
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border    = THIN_BORDER
    ws4.column_dimensions[get_column_letter(c_idx)].width = w
ws4.row_dimensions[3].height = 55

for i, ui in enumerate(internal_units):
    fi  = UNIT_TO_FUNCTION[ui]
    row = 4 + i
    ws4.row_dimensions[row].height = 14

    ws4.cell(row=row, column=1, value=i+1).font = Font(name="Arial", size=9)

    cf = ws4.cell(row=row, column=2, value=fi)
    cf.fill      = PatternFill("solid", fgColor=FUNC_FG[fi])
    cf.font      = Font(name="Arial", bold=True, size=9, color="FFFFFF")
    cf.alignment = Alignment(horizontal="center")
    cf.border    = THIN_BORDER

    cu = ws4.cell(row=row, column=3, value=ui)
    cu.fill   = PatternFill("solid", fgColor=FUNC_BG[fi])
    cu.font   = Font(name="Arial", size=9)
    cu.border = THIN_BORDER

    total_fte = 0.0
    act_count = 0
    for k, act in enumerate(AI_ACTIVITIES):
        col  = 4 + k
        fte  = unit_fte(ui, act)
        has  = act in unit_ai_acts[ui]
        cell = ws4.cell(row=row, column=col)
        cell.border    = THIN_BORDER
        cell.alignment = Alignment(horizontal="center")
        if has:
            cell.value = f"✓  ({fte:.2f} FTE)"
            cell.fill  = PatternFill("solid", fgColor=FUNC_BG[fi])
            cell.font  = Font(name="Arial", size=9, bold=True)
            total_fte += fte
            act_count += 1
        else:
            cell.fill = PatternFill("solid", fgColor="F8F8F8")

    c_cnt = ws4.cell(row=row, column=11, value=act_count)
    c_cnt.font      = Font(name="Arial", bold=True, size=9)
    c_cnt.alignment = Alignment(horizontal="center")
    c_cnt.fill      = PatternFill("solid", fgColor="FFF2CC" if act_count > 0 else "FFFFFF")
    c_cnt.border    = THIN_BORDER

    c_fte = ws4.cell(row=row, column=12, value=round(total_fte, 2))
    c_fte.font      = Font(name="Arial", bold=True, size=9)
    c_fte.alignment = Alignment(horizontal="center")
    c_fte.fill      = PatternFill("solid", fgColor="FCE4D6" if total_fte > 0 else "FFFFFF")
    c_fte.border    = THIN_BORDER


# ── Sheet 5: Methodology Notes ───────────────────────────────────────────────
ws5 = wb.create_sheet("Methodology Notes")
ws5.column_dimensions["A"].width = 120

notes = [
    ("Consolidation Potential DSM — Scenario 1: AI Center of Excellence", True, 14, NAVY),
    ("Methodology for constructing the γ matrix", True, 11, MID_BLUE),
    ("", False, 10, "000000"),
    ("This workbook contains the consolidation potential (γ) matrix for Scenario 1 of the MDL validation study.", False, 10, "000000"),
    ("It follows the activity overlap scoring protocol described in the research design (Section 3.3).", False, 10, "000000"),
    ("", False, 10, "000000"),
    ("Step 1: Define consolidation-candidate activities (AI CoE scenario)", True, 10, NAVY),
    ("Seven activities identified as AI-augmentable (high-volume information processing or structured document work):", False, 10, "000000"),
    ("  A1  Collection of latest scientific information, expert meetings, and insight reporting  (ME: 10.94 FTE)", False, 10, "000000"),
    ("  A2  Review and management of promotional and non-promotional materials  (MSIC: 10.05 FTE)", False, 10, "000000"),
    ("  A3  Planning and management of database, survey, and literature review studies  (MRE: 4.55 FTE)", False, 10, "000000"),
    ("  A4  Development and execution of publication and conference presentation strategies  (MRE: 2.92 FTE)", False, 10, "000000"),
    ("  A5  Application, approval, and publication of re-examination results  (PMS: 4.91 FTE)", False, 10, "000000"),
    ("  A6  Publication of post-marketing study results and disclosure to tracking systems  (PMS: 1.41 FTE)", False, 10, "000000"),
    ("  A7  Promotion of data and digital projects  (SME: 0.65 FTE)", False, 10, "000000"),
    (f"  Total: {sum(v for (f,a),v in fte_map.items() if a in AI_ACTIVITIES):.2f} FTE across 5 functions (ME, MSIC, MRE, PMS, SME)", False, 10, "C00000"),
    ("", False, 10, "000000"),
    ("Step 2: Infer employee-level activity participation", True, 10, NAVY),
    ("Source: Communication_matrix__Relationship_work_effort_-_Frequency__Avg__.xlsx (Matrix cells sheet)", False, 10, "000000"),
    ("Each dyad row contains an 'Activities' field listing activities the collaboration concerns.", False, 10, "000000"),
    ("If any AI CoE activity appears in an employee's reported dyad, that employee is flagged as participating.", False, 10, "000000"),
    ("Note: this is an inference — participation is inferred from collaboration context, not direct time allocation.", False, 10, "777777"),
    ("", False, 10, "000000"),
    ("Step 3: Aggregate to sub-unit level", True, 10, NAVY),
    ("A sub-unit is marked as participating in an activity if at least one of its employees participates (binary presence).", False, 10, "000000"),
    ("FTE per sub-unit = function-level FTE divided equally across active sub-units within that function.", False, 10, "000000"),
    ("Source: time-utilization-insights.xlsx (Activity Coverage sheet)", False, 10, "000000"),
    ("", False, 10, "000000"),
    ("Step 4: Compute pairwise overlap scores", True, 10, NAVY),
    ("For each ordered pair of sub-units (i, j):", False, 10, "000000"),
    ("  Overlap count = number of AI activities where BOTH sub-units have at least one participating employee", False, 10, "000000"),
    ("  Combined FTE  = sum of unit-i FTE + unit-j FTE across all shared activities", False, 10, "000000"),
    ("", False, 10, "000000"),
    ("Step 5: Binarize (threshold rule)", True, 10, NAVY),
    ("A cell is marked 1 (consolidation potential) if EITHER condition is met:", False, 10, "000000"),
    (f"  Condition A: Overlap count ≥ {THRESHOLD_SHARED_ACTIVITIES} "
     f"(both units active in at least {THRESHOLD_SHARED_ACTIVITIES} of the same AI activities)",
     False, 10, "000000"),
    (f"  Condition B: Combined FTE ≥ {THRESHOLD_COMBINED_FTE} "
     f"(meaningful shared workload in the same activities)",
     False, 10, "000000"),
    ("The matrix is then symmetrized: if (i,j) = 1 then (j,i) = 1.", False, 10, "000000"),
    ("", False, 10, "000000"),
    ("Step 6: Result", True, 10, NAVY),
    (f"  30×30 sub-unit matrix with {total_marked_pairs} unique pairs marked (out of {n*(n-1)//2} possible off-diagonal pairs).", False, 10, "C00000"),
    ("  See 'Binary DSM (γ matrix)' sheet for the primary output fed into the GA optimizer.", False, 10, "000000"),
    ("", False, 10, "000000"),
    ("Limitation", True, 10, "833C00"),
    ("Activity participation is inferred from collaboration context tags, not direct survey responses about time allocation.", False, 10, "777777"),
    ("Sub-units with zero AI participation (e.g. Medical Governance Unit, Operational Effectiveness) either genuinely do not", False, 10, "777777"),
    ("perform these activities or simply did not tag them in reported collaborations. Validate Sheet 4 against domain knowledge.", False, 10, "777777"),
]

for r_idx, (text, bold, size, color) in enumerate(notes, 1):
    c = ws5.cell(row=r_idx, column=1, value=text)
    c.font = Font(name="Arial", bold=bold, size=size, color=color)
    ws5.row_dimensions[r_idx].height = 15 if text else 8


# ── Sheet 6: Sensitivity Analysis ────────────────────────────────────────────
print("Running sensitivity analysis…")

import math

# Build grid of (sa_thresh, fte_thresh) combinations
sa_values  = list(range(SA_MIN, SA_MAX + 1))
n_steps    = round((SA_FTE_MAX - SA_FTE_MIN) / SA_FTE_STEP)
fte_values = [round(SA_FTE_MIN + i * SA_FTE_STEP, 10) for i in range(n_steps + 1)]

# Pre-compute pair-level raw scores (count, fte) — already in dsm_count / dsm_fte
# We only need upper triangle (i < j) since matrix is symmetric
pair_counts = []
pair_ftes   = []
for i in range(n):
    for j in range(i + 1, n):
        pair_counts.append(int(dsm_count[i][j]))
        pair_ftes.append(float(dsm_fte[i][j]))

def marked_pairs(sa_thresh, fte_thresh):
    """Count unique pairs marked under given thresholds."""
    return sum(
        1 for cnt, fte in zip(pair_counts, pair_ftes)
        if cnt >= sa_thresh or fte >= fte_thresh
    )

# Build result grid: rows = SA thresholds, cols = FTE thresholds
grid = {}
for sa in sa_values:
    for fte in fte_values:
        grid[(sa, fte)] = marked_pairs(sa, fte)

ws6 = wb.create_sheet("Sensitivity Analysis")

ws6["A1"] = "Sensitivity Analysis — Number of Marked Sub-unit Pairs by Threshold Combination"
ws6["A1"].font = Font(name="Arial", bold=True, size=13, color=NAVY)
ws6["A2"] = (
    "Each cell shows the number of unique sub-unit pairs marked as having consolidation potential "
    "under that combination of thresholds (OR logic: pair marked if EITHER condition met)."
)
ws6["A2"].font = Font(name="Arial", size=9, italic=True, color="555555")
ws6["A3"] = (
    f"Possible pairs: {len(pair_counts)}  |  "
    f"Active setting: SA ≥ {THRESHOLD_SHARED_ACTIVITIES}, FTE ≥ {THRESHOLD_COMBINED_FTE}  →  "
    f"{marked_pairs(THRESHOLD_SHARED_ACTIVITIES, THRESHOLD_COMBINED_FTE)} pairs marked"
)
ws6["A3"].font = Font(name="Arial", size=10, bold=True, color="C00000")

# Layout: row 5 = column headers (FTE thresholds)
#         col A = row label, col B = SA threshold values, data from col C
SA_LABEL_ROW  = 6
FTE_LABEL_ROW = 5
DATA_ROW_OFF  = SA_LABEL_ROW
DATA_COL_OFF  = 2   # col C onward

ws6.column_dimensions["A"].width = 36
ws6.column_dimensions["B"].width = 10

# Top-left corner labels
ws6.cell(row=FTE_LABEL_ROW, column=1,
         value="→  Combined FTE threshold  →").font = Font(name="Arial", size=9,
                                                            italic=True, color="555555")
ws6.cell(row=SA_LABEL_ROW - 1, column=2,
         value="SA\\ FTE →").font = Font(name="Arial", bold=True, size=9)

# FTE column headers (row 5)
for j, fte in enumerate(fte_values):
    col = DATA_COL_OFF + 1 + j
    ws6.column_dimensions[get_column_letter(col)].width = 7
    c = ws6.cell(row=FTE_LABEL_ROW, column=col, value=fte)
    c.fill      = PatternFill("solid", fgColor=NAVY)
    c.font      = Font(name="Arial", bold=True, size=9, color="FFFFFF")
    c.alignment = Alignment(horizontal="center", vertical="center")
    c.border    = THIN_BORDER

# SA row headers + data
max_val = max(grid.values())
min_val = min(grid.values())
total_possible = len(pair_counts)

def cell_color(val, lo, hi):
    """White (low) → dark red (high) gradient."""
    if hi == lo:
        return "FFFFFF"
    ratio = (val - lo) / (hi - lo)
    # interpolate: white (255,255,255) → dark red (192,0,0)
    r = 255
    g = int(255 * (1 - ratio))
    b = int(255 * (1 - ratio))
    return f"{r:02X}{g:02X}{b:02X}"

for i, sa in enumerate(sa_values):
    row = DATA_ROW_OFF + i
    ws6.row_dimensions[row].height = 16

    # SA threshold label
    lbl = ws6.cell(row=row, column=1,
                   value=f"Shared-activity threshold ≥ {sa}")
    lbl.font      = Font(name="Arial", size=9)
    lbl.alignment = Alignment(horizontal="left", vertical="center")

    sa_cell = ws6.cell(row=row, column=2, value=sa)
    sa_cell.fill      = PatternFill("solid", fgColor=NAVY)
    sa_cell.font      = Font(name="Arial", bold=True, size=9, color="FFFFFF")
    sa_cell.alignment = Alignment(horizontal="center", vertical="center")
    sa_cell.border    = THIN_BORDER

    for j, fte in enumerate(fte_values):
        col = DATA_COL_OFF + 1 + j
        val = grid[(sa, fte)]
        pct = 100 * val / total_possible

        c = ws6.cell(row=row, column=col, value=val)
        c.fill      = PatternFill("solid", fgColor=cell_color(val, min_val, max_val))
        c.font      = Font(name="Arial", size=9, bold=True,
                           color="FFFFFF" if val > (max_val * 0.7) else "000000")
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border    = THIN_BORDER

        # Highlight the active setting
        if sa == THRESHOLD_SHARED_ACTIVITIES and abs(fte - THRESHOLD_COMBINED_FTE) < 1e-9:
            c.border = Border(
                left=Side(style="medium", color="000000"),
                right=Side(style="medium", color="000000"),
                top=Side(style="medium", color="000000"),
                bottom=Side(style="medium", color="000000"),
            )
            c.font = Font(name="Arial", size=9, bold=True, color="000000",
                          underline="single")

# Percentage sub-table — repeat grid but show % of total pairs
PCT_ROW_START = DATA_ROW_OFF + len(sa_values) + 3

ws6.cell(row=PCT_ROW_START - 1, column=1,
         value="Same grid as % of total possible pairs "
               f"({total_possible} pairs)").font = Font(
    name="Arial", bold=True, size=10, color=MID_BLUE)

# FTE headers again
for j, fte in enumerate(fte_values):
    col = DATA_COL_OFF + 1 + j
    c = ws6.cell(row=PCT_ROW_START, column=col, value=fte)
    c.fill      = PatternFill("solid", fgColor=MID_BLUE)
    c.font      = Font(name="Arial", bold=True, size=9, color="FFFFFF")
    c.alignment = Alignment(horizontal="center", vertical="center")
    c.border    = THIN_BORDER

ws6.cell(row=PCT_ROW_START, column=2, value="SA \\ FTE").font = Font(
    name="Arial", bold=True, size=9)

for i, sa in enumerate(sa_values):
    row = PCT_ROW_START + 1 + i
    ws6.row_dimensions[row].height = 16

    lbl = ws6.cell(row=row, column=1,
                   value=f"Shared-activity threshold ≥ {sa}")
    lbl.font = Font(name="Arial", size=9)

    sa_cell = ws6.cell(row=row, column=2, value=sa)
    sa_cell.fill      = PatternFill("solid", fgColor=MID_BLUE)
    sa_cell.font      = Font(name="Arial", bold=True, size=9, color="FFFFFF")
    sa_cell.alignment = Alignment(horizontal="center", vertical="center")
    sa_cell.border    = THIN_BORDER

    for j, fte in enumerate(fte_values):
        col = DATA_COL_OFF + 1 + j
        val = grid[(sa, fte)]
        pct = round(100 * val / total_possible, 1)

        c = ws6.cell(row=row, column=col, value=f"{pct}%")
        c.fill      = PatternFill("solid", fgColor=cell_color(val, min_val, max_val))
        c.font      = Font(name="Arial", size=9, bold=True,
                           color="FFFFFF" if val > (max_val * 0.7) else "000000")
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border    = THIN_BORDER

        if sa == THRESHOLD_SHARED_ACTIVITIES and abs(fte - THRESHOLD_COMBINED_FTE) < 1e-9:
            c.border = Border(
                left=Side(style="medium", color="000000"),
                right=Side(style="medium", color="000000"),
                top=Side(style="medium", color="000000"),
                bottom=Side(style="medium", color="000000"),
            )
            c.font = Font(name="Arial", size=9, bold=True, color="000000",
                          underline="single")

# Legend note
note_row = PCT_ROW_START + len(sa_values) + 3
ws6.cell(row=note_row, column=1,
         value="Colour scale: white = fewest marked pairs → dark red = most marked pairs.").font = Font(
    name="Arial", size=9, italic=True, color="555555")
ws6.cell(row=note_row + 1, column=1,
         value="Underlined/outlined cell = currently active threshold setting in this script.").font = Font(
    name="Arial", size=9, italic=True, color="555555")
ws6.cell(row=note_row + 2, column=1,
         value=f"Note: OR logic — a pair is marked if shared-activity count ≥ SA threshold "
               f"OR combined FTE ≥ FTE threshold. "
               f"Stricter thresholds on BOTH axes are needed to reduce marks meaningfully.").font = Font(
    name="Arial", size=9, italic=True, color="555555")

# Print summary to console
print(f"  Grid: {len(sa_values)} SA values × {len(fte_values)} FTE values "
      f"= {len(sa_values)*len(fte_values)} combinations")
print(f"  Marked pairs range: {min_val} – {max_val} (out of {total_possible} possible)")
print(f"  Active setting (SA≥{THRESHOLD_SHARED_ACTIVITIES}, FTE≥{THRESHOLD_COMBINED_FTE}): "
      f"{marked_pairs(THRESHOLD_SHARED_ACTIVITIES, THRESHOLD_COMBINED_FTE)} pairs")

# ── Save ──────────────────────────────────────────────────────────────────────
wb.save(OUTPUT)
print(f"\nDone. Output saved to: {OUTPUT}")
print(f"  Sheets: {[ws.title for ws in wb.worksheets]}")
print(f"  Binary DSM: {n}×{n} matrix, {total_marked_pairs} unique pairs marked "
      f"(SA≥{THRESHOLD_SHARED_ACTIVITIES}, FTE≥{THRESHOLD_COMBINED_FTE}).")
