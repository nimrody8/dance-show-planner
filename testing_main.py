import streamlit as st
import pandas as pd
import io
import json

# הגדרת תצורת עמוד - תמיכה ב-RTL לעברית
st.set_page_config(page_title="מנהל סדר הופעות - אולפן למחול", layout="wide", initial_sidebar_state="expanded")

# יצירת סגנון עיצוב בסיסי לעברית וישור לימין
st.markdown("""
<style>
html, body, [class*="css"]  {
    direction: rtl;
    text-align: right;
}
.reportview-container .main .block-container {
    direction: rtl;
    text-align: right;
}
table {
    width: 100% !important;
}
.block-container {
    max-width: 100% !important;
    padding-left: 2rem;
    padding-right: 2rem;
}
section[data-testid="stSidebar"] {
    direction: rtl;
    text-align: right;
}
h1, h2, h3, h4, h5, h6, p, label, span {
    direction: rtl !important;
    text-align: right !important;
}
div[data-baseweb="select"] {
    direction: rtl;
    text-align: right;
}
input {
    direction: rtl;
    text-align: right;
}
button {
    direction: rtl;
    text-align: right;
}
thead tr th {
    text-align: right !important;
}
tbody tr td {
    text-align: right !important;
}
pre, code {
    direction: rtl !important;
    text-align: right !important;
}
div[style*="overflow-x"] {
    direction: rtl;
}
</style>
""", unsafe_allow_html=True)

st.title("מופע סוף שנה - אופטימיזציית סדר עלייה 🩰")

# --- אתחול בסיסי של ה-Session State ---
if 'manual_order' not in st.session_state:
    st.session_state.manual_order = []
if 'loaded_configs' not in st.session_state:
    st.session_state.loaded_configs = {}

# --- פונקציות עזר ללוגיקה ושמירת מצב ---
def validate_excel(df):
    required_cols = ['שם תלמידה', 'שם משפחה', 'גיל', 'קבוצה']
    missing_cols = [col for col in required_cols if col not in df.columns]
    return missing_cols

def serialize_state():
    """אוסף את כל הנתונים מהווידג'טים והמערך ושומר לקובץ JSON"""
    current_fixed = {}
    num_fixed = st.session_state.get("num_fixed_input", 0)
    for i in range(num_fixed):
        g = st.session_state.get(f"fixed_group_{i}")
        p = st.session_state.get(f"fixed_pos_{i}")
        if g and p:
            current_fixed[int(p) - 1] = g

    data = {
        "manual_order": st.session_state.get("manual_order", []),
        "gap_size": st.session_state.get("gap_size_input", 2),
        "max_solutions": st.session_state.get("max_solutions_input", 100),
        "selected_groups": st.session_state.get("selected_groups_input", []),
        "start_groups": st.session_state.get("start_groups_input", []),
        "end_groups": st.session_state.get("end_groups_input", []),
        "fixed_positions": current_fixed
    }
    return json.dumps(data, ensure_ascii=False).encode("utf-8")

def load_state_callback():
    """קריאת קובץ ה-JSON בצורה בטוחה לתוך מילון אחסון זמני כדי למנוע לולאות Rerun"""
    if st.session_state.load_state_file is not None:
        try:
            data = json.load(st.session_state.load_state_file)
            st.session_state.loaded_configs = data
            st.session_state.manual_order = data.get("manual_order", [])
            st.toast("✅ נתוני הקובץ הועלו! ההגדרות מעודכנות בסרגל הצד.", icon="💾")
        except Exception as e:
            st.sidebar.error(f"שגיאה בקריאת קובץ המצב: {e}")

def build_data_structures(df):
    group_students = {}
    for _, row in df.iterrows():
        student = f"{row['שם תלמידה']} {row['שם משפחה']}".strip()
        group = str(row['קבוצה']).strip()
        if group not in group_students:
            group_students[group] = set()
        group_students[group].add(student)

    conflict_matrix = {}
    groups = list(group_students.keys())
    for g1 in groups:
        conflict_matrix[g1] = set()
        for g2 in groups:
            if g1 != g2:
                if group_students[g1].intersection(group_students[g2]):
                    conflict_matrix[g1].add(g2)

    return group_students, conflict_matrix

def find_schedules(remaining, current, gap, conflicts, end_groups, max_solutions, fixed_positions):
    pos = len(current)
    if not remaining:
        if not end_groups or current[-1] in end_groups:
            return [current.copy()]
        return []

    solutions = []

    if pos in fixed_positions:
        g = fixed_positions[pos]
        if g not in remaining:
            return []

        valid = True
        lookback = min(len(current), gap)
        for i in range(1, lookback + 1):
            if g in conflicts.get(current[-i], set()):
                valid = False
                break

        if valid:
            current.append(g)
            remaining.remove(g)
            res = find_schedules(remaining, current, gap, conflicts, end_groups, max_solutions, fixed_positions)
            solutions.extend(res)
            remaining.add(g)
            current.pop()
        return solutions

    for g in list(remaining):
        valid = True
        lookback = min(len(current), gap)
        for i in range(1, lookback + 1):
            if g in conflicts.get(current[-i], set()):
                valid = False
                break

        if valid:
            current.append(g)
            remaining.remove(g)
            res = find_schedules(remaining, current, gap, conflicts, end_groups, max_solutions, fixed_positions)
            solutions.extend(res)
            remaining.add(g)
            current.pop()

            if len(solutions) >= max_solutions:
                return solutions[:max_solutions]
    return solutions

def generate_excel_download(order, group_students):
    export_dict = {}
    max_students = 0
    for dance in order:
        students = sorted(list(group_students[dance]))
        export_dict[dance] = students
        if len(students) > max_students:
            max_students = len(students)

    for dance in export_dict:
        actual_len = len(export_dict[dance])
        if actual_len < max_students:
            export_dict[dance].extend([""] * (max_students - actual_len))

    export_df = pd.DataFrame(export_dict)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        export_df.to_excel(writer, index=False, sheet_name="סדר מופע")
    return buffer.getvalue()


# --- סרגל צדדי (Sidebar) להגדרות והעלאת קובץ ---
st.sidebar.header("⚙️ הגדרות והעלאת נתונים")

uploaded_file = st.sidebar.file_uploader("העלאת קובץ אקסל (XLSX)", type=["xlsx"])

# שליפת ערכים שנטענו מהקובץ (אם קיימים) בצורה בטוחה
saved_cfg = st.session_state.loaded_configs
default_gap = saved_cfg.get("gap_size", 2)
default_max_sol = saved_cfg.get("max_solutions", 100)

gap_size = st.sidebar.number_input("מרווח מינימלי נדרש (מספר ריקודים באמצע)", min_value=1, max_value=5, value=int(default_gap), key="gap_size_input")
max_solutions = st.sidebar.number_input("מספר פתרונות מקסימלי להצגה", min_value=1, max_value=500, value=int(default_max_sol), key="max_solutions_input")

st.sidebar.subheader("💾 שמירה וטעינה")

# כפתור הורדת הסטייט הנוכחי
st.sidebar.download_button(
    label="📥 שמור מצב מלא",
    data=serialize_state(),
    file_name="dance_state.json",
    mime="application/json"
)

# העלאת קובץ הסטייט שמפעיל קולבק ייעודי פעם אחת בלבד
st.sidebar.file_uploader(
    "📤 טען מצב קודם",
    type=["json"],
    key="load_state_file",
    on_change=load_state_callback
)


# --- המשך זרימת האפליקציה ---
if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        missing = validate_excel(df)
        
        if missing:
            st.error(f"❌ הקובץ אינו תקין! העמודות הבאות חסרות: {', '.join(missing)}")
        else:
            st.success("✅ הקובץ נטען ונבדק בהצלחה!")

            group_students, conflict_matrix = build_data_structures(df)
            all_groups = sorted(list(group_students.keys()))

            st.sidebar.subheader("🎭 בחירת ריקודים למופע")

            # הגדרת קבוצות ברירת מחדל על בסיס קובץ שנשמר או כל הקבוצות
            saved_selected = saved_cfg.get("selected_groups", all_groups)
            default_selected = [g for g in saved_selected if g in all_groups] if saved_selected else all_groups

            selected_groups = st.sidebar.multiselect(
                "בחר אילו קבוצות ישתתפו:",
                options=all_groups,
                default=default_selected,
                key="selected_groups_input"
            )

            active_groups = selected_groups if selected_groups else all_groups

            st.sidebar.subheader("🎯 אילוצי קבוצות מיוחדות")
            
            saved_starts = saved_cfg.get("start_groups", [])
            default_starts = [g for g in saved_starts if g in active_groups]
            
            saved_ends = saved_cfg.get("end_groups", [])
            default_ends = [g for g in saved_ends if g in active_groups]

            start_groups = st.sidebar.multiselect("קבוצות שחייבות לפתוח את המופע:", options=active_groups, default=default_starts, key="start_groups_input")
            end_groups = st.sidebar.multiselect("קבוצות שחייבות לסיים את המופע:", options=active_groups, default=default_ends, key="end_groups_input")

            st.sidebar.subheader("📌 שריון מיקומים ספציפיים")

            saved_fixed_positions = saved_cfg.get("fixed_positions", {})
            default_num_fixed = len(saved_fixed_positions)

            num_fixed = st.sidebar.number_input(
                "כמה מיקומים קבועים להגדיר?",
                min_value=0,
                max_value=len(active_groups),
                value=int(default_num_fixed),
                key="num_fixed_input"
            )

            fixed_positions = {}
            for i in range(num_fixed):
                col1, col2 = st.sidebar.columns(2)
                
                # שליפת ערך קודם עבור האינדקס הנוכחי אם קיים בקובץ השמור
                saved_pos_key = list(saved_fixed_positions.keys())[i] if i < len(saved_fixed_positions) else None
                saved_group_val = saved_fixed_positions[saved_pos_key] if saved_pos_key else active_groups[0]
                saved_pos_val = int(saved_pos_key) + 1 if saved_pos_key else i + 1

                with col1:
                    group = st.selectbox(
                        f"קבוצה {i + 1}",
                        options=active_groups,
                        index=active_groups.index(saved_group_val) if saved_group_val in active_groups else 0,
                        key=f"fixed_group_{i}"
                    )

                with col2:
                    position = st.number_input(
                        f"מיקום {i + 1}",
                        min_value=1,
                        max_value=len(active_groups),
                        value=int(saved_pos_val),
                        key=f"fixed_pos_{i}"
                    )

                fixed_positions[position - 1] = group

            st.session_state.invalid_fixed = False

            if start_groups and 0 in fixed_positions:
                fixed_first = fixed_positions[0]
                if fixed_first not in start_groups:
                    st.sidebar.error(f"❌ קונפליקט: הקבוצה '{fixed_first}' משובצת במקום הראשון, אך אינה ברשימת הפתיחה.")
                    st.session_state.invalid_fixed = True

            current_config = (tuple(start_groups), tuple(end_groups), tuple(sorted(fixed_positions.items())), gap_size)

            # טאבים לחלוקת התצוגה
            tab_report, tab_auto, tab_manual = st.tabs([
                "📊 דוח חפיפות ונתונים",
                "🤖 אופציה 1: גנרציה אוטומטית",
                "✍️ אופציה 2: שיבוץ ידני חכם"
            ])

            # --- טאב 1: דוח חפיפות (מסונן דינמית) ---
            with tab_report:
                st.subheader("ריקודים שלא יכולים להיות חופפים (חולקים רקדניות):")
                conflict_data = []
                active_set = set(active_groups)

                for group, item in conflict_matrix.items():
                    if group in active_set:
                        active_conflicts = item.intersection(active_set)
                        if active_conflicts:
                            conflict_data.append({
                                "ריקוד / קבוצה": group, 
                                "ריקודים מתנגשים": ", ".join(sorted(list(active_conflicts)))
                            })

                if conflict_data:
                    df_conflicts = pd.DataFrame(conflict_data)
                    df_conflicts = df_conflicts[df_conflicts.columns[::-1]]
                    st.dataframe(df_conflicts, use_container_width=True)
                else:
                    st.write("אין אף חפיפה בין הקבוצות שנבחרו!")

            # --- טאב 2: גנרציה אוטומטית (תיקון רוחב העמודה ומתיחה מלאה) ---
            with tab_auto:
                st.subheader("ייצור אוטומטי של סדרי עלייה אפשריים")
                st.write("האלגוריתם ינסה למצוא סידורים שעומדים בכל האילוצים שהגדרת.")

                generate_clicked = st.button("🚀 ג'נרס סדרי עלייה אפשריים")

                if generate_clicked:
                    if st.session_state.get("invalid_fixed"):
                        st.error("❌ יש קונפליקט בהגדרות — תקן לפני הרצה")
                    else:
                        solutions = []
                        starts_to_try = start_groups if start_groups else active_groups
                        if 0 in fixed_positions:
                            starts_to_try = [fixed_positions[0]]

                        with st.spinner("מחשב פתרונות אופטימליים..."):
                            for start_g in starts_to_try:
                                remaining = set(active_groups) - {start_g}
                                current = [start_g]

                                res = find_schedules(
                                    remaining, current, gap_size, conflict_matrix,
                                    set(end_groups), max_solutions, fixed_positions
                                )
                                solutions.extend(res)
                                if len(solutions) >= max_solutions:
                                    break

                        if solutions:
                            st.session_state.auto_solutions = solutions[:max_solutions]
                            st.success(f"נמצאו {len(st.session_state.auto_solutions)} סדרי עלייה אפשריים:")
                        else:
                            st.session_state.auto_solutions = []
                            st.error("❌ לא נמצא סדר חוקי שמקיים את כל התנאים...")

                if "auto_solutions" in st.session_state and st.session_state.auto_solutions:
                    for idx, sol in enumerate(st.session_state.auto_solutions):
                        # שינוי היחס ל-[1, 12] נותן לטקסט את הרוב המוחלט של רוחב המסך ומציג אותו מלא!
                        col1, col2 = st.columns([1, 12])
                        with col1:
                            excel_data = generate_excel_download(sol, group_students)
                            st.download_button(
                                label="⬇️ אקסל",
                                data=excel_data,
                                file_name=f"סדר_הופעות_אופציה_{idx + 1}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"download_auto_{idx}"
                            )
                        with col2:
                            st.markdown(
                                f"""
                                <div dir="rtl" style="
                                    width: 100%;
                                    overflow-x: auto;
                                    white-space: nowrap;
                                    border: 1px solid #ddd;
                                    padding: 10px;
                                    border-radius: 6px;
                                    background-color: #f6f8fa;
                                    font-family: system-ui, -apple-system, sans-serif;
                                    font-size: 15px;
                                    font-weight: bold;
                                ">
                                    {" ⬅️ ".join(sol)}
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

            # --- טאב 3: שיבוץ ידני חכם ---
            with tab_manual:
                st.subheader("בניית סדר הופעות אינטראקטיבי")

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("🗑️ אפס סדר הופעות", key="reset_manual"):
                        st.session_state.manual_order = []
                        st.rerun()
                with col_btn2:
                    if st.button("↩️ מחק ריקוד אחרון", key="pop_manual") and st.session_state.manual_order:
                        st.session_state.manual_order.pop()
                        st.rerun()

                if st.session_state.manual_order:
                    st.markdown("### 🎬 סדר המופע הנוכחי:")
                    st.info(" ⬅️ ".join(st.session_state.manual_order))

                    excel_data = generate_excel_download(st.session_state.manual_order, group_students)
                    st.download_button(
                        label="📥 יצא לאקסל ושמור מקומית",
                        data=excel_data,
                        file_name="סדר_הופעות_סופי.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="download_excel_btn"
                    )
                    st.markdown("---")
                else:
                    st.warning("טרם שובצו ריקודים. בחר את הריקוד הראשון למטה.")

                used_groups = set(st.session_state.manual_order)
                remaining_groups = [g for g in active_groups if g not in used_groups]
                current_pos = len(st.session_state.manual_order)

                if current_pos in fixed_positions:
                    forced_group = fixed_positions[current_pos]
                    remaining_groups = [forced_group] if forced_group in remaining_groups else []

                invalid_by_gap = set()
                if len(st.session_state.manual_order) > 0:
                    lookback = min(len(st.session_state.manual_order), gap_size)
                    for i in range(1, lookback + 1):
                        prev_dance = st.session_state.manual_order[-i]
                        invalid_by_gap.update(conflict_matrix.get(prev_dance, []))

                allowed_options = [g for g in remaining_groups if g not in invalid_by_gap]

                if len(st.session_state.manual_order) == 0 and start_groups:
                    allowed_options = [g for g in allowed_options if g in start_groups]

                bypass_constraints = st.checkbox("⚠️ אפשר בחירת קבוצה חסומה (עקיפת אילוץ המרווחים)")
                final_options_to_show = remaining_groups if bypass_constraints else allowed_options

                if remaining_groups:
                    if final_options_to_show:
                        chosen_dance = st.selectbox("בחר את הריקוד הבא להוספה:", options=final_options_to_show, key="next_dance_select")

                        if chosen_dance in invalid_by_gap:
                            st.warning(f"שים לב: הריקוד '{chosen_dance}' מפר את אילוץ המרווח שהגדרת!")

                        if st.button("➕ הוסף לסדר ההופעות"):
                            st.session_state.manual_order.append(chosen_dance)
                            st.rerun()
                    else:
                        st.error("😭 אין קבוצות זמינות העומדות באילוצי המרווח!")
                else:
                    st.success("🎉 כל הריקודים שובצו בהצלחה בסדר המופע!")

                if st.session_state.manual_order:
                    st.markdown("### 👥 פירוט הרקדניות בכל ריקוד (לפי סדר המופע שנבחר):")
                    for pos, dance in enumerate(st.session_state.manual_order, 1):
                        students_list = sorted(list(group_students[dance]))
                        with st.expander(f"ריקוד {pos}: {dance} ({len(students_list)} רקדניות)"):
                            cols = st.columns(3)
                            for s_idx, student in enumerate(students_list):
                                cols[s_idx % 3].write(f"• {student}")

    except Exception as e:
        st.error(f"שגיאה בקריאת הקובץ: {e}")
else:
    st.info("👋 אנא העלה קובץ אקסל בסרגל הצד כדי להתחיל לעבוד.")
