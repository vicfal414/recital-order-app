import json
import random
import streamlit as st
import pandas as pd
from typing import List, Dict

# --- Page Config ---
st.set_page_config(
    page_title="Recital Order Generator",
    page_icon="🩰",
    layout="wide"
)

# --- Styling ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Lato:wght@300;400&display=swap');

        html, body, [class*="css"] {
            font-family: 'Lato', sans-serif;
        }
        h1, h2, h3 {
            font-family: 'Playfair Display', serif;
        }
        .main-title {
            font-family: 'Playfair Display', serif;
            font-size: 2.8rem;
            color: #2c2c2c;
            letter-spacing: 1px;
        }
        .subtitle {
            font-family: 'Lato', sans-serif;
            font-weight: 300;
            color: #888;
            font-size: 1.1rem;
            margin-top: -10px;
            margin-bottom: 30px;
        }
        .part-header {
            font-family: 'Playfair Display', serif;
            font-size: 1.5rem;
            color: #b5566e;
            border-bottom: 2px solid #f0c0cc;
            padding-bottom: 6px;
            margin-top: 30px;
        }
        .stButton > button {
            background-color: #b5566e;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 0.6rem 2rem;
            font-family: 'Lato', sans-serif;
            font-size: 1rem;
            font-weight: 400;
            letter-spacing: 1px;
            transition: background 0.2s;
        }
        .stButton > button:hover {
            background-color: #8f3f55;
            color: white;
        }
        .stDownloadButton > button {
            background-color: #f5f0eb;
            color: #2c2c2c;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-family: 'Lato', sans-serif;
        }
        .stDownloadButton > button:hover {
            background-color: #ede5db;
            color: #2c2c2c;
        }
        .success-box {
            background: #f0faf4;
            border-left: 4px solid #4caf7d;
            padding: 12px 18px;
            border-radius: 4px;
            margin-bottom: 20px;
            font-family: 'Lato', sans-serif;
            color: #2a6041;
        }
        .error-box {
            background: #fdf0f0;
            border-left: 4px solid #e05c5c;
            padding: 12px 18px;
            border-radius: 4px;
            margin-bottom: 20px;
            font-family: 'Lato', sans-serif;
            color: #7a2020;
        }
        .warning-box {
            background: #fffbf0;
            border-left: 4px solid #f0a500;
            padding: 12px 18px;
            border-radius: 4px;
            margin-bottom: 20px;
            font-family: 'Lato', sans-serif;
            color: #7a5500;
        }
    </style>
""", unsafe_allow_html=True)

# --- Core Logic ---
MIN_GAP_SIZE = 3


def get_student_gap(sequence: List[Dict], student_name: str) -> int:
    current_index = len(sequence)
    for i in range(current_index - 1, -1, -1):
        if student_name in sequence[i]['classList']:
            return current_index - i - 1
    return 999


def passes_base_rules(sequence: List[Dict], routine: Dict) -> bool:
    """
    Returns True if the routine satisfies the two hard scheduling rules:
      1. No back-to-back same style (SOLOs are exempt).
      2. Every student has at least MIN_GAP_SIZE routines since their last appearance.
    Does NOT enforce the TOT placement preference — that is handled by fill_part.
    """
    if sequence:
        if routine['style'] == sequence[-1]['style'] and routine['style'] != "SOLO":
            return False
    for student in routine['classList']:
        if get_student_gap(sequence, student) < MIN_GAP_SIZE:
            return False
    return True


def fill_part(
    fixed_start: List[Dict],
    pool: List[Dict],
    target_size: int,
    tot_cutoff: int,
    adult_tap: Dict = None,
    adult_tap_slot: int = None,
) -> tuple:
    """
    Build one part of the recital.

    Parameters
    ----------
    fixed_start   : classes already locked into the front (e.g. [opening, teen_tap])
    pool          : available classes to draw from (not mutated — a copy is used)
    target_size   : total number of slots in this part (not counting the senior_jazz anchor)
    tot_cutoff    : 0-based index; TOT classes are preferred before this position,
                    but placed after it only as a last resort (never hard-blocked)
    adult_tap     : if provided, must be inserted at adult_tap_slot
    adult_tap_slot: 0-based index where adult_tap is forced in (e.g. 20 for show slot 21)

    Returns
    -------
    (part, leftover_pool, success)
    """
    part      = list(fixed_start)
    remaining = list(pool)

    while len(part) < target_size:
        pos = len(part)

        # Insert the adult_tap anchor at its reserved slot
        if adult_tap is not None and pos == adult_tap_slot:
            part.append(adult_tap)
            continue

        in_first_half = pos < tot_cutoff

        # Split valid candidates into TOT and non-TOT
        valid_tot     = []
        valid_non_tot = []
        for i, c in enumerate(remaining):
            if passes_base_rules(part, c):
                if c['style'] == 'TOT':
                    valid_tot.append((i, c))
                else:
                    valid_non_tot.append((i, c))

        if not valid_tot and not valid_non_tot:
            # Completely stuck — signal failure so the outer loop retries
            return part, remaining, False

        if in_first_half and valid_tot:
            # Actively prefer TOT while we're still in the first half
            chosen_i, chosen = random.choice(valid_tot)
        elif valid_non_tot:
            # Normal slot: any valid non-TOT class
            chosen_i, chosen = random.choice(valid_non_tot)
        else:
            # Past the cutoff but only TOT classes are valid — place with a warning
            chosen_i, chosen = random.choice(valid_tot)

        part.append(chosen)
        remaining.pop(chosen_i)

    return part, remaining, True


def generate_schedule(routines: List[Dict], max_attempts: int = 5000):
    def pull(fragment, src):
        frag = fragment.lower()
        for i, r in enumerate(src):
            if frag in r['className'].lower():
                return src.pop(i)
        return None

    for _ in range(max_attempts):
        pool = routines[:]
        random.shuffle(pool)

        opening     = pull("Opening",           pool)
        teen_tap    = pull("TEEN/JR. COMP TAP", pool)
        production  = pull("Production",        pool)
        senior_jazz = pull("SENIOR COMP JAZZ",  pool)
        adult_tap   = pull("ADULT TAP",         pool)

        if not all([opening, teen_tap, production, senior_jazz, adult_tap]):
            return None, (
                "Could not find one or more required fixed routines "
                "(Opening, TEEN/JR. COMP TAP, Production, SENIOR COMP JAZZ, ADULT TAP). "
                "Please check your data file."
            )

        total   = len(routines)
        p1_size = total // 2      # number of slots in Part 1
        p2_size = total - p1_size  # slots in Part 2 (senior_jazz added separately after)

        # ── Part 1 ──────────────────────────────────────────────────────────
        # Slot 0 = opening, slot 1 = teen_tap, then fill freely to p1_size.
        # TOT preference: first half of Part 1, i.e. index < p1_size // 2.
        p1_tot_cutoff = p1_size // 2

        part1, leftover, ok1 = fill_part(
            fixed_start=[opening, teen_tap],
            pool=pool,
            target_size=p1_size,
            tot_cutoff=p1_tot_cutoff,
        )
        if not ok1:
            continue

        # ── Part 2 ──────────────────────────────────────────────────────────
        # Slot 0 = production, slot 20 = adult_tap, last = senior_jazz (appended below).
        # p2_size includes production + regular slots + adult_tap slot.
        # TOT preference: first half of Part 2, i.e. index < p2_size // 2.
        p2_tot_cutoff = p2_size // 2

        part2, _, ok2 = fill_part(
            fixed_start=[production],
            pool=leftover,
            target_size=p2_size,
            tot_cutoff=p2_tot_cutoff,
            adult_tap=adult_tap,
            adult_tap_slot=20,   # 0-based → show position 21
        )
        if not ok2:
            continue

        # Senior Jazz is always the final number
        part2.append(senior_jazz)

        return add_order_to_recital({"Part 1": part1, "Part 2": part2}), None

    return None, (
        "Could not generate a valid schedule after many attempts. "
        "Try again — the randomizer may find a valid path on another run."
    )


def add_order_to_recital(data: Dict) -> Dict:
    current_order = 1
    for part in ["Part 1", "Part 2"]:
        if part in data and isinstance(data[part], list):
            updated = []
            for item in data[part]:
                updated.append({
                    "order":     current_order,
                    "className": item.get("className"),
                    "style":     item.get("style"),
                    "classList": item.get("classList"),
                })
                current_order += 1
            data[part] = updated
    return data


def check_tot_placement(result: Dict) -> List[str]:
    """Return warning strings for any TOT class in the second half of its part."""
    warnings = []
    for part_name in ("Part 1", "Part 2"):
        routines = result[part_name]
        cutoff   = len(routines) // 2
        for idx, r in enumerate(routines):
            if r["style"] == "TOT" and idx >= cutoff:
                warnings.append(
                    f"{part_name} #{r['order']}: {r['className']} "
                    f"(position {idx + 1} of {len(routines)} — past midpoint {cutoff})"
                )
    return warnings


def generate_quick_change_report(order_data: Dict) -> str:
    lines = [
        "RECITAL QUICK CHANGE REPORT (2026)",
        "==================================",
        "Validation Rules:",
        f"1. Minimum Enforced Gap: {MIN_GAP_SIZE} routines in between.",
        "2. Report Flag: Any gap of 4 or less routines.",
        "   (Note: A gap of 3 or 4 is VALID but tight. A gap < 3 is INVALID.)\n",
    ]

    def scan_part(part_name, routine_list):
        lines.append(f"--- {part_name} ---")
        count = 0
        for i, routine in enumerate(routine_list):
            for student in routine['classList']:
                for prev_i in range(i - 1, -1, -1):
                    prev = routine_list[prev_i]
                    if student in prev['classList']:
                        gap = i - prev_i - 1
                        if gap <= 4:
                            count += 1
                            status = "VALID (Tight)" if gap >= MIN_GAP_SIZE else "**INVALID/ERROR**"
                            lines.append(f"Student: {student}")
                            lines.append(f"  Status: {status}")
                            lines.append(f"  Gap:    {gap} numbers in between")
                            lines.append(f"  FROM:   #{prev_i+1} {prev['className']}")
                            lines.append(f"  TO:     #{i+1} {routine['className']}")
                            lines.append("-" * 40)
                        break
        if count == 0:
            lines.append("No quick changes detected.")
        lines.append("")

    scan_part("PART 1", order_data["Part 1"])
    scan_part("PART 2", order_data["Part 2"])
    return "\n".join(lines)


# --- UI ---
st.markdown('<div class="main-title">🩰 Recital Order Generator</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Upload your routine data to generate the show order '
    'and quick change report.</div>',
    unsafe_allow_html=True,
)

uploaded_file = st.file_uploader("Upload your recital data file (JSON)", type=["json"])

if uploaded_file:
    try:
        data      = json.load(uploaded_file)
        tot_count = sum(1 for r in data if r.get("style") == "TOT")
        st.markdown(
            f'<div class="success-box">✓ File loaded — <strong>{len(data)} routines</strong> found'
            f'{f" ({tot_count} TOT)" if tot_count else ""}.</div>',
            unsafe_allow_html=True,
        )

        if st.button("✨ Generate Schedule"):
            with st.spinner("Calculating schedule… this may take a moment."):
                result, error = generate_schedule(data)

            if error:
                st.markdown(f'<div class="error-box">⚠️ {error}</div>', unsafe_allow_html=True)
            else:
                json_output   = json.dumps({"Part 1": result["Part 1"], "Part 2": result["Part 2"]}, indent=4)
                report_output = generate_quick_change_report(result)
                has_invalid   = "**INVALID/ERROR**" in report_output
                tot_warnings  = check_tot_placement(result)

                # ── Status banners ─────────────────────────────────────────
                if has_invalid:
                    st.markdown(
                        '<div class="error-box">⚠️ <strong>Invalid Quick Change Detected!</strong> '
                        'This schedule contains one or more students with an invalid gap between '
                        'performances. Please click <em>Generate Schedule</em> again.</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<div class="success-box">✓ Schedule generated successfully! '
                        'No invalid quick changes detected.</div>',
                        unsafe_allow_html=True,
                    )

                if tot_warnings:
                    items = "".join(f"<li>{w}</li>" for w in tot_warnings)
                    st.markdown(
                        f'<div class="warning-box">⚠️ <strong>TOT Placement Notice:</strong> '
                        f'The following TOT classes could not be placed in the first half of their '
                        f'part. Consider regenerating.<ul>{items}</ul></div>',
                        unsafe_allow_html=True,
                    )

                # ── Downloads ──────────────────────────────────────────────
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="⬇ Download Recital Order (JSON)",
                        data=json_output,
                        file_name="recital_order.json",
                        mime="application/json",
                    )
                with col2:
                    st.download_button(
                        label="⬇ Download Quick Change Report (TXT)",
                        data=report_output,
                        file_name="quick_change_report.txt",
                        mime="text/plain",
                    )

                # ── Schedule tables ────────────────────────────────────────
                def make_rows(part_key):
                    part      = result[part_key]
                    half_mark = len(part) // 2
                    rows = []
                    for idx, r in enumerate(part):
                        is_tot = r["style"] == "TOT"
                        tag = ""
                        if is_tot and idx >= half_mark:
                            tag = " ⚠️ TOT (2nd half)"
                        elif is_tot:
                            tag = " ✓ TOT"
                        rows.append({
                            "#":          r["order"],
                            "Class Name": r["className"] + tag,
                            "Style":      r["style"],
                        })
                    return rows

                st.markdown('<div class="part-header">Part 1</div>', unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(make_rows("Part 1")), use_container_width=True, hide_index=True)

                st.markdown('<div class="part-header">Part 2</div>', unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(make_rows("Part 2")), use_container_width=True, hide_index=True)

                # ── Copyable list ──────────────────────────────────────────
                st.markdown('<div class="part-header">Copy as List</div>', unsafe_allow_html=True)
                all_lines  = ["--- Part 1 ---"]
                all_lines += [f"{r['order']}. {r['className']}" for r in result["Part 1"]]
                all_lines += ["", "--- Part 2 ---"]
                all_lines += [f"{r['order']}. {r['className']}" for r in result["Part 2"]]
                st.text_area("", value="\n".join(all_lines), height=300, label_visibility="collapsed")

                # ── Quick change preview ───────────────────────────────────
                st.markdown('<div class="part-header">Quick Change Report Preview</div>', unsafe_allow_html=True)
                st.text(report_output)

    except json.JSONDecodeError:
        st.markdown(
            '<div class="error-box">⚠️ Could not read the file. '
            'Please make sure it is a valid JSON file.</div>',
            unsafe_allow_html=True,
        )
else:
    st.info("👆 Upload your JSON data file above to get started.")
