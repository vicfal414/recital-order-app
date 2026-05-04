import json
import random
import streamlit as st
import pandas as pd
from io import StringIO
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


def is_valid_addition(sequence: List[Dict], routine: Dict,
                      part_length: int = None) -> bool:
    """
    Check whether a routine can be appended to the current sequence.

    Extra constraint: TOT-style routines must land in the first half of
    their part (position < part_length // 2).  part_length should be the
    estimated total length of the part being built.
    """
    if sequence:
        previous = sequence[-1]
        # No back-to-back same style (except SOLO)
        if routine['style'] == previous['style'] and routine['style'] != "SOLO":
            return False

    # Student spacing
    for student in routine['classList']:
        if get_student_gap(sequence, student) < MIN_GAP_SIZE:
            return False

    # TOT must be in the first half of the part
    if routine['style'] == 'TOT' and part_length is not None:
        if len(sequence) >= part_length // 2:
            return False

    return True


def generate_schedule(routines: List[Dict], max_attempts: int = 5000):
    def pull(name_fragment, source_list):
        for i, r in enumerate(source_list):
            if name_fragment.lower() in r['className'].lower():
                return source_list.pop(i)
        return None

    for attempt in range(max_attempts):
        pool = routines[:]
        random.shuffle(pool)

        opening     = pull("Opening",             pool)
        teen_tap    = pull("TEEN/JR. COMP TAP",   pool)
        production  = pull("Production",           pool)
        senior_jazz = pull("SENIOR COMP JAZZ",     pool)
        adult_tap   = pull("ADULT TAP",            pool)

        if not all([opening, teen_tap, production, senior_jazz, adult_tap]):
            return None, (
                "Could not find one or more required fixed routines "
                "(Opening, TEEN/JR. COMP TAP, Production, SENIOR COMP JAZZ, ADULT TAP). "
                "Please check your data file."
            )

        # ── Part 1 ──────────────────────────────────────────────────────────
        # Fixed: opening (pos 0), teen_tap (pos 1)
        # TOT classes must appear before the halfway mark of Part 1.
        # We don't know the exact final length yet, so split the remaining
        # pool intelligently: send half the TOT classes to Part 1 so they
        # have a realistic chance of landing early.

        tot_pool     = [c for c in pool if c['style'] == 'TOT']
        non_tot_pool = [c for c in pool if c['style'] != 'TOT']
        random.shuffle(tot_pool)
        random.shuffle(non_tot_pool)

        total_count = len(routines)
        half_point  = total_count // 2

        # Rough Part 1 length = half_point (includes opening + teen_tap)
        p1_length_estimate = half_point

        # Split TOT classes roughly evenly across both parts
        tot_for_p1 = tot_pool[: len(tot_pool) // 2]
        tot_for_p2 = tot_pool[len(tot_pool) // 2 :]

        p1_candidates = tot_for_p1 + non_tot_pool[: half_point - 2 - len(tot_for_p1)]
        p2_candidates = (
            tot_for_p2
            + non_tot_pool[half_point - 2 - len(tot_for_p1):]
        )
        random.shuffle(p1_candidates)
        random.shuffle(p2_candidates)

        part1 = [opening, teen_tap]
        success_p1 = True

        while len(part1) < half_point:
            found = False
            for i, candidate in enumerate(p1_candidates):
                if is_valid_addition(part1, candidate,
                                     part_length=p1_length_estimate):
                    part1.append(p1_candidates.pop(i))
                    found = True
                    break
            if not found:
                # If we still have TOT candidates blocking us past the halfway
                # mark, fall back to any non-TOT candidate ignoring the TOT rule
                fallback_found = False
                for i, candidate in enumerate(p1_candidates):
                    if candidate['style'] != 'TOT' and is_valid_addition(
                            part1, candidate):
                        part1.append(p1_candidates.pop(i))
                        fallback_found = True
                        break
                if not fallback_found:
                    success_p1 = False
                    break

        if not success_p1:
            continue

        # Any Part 1 candidates that didn't fit go back into Part 2 pool
        p2_candidates = p1_candidates + p2_candidates

        # ── Part 2 ──────────────────────────────────────────────────────────
        # Fixed: production (pos 0), adult_tap (pos 20), senior_tap (last)
        # TOT classes must appear before the halfway mark of Part 2.

        # Estimate Part 2 length = everything left + adult_tap + senior_tap
        p2_length_estimate = len(p2_candidates) + 3  # production + adult_tap + senior_tap

        part2 = [production]
        success_p2 = True

        while p2_candidates:
            current_slot = len(part2) + 1   # 1-indexed position about to be filled
            if current_slot == 21:
                part2.append(adult_tap)
                continue

            found = False
            for i, candidate in enumerate(p2_candidates):
                if is_valid_addition(part2, candidate,
                                     part_length=p2_length_estimate):
                    part2.append(p2_candidates.pop(i))
                    found = True
                    break

            if not found:
                # Relax TOT constraint as fallback (prefer not to, but don't fail)
                fallback_found = False
                for i, candidate in enumerate(p2_candidates):
                    if candidate['style'] != 'TOT' and is_valid_addition(
                            part2, candidate):
                        part2.append(p2_candidates.pop(i))
                        fallback_found = True
                        break
                if not fallback_found:
                    success_p2 = False
                    break

        if not success_p2:
            continue

        # Ensure adult_tap is in position 21 if not already inserted
        if adult_tap not in part2:
            part2.append(adult_tap)

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
            updated_part = []
            for item in data[part]:
                updated_part.append({
                    "order":     current_order,
                    "className": item.get("className"),
                    "style":     item.get("style"),
                    "classList": item.get("classList"),
                })
                current_order += 1
            data[part] = updated_part
    return data


def check_tot_placement(result: Dict):
    """
    Return a list of warning strings for any TOT class that ended up in
    the second half of its part.
    """
    warnings = []
    for part_name in ("Part 1", "Part 2"):
        routines = result[part_name]
        cutoff = len(routines) // 2
        for r in routines:
            # order is 1-indexed; convert to 0-indexed for comparison
            if r["style"] == "TOT" and (r["order"] - 1) % len(routines) >= cutoff:
                warnings.append(
                    f"{part_name} #{r['order']}: {r['className']} "
                    f"(TOT in second half — position {r['order']} of {len(routines)})"
                )
    return warnings


def generate_quick_change_report(order_data: Dict) -> str:
    lines = []
    lines.append("RECITAL QUICK CHANGE REPORT (2026)")
    lines.append("==================================")
    lines.append("Validation Rules:")
    lines.append(f"1. Minimum Enforced Gap: {MIN_GAP_SIZE} routines in between.")
    lines.append("2. Report Flag: Any gap of 4 or less routines.")
    lines.append(
        "   (Note: A gap of 3 or 4 is VALID but tight. A gap < 3 is INVALID.)\n"
    )

    def scan_part(part_name, routine_list):
        lines.append(f"--- {part_name} ---")
        count = 0
        for i, routine in enumerate(routine_list):
            for student in routine['classList']:
                for prev_i in range(i - 1, -1, -1):
                    prev_routine = routine_list[prev_i]
                    if student in prev_routine['classList']:
                        gap = i - prev_i - 1
                        if gap <= 4:
                            count += 1
                            status = (
                                "VALID (Tight)"
                                if gap >= MIN_GAP_SIZE
                                else "**INVALID/ERROR**"
                            )
                            lines.append(f"Student: {student}")
                            lines.append(f"  Status: {status}")
                            lines.append(f"  Gap:    {gap} numbers in between")
                            lines.append(f"  FROM:   #{prev_i+1} {prev_routine['className']}")
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
        data = json.load(uploaded_file)
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
                st.markdown(
                    f'<div class="error-box">⚠️ {error}</div>',
                    unsafe_allow_html=True,
                )
            else:
                json_output   = json.dumps(
                    {"Part 1": result["Part 1"], "Part 2": result["Part 2"]}, indent=4
                )
                report_output = generate_quick_change_report(result)
                has_invalid   = "**INVALID/ERROR**" in report_output
                tot_warnings  = check_tot_placement(result)

                # ── Status banners ──────────────────────────────────────────
                if has_invalid:
                    st.markdown(
                        '<div class="error-box">'
                        '⚠️ <strong>Invalid Quick Change Detected!</strong> This schedule contains '
                        'one or more students with an invalid gap between performances. '
                        'Please click <em>Generate Schedule</em> again to try a new order.'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<div class="success-box">✓ Schedule generated successfully! '
                        'No invalid quick changes detected.</div>',
                        unsafe_allow_html=True,
                    )

                if tot_warnings:
                    warning_items = "".join(f"<li>{w}</li>" for w in tot_warnings)
                    st.markdown(
                        f'<div class="warning-box">'
                        f'⚠️ <strong>TOT Placement Notice:</strong> The following TOT classes '
                        f'could not be placed in the first half of their part. '
                        f'Consider regenerating.<ul>{warning_items}</ul>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                # ── Downloads ───────────────────────────────────────────────
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

                # ── Schedule display ────────────────────────────────────────
                def make_rows(part_key):
                    part      = result[part_key]
                    half_mark = len(part) // 2
                    rows = []
                    for r in part:
                        pos       = r["order"]
                        part_pos  = part.index(r)   # 0-indexed within the part
                        is_tot    = r["style"] == "TOT"
                        in_second = part_pos >= half_mark
                        tag = ""
                        if is_tot and in_second:
                            tag = " ⚠️ TOT (2nd half)"
                        elif is_tot:
                            tag = " ✓ TOT"
                        rows.append({
                            "#":          pos,
                            "Class Name": r["className"] + tag,
                            "Style":      r["style"],
                        })
                    return rows

                st.markdown('<div class="part-header">Part 1</div>', unsafe_allow_html=True)
                st.dataframe(
                    pd.DataFrame(make_rows("Part 1")),
                    use_container_width=True,
                    hide_index=True,
                )

                st.markdown('<div class="part-header">Part 2</div>', unsafe_allow_html=True)
                st.dataframe(
                    pd.DataFrame(make_rows("Part 2")),
                    use_container_width=True,
                    hide_index=True,
                )

                # ── Copyable list ───────────────────────────────────────────
                st.markdown('<div class="part-header">Copy as List</div>', unsafe_allow_html=True)
                all_lines = ["--- Part 1 ---"]
                all_lines += [f"{r['order']}. {r['className']}" for r in result["Part 1"]]
                all_lines += ["", "--- Part 2 ---"]
                all_lines += [f"{r['order']}. {r['className']}" for r in result["Part 2"]]
                st.text_area(
                    "",
                    value="\n".join(all_lines),
                    height=300,
                    label_visibility="collapsed",
                )

                # ── Quick change report preview ─────────────────────────────
                st.markdown(
                    '<div class="part-header">Quick Change Report Preview</div>',
                    unsafe_allow_html=True,
                )
                st.text(report_output)

    except json.JSONDecodeError:
        st.markdown(
            '<div class="error-box">⚠️ Could not read the file. '
            'Please make sure it is a valid JSON file.</div>',
            unsafe_allow_html=True,
        )
else:
    st.info("👆 Upload your JSON data file above to get started.")
