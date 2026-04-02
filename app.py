import json
import random
import streamlit as st
import pandas as pd
from io import StringIO

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
    </style>
""", unsafe_allow_html=True)

# --- Core Logic (from original script) ---
MIN_GAP_SIZE = 3

def get_student_gap(sequence, student_name):
    current_index = len(sequence)
    for i in range(current_index - 1, -1, -1):
        if student_name in sequence[i]['classList']:
            return current_index - i - 1
    return 999

def is_valid_addition(sequence, routine):
    if not sequence:
        return True
    previous_routine = sequence[-1]
    if routine['style'] == previous_routine['style'] and routine['style'] != "SOLO":
        return False
    for student in routine['classList']:
        gap = get_student_gap(sequence, student)
        if gap < MIN_GAP_SIZE:
            return False
    return True

def generate_schedule(routines, max_attempts=5000):
    def pull(name_fragment, source_list):
        for i, r in enumerate(source_list):
            if name_fragment.lower() in r['className'].lower():
                return source_list.pop(i)
        return None

    for attempt in range(max_attempts):
        pool = routines[:]
        random.shuffle(pool)

        opening = pull("Opening", pool)
        teen_tap = pull("TEEN/JR. COMP TAP", pool)
        production = pull("Production", pool)
        senior_tap = pull("SENIOR COMP TAP", pool)
        adult_tap = pull("ADULT TAP", pool)

        if not all([opening, teen_tap, production, senior_tap, adult_tap]):
            return None, "Could not find one or more required fixed routines (Opening, TEEN/JR. COMP TAP, Production, SENIOR COMP TAP, ADULT TAP). Please check your data file."

        part1 = [opening, teen_tap]
        total_count = len(routines)
        half_point = total_count // 2

        success_p1 = True
        while len(part1) < half_point:
            found_candidate = False
            for i, candidate in enumerate(pool):
                if is_valid_addition(part1, candidate):
                    part1.append(pool.pop(i))
                    found_candidate = True
                    break
            if not found_candidate:
                success_p1 = False
                break

        if not success_p1:
            continue

        part2 = [production]
        success_p2 = True
        while len(pool) > 0:
            current_slot = len(part2) + 1
            if current_slot == 21:
                part2.append(adult_tap)
                continue
            found_candidate = False
            for i, candidate in enumerate(pool):
                if is_valid_addition(part2, candidate):
                    part2.append(pool.pop(i))
                    found_candidate = True
                    break
            if not found_candidate:
                success_p2 = False
                break

        if not success_p2:
            continue

        if adult_tap not in part2:
            part2.append(adult_tap)

        part2.append(senior_tap)

        return add_order_to_recital({"Part 1": part1, "Part 2": part2}), None

    return None, "Could not generate a valid schedule after many attempts. Try again — the randomizer may find a valid path on another run."

def add_order_to_recital(data):
    current_order = 1
    for part in ["Part 1", "Part 2"]:
        if part in data and isinstance(data[part], list):
            updated_part = []
            for item in data[part]:
                ordered_item = {
                    "order": current_order,
                    "className": item.get("className"),
                    "style": item.get("style"),
                    "classList": item.get("classList")
                }
                updated_part.append(ordered_item)
                current_order += 1
            data[part] = updated_part
    return data

def generate_quick_change_report(order_data):
    lines = []
    lines.append("RECITAL QUICK CHANGE REPORT (2026)")
    lines.append("==================================")
    lines.append("Validation Rules:")
    lines.append(f"1. Minimum Enforced Gap: {MIN_GAP_SIZE} routines in between.")
    lines.append("2. Report Flag: Any gap of 4 or less routines.")
    lines.append("   (Note: A gap of 3 or 4 is VALID but tight. A gap < 3 is INVALID.)\n")

    def scan_part(part_name, routine_list):
        lines.append(f"--- {part_name} ---")
        count = 0
        for i, routine in enumerate(routine_list):
            students = routine['classList']
            for student in students:
                for prev_i in range(i - 1, -1, -1):
                    prev_routine = routine_list[prev_i]
                    if student in prev_routine['classList']:
                        gap = i - prev_i - 1
                        if gap <= 4:
                            count += 1
                            status = "VALID (Tight)" if gap >= MIN_GAP_SIZE else "**INVALID/ERROR**"
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
st.markdown('<div class="subtitle">Upload your routine data to generate the show order and quick change report.</div>', unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload your recital data file (JSON)", type=["json"])

if uploaded_file:
    try:
        data = json.load(uploaded_file)
        st.markdown(f'<div class="success-box">✓ File loaded — <strong>{len(data)} routines</strong> found.</div>', unsafe_allow_html=True)

        if st.button("✨ Generate Schedule"):
            with st.spinner("Calculating schedule... this may take a moment."):
                result, error = generate_schedule(data)

            if error:
                st.markdown(f'<div class="error-box">⚠️ {error}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="success-box">✓ Schedule generated successfully!</div>', unsafe_allow_html=True)

                # --- Downloads ---
                json_output = json.dumps({"Part 1": result["Part 1"], "Part 2": result["Part 2"]}, indent=4)
                report_output = generate_quick_change_report(result)

                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="⬇ Download Recital Order (JSON)",
                        data=json_output,
                        file_name="recital_order.json",
                        mime="application/json"
                    )
                with col2:
                    st.download_button(
                        label="⬇ Download Quick Change Report (TXT)",
                        data=report_output,
                        file_name="quick_change_report.txt",
                        mime="text/plain"
                    )

                # --- Display Order ---
                st.markdown('<div class="part-header">Part 1</div>', unsafe_allow_html=True)
                p1_rows = [{"#": r["order"], "Class Name": r["className"]} for r in result["Part 1"]]
                st.dataframe(pd.DataFrame(p1_rows), use_container_width=True, hide_index=True)

                st.markdown('<div class="part-header">Part 2</div>', unsafe_allow_html=True)
                p2_rows = [{"#": r["order"], "Class Name": r["className"]} for r in result["Part 2"]]
                st.dataframe(pd.DataFrame(p2_rows), use_container_width=True, hide_index=True)

                # --- Copyable List ---
                st.markdown('<div class="part-header">Copy as List</div>', unsafe_allow_html=True)
                all_lines = ["--- Part 1 ---"]
                all_lines += [f"{r['order']}. {r['className']}" for r in result["Part 1"]]
                all_lines += ["", "--- Part 2 ---"]
                all_lines += [f"{r['order']}. {r['className']}" for r in result["Part 2"]]
                st.text_area("", value="\n".join(all_lines), height=300, label_visibility="collapsed")

                # --- Quick Change Summary ---
                st.markdown('<div class="part-header">Quick Change Report Preview</div>', unsafe_allow_html=True)
                st.text(report_output)

    except json.JSONDecodeError:
        st.markdown('<div class="error-box">⚠️ Could not read the file. Please make sure it is a valid JSON file.</div>', unsafe_allow_html=True)
else:
    st.info("👆 Upload your JSON data file above to get started.")
