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

# --- אתחול דינמי של ה-State (חובה עבור חיבור מפתחות לווידג'טים) ---
if 'manual_order' not in st.session_state:
    st.session_state.manual_order = []
if 'gap_size' not in st.session_state:
    st.session_state.gap_size = 2
if 'max_solutions' not in st.session_state:
    st.session_state.max_solutions = 100
if 'num_fixed' not in st.session_state:
    st.session_state.num_fixed = 0

# --- פונקציות עזר ללוגיקה ושמירת מצב ---
def validate_excel(df):
    required_cols = ['שם תלמידה', 'שם משפחה', 'גיל', 'קבוצה']
    missing_cols = [col for col in required_cols if col not in df.columns]
    return missing_cols

def serialize_state():
    """אוסף את כל הנתונים הנוכחיים מה-Session State ומכין קובץ JSON להורדה"""
    current_fixed = {}
    for i in range(st.session_state.get("num_fixed", 0)):
        g = st.session_state.get(f"fixed_group_{i}")
        p = st.session_state.get(f"fixed_pos_{i}")
        if g and p:
            current_fixed[int(p) - 1] = g

    data = {
        "manual_order": st.session_state.get("manual_order", []),
        "gap_size": st.session_state.get("gap_size", 2),
        "max_solutions": st.session_state.get("max_solutions", 100),
        "selected_groups": st.session_state.get("selected_groups", []),
        "start_groups": st.session_state.get("start_groups", []),
        "end_groups": st.session_state.get("end_groups", []),
        "fixed_positions": current_fixed
    }
    return json.dumps(data, ensure_ascii=False).encode("utf-8")

def load_state_callback():
    """פונקציית קולבק שרצה אך ורק ברגע העלאת קובץ הסטייט ומונעת נעילה"""
    if st.session_state.load_state_file is not None:
        try:
            data = json.load(st.session_state.load_state_file)
            
            # טעינת משתנים פשוטים לרמת האפליקציה
            st.session_state.manual_order = data.get("manual_order", [])
            st.session_state.gap_size = data.get("gap_size", 2)
            st.session_state.max_solutions = data.get("max_solutions", 100)
            st.session_state.selected_groups = data.get("selected_groups", [])
            st.session_state.start_groups = data.get("start_groups", [])
            st.session_state.end_groups = data.get("end_groups", [])
            
            # טעינת המיקומים המשוריינים הדינמיים
            saved_fixed = data.get("fixed_positions", {})
            st.session_state.num_fixed = len(saved_fixed)
            
            for idx, (pos_str, group) in enumerate(saved_fixed.items()):
                st.session_state[f"fixed_group_{idx}"] = group
                st.session_state[f"fixed_pos_{idx}"] = int(pos_str) + 1  # המרה חזרה מאינדקס 0 למיקום אנושי (1 ומעלה)
                
            st.toast("✅ מצב קודם נטען בהצלחה!", icon="💾")
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

# הגדרות מחוברות ל-Session State
gap_size = st.sidebar.number_input("מרווח מינימלי נדרש (מספר ריקודים באמצע)", min_value=1, max_value=5, key="gap_size")
max_solutions = st.sidebar.number_input("מספר פתרונות מקסימלי להצגה", min_value=1, max_value=500, key="max_solutions")

st.sidebar.subheader("💾 שמירה וטעינה")

# שמירת המצב הנוכחי המלא לקובץ JSON
st.sidebar.download_button(
    label="📥 שמור מצב מלא",
    data=serialize_state(),
    file_name="dance_state.json",
    mime="application/json"
)

# טעינת המצב באמצעות מנגנון קולבק (Callback) שלא נועל את האפליקציה
uploaded_state = st.sidebar.file_uploader(
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
            st.info("אנא ודא שהעמודות באקסל הן בדיוק: 'שם תלמידה', 'שם משפחה', 'גיל', 'קבוצה'")
        else:
            st.success("✅ הקובץ נטען ונבדק בהצלחה!")

            group_students, conflict_matrix = build_data_structures(df)
            all_groups = sorted(list(group_students.keys()))

            st.sidebar.subheader("🎭 בחירת ריקודים למופע")

            # הגנה וניקוי במקרה ונטען קובץ הגדרות לא תואם
            if "selected_groups" in st.session_state and st.session_state.selected_groups:
                st.session_state.selected_groups = [g for g in st.session_state.selected_groups if g in all_groups]
            else:
                st.session_state.selected_groups = all_groups

            selected_groups = st.sidebar.multiselect(
                "בחר אילו קבוצות ישתתפו:",
                options=all_groups,
                key="selected_groups"
            )

            active_groups = selected_groups if selected_groups else all_groups

            st.sidebar.subheader("🎯 אילוצי קבוצות מיוחדות")
            
            if "start_groups" in st.session_state and st.session_state.start_groups:
                st.session_state.start_groups = [g for g in st.session_state.start_groups if g in active_groups]
            if "end_groups" in st.session_state and st.session_state.end_groups:
                st.session_state.end_groups = [g for g in st.session_state.end_groups if g in active_groups]

            start_groups = st.sidebar.multiselect("קבוצות שחייבות לפתוח את המופע:", options=active_groups, key="start_groups")
            end_groups = st.sidebar.multiselect("קבוצות שחייבות לסיים את המופע:", options=active_groups, key="end_groups")

            st.sidebar.subheader("📌 שריון מיקומים ספציפיים")

            num_fixed = st.sidebar.number_input(
                "כמה מיקומים קבועים להגדיר?",
                min_value=0,
                max_value=len(active_groups),
                key="num_fixed"
            )

            fixed_positions = {}
            for i in range(num_fixed):
                col1, col2 = st.sidebar.columns(2)

                with col1:
                    group = st.selectbox(
                        f"קבוצה {i + 1}",
                        options=active_groups,
                        key=f"fixed_group_{i}"
                    )

                with col2:
                    position = st.number_input(
                        f"מיקום {i + 1}",
                        min_value=1,
                        max_value=len(active_groups),
                        key=f"fixed_pos_{i}"
                    )

                fixed_positions[position - 1] = group  # 0-based index

            st.session_state.invalid_fixed = False

            if start_groups and 0 in fixed_positions:
                fixed_first = fixed_positions[0]
                if fixed_first not in start_groups:
                    st.sidebar.error(
                        f"❌ קונפליקט: הקבוצה '{fixed_first}' משובצת במקום הראשון, "
                        f"אבל רק {start_groups} יכולות לפתוח את המופע"
                    )
                    st.session_state.invalid_fixed = True

            for pos1, group1 in fixed_positions.items():
                for pos2, group2 in fixed_positions.items():
                    if pos1 >= pos2:
                        continue

                    distance = abs(pos1 - pos2) - 1
                    if distance < gap_size:
                        if group2 in conflict_matrix.get(group1, set()):
                            st.sidebar.error(
                                f"❌ קונפליקט: '{group1}' (מקום {pos1 + 1}) "
                                f"לא יכולה להיות קרובה ל '{group2}' (מקום {pos2 + 1}) "
                                f"בגלל חפיפת רקדניות"
                            )
                            st.session_state.invalid_fixed = True

            if len(set(fixed_positions.values())) != len(fixed_positions):
                st.sidebar.error("⚠️ בחרת אותה קבוצה פעמיים במיקומים שונים")

            current_config = (
                tuple(start_groups),
                tuple(end_groups),
                tuple(sorted(fixed_positions.items())),
                gap_size
            )

            # טאבים לחלוקת התצוגה
            tab_report, tab_auto, tab_manual = st.tabs([
                "📊 דוח חפיפות ונתונים",
                "🤖 אופציה 1: גנרציה אוטומטית",
                "✍️ אופציה 2: שיבוץ ידני חכם"
            ])

            # --- טאב 1: דוח חפיפות (מציג ומסנן רק לפי הקבוצות שנבחרו במופע) ---
            with tab_report:
                st.subheader("ריקודים שלא יכולים להיות חופפים (חולקים רקדניות):")
                conflict_data = []
                active_set = set(active_groups)  # הגדרת סט של הקבוצות הפעילות לטובת סינון מהיר

                for group, item in conflict_matrix.items():
                    # מציג קבוצה רק אם היא נבחרה להשתתף במופע
                    if group in active_set:
                        # מסנן את רשימת הקונפליקטים שלה, כך שיופיעו רק קבוצות שגם משתתפות במופע
                        active_conflicts = item.intersection(active_set)
                        if active_conflicts:
                            conflict_data.append({
                                "ריקוד / קבוצה": group, 
                                "ריקודים מתנגשים": ", ".join(sorted(list(active_conflicts)))
                            })

                if conflict_data:
                    df_conflicts = pd.DataFrame(conflict_data)
                    df_conflicts = df_conflicts[df_conflicts.columns[::-1]]  # היפוך סדר העמודות ל-RTL
                    st.dataframe(df_conflicts, use_container_width=True)
                else:
                    st.write("אין אף חפיפה בין הקבוצות שנבחרו! (כל תלמידה רוקדת רק בריקוד אחד מתוך הרשימה שנבחרה)")

            # --- טאב 2: גנרציה אוטומטית ---
            with tab_auto:
                st.subheader("ייצור אוטומטי של סדרי עלייה אפשריים")
                st.write("האלגוריתם ינסה למצוא סידורים שעומדים בכל האילוצים שהגדרת (מרווחים, פתיחה וסיום).")

                auto_run = False
                if "last_config" not in st.session_state:
                    st.session_state.last_config = current_config

                if st.session_state.last_config != current_config:
                    auto_run = True
                    st.session_state.last_config = current_config

                generate_clicked = st.button("🚀 ג'נרס סדרי עלייה אפשריים")

                if generate_clicked or auto_run:
                    if st.session_state.get("invalid_fixed"):
                        st.error("❌ יש קונפליקט בהגדרות — תקן לפני הרצה")
                        st.stop()

                    solutions = []
                    starts_to_try = start_groups if start_groups else active_groups
                    if 0 in fixed_positions:
                        starts_to_try = [fixed_positions[0]]

                    with st.spinner("מחשב פתרונות אופטימליים..."):
                        for start_g in starts_to_try:
                            remaining = set(active_groups) - {start_g}
                            current = [start_g]

                            res = find_schedules(
                                remaining,
                                current,
                                gap_size,
                                conflict_matrix,
                                set(end_groups),
                                max_solutions,
                                fixed_positions
                            )
                            solutions.extend(res)
                            if len(solutions) >= max_solutions:
                                break

                    if solutions:
                        st.session_state.auto_solutions = solutions[:max_solutions]
                        st.success(f"נמצאו {len(st.session_state.auto_solutions)} סדרי עלייה אפשריים:")

                        for idx, sol in enumerate(st.session_state.auto_solutions):
                            col1, col2 = st.columns([1, 4])
                            with col1:
                                st.markdown(f"**אופציה {idx + 1}:**")
                                st.markdown(
                                    f"""
                                    <div dir="rtl" style="
                                        overflow-x: auto;
                                        white-space: nowrap;
                                        border: 1px solid #ddd;
                                        padding: 8px;
                                        border-radius: 6px;
                                        background-color: #f6f8fa;
                                        font-family: monospace;
                                    ">
                                        {" ⬅️ ".join(sol)}
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                            with col2:
                                excel_data = generate_excel_download(sol, group_students)
                                st.download_button(
                                    label="⬇️ אקסל",
                                    data=excel_data,
                                    file_name=f"סדר_הופעות_אופציה_{idx + 1}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    key=f"download_auto_{idx}"
                                )
                    else:
                        st.session_state.auto_solutions = []
                        st.error("❌ לא נמצא סדר חוקי שמקיים את כל התנאים...")

                if st.session_state.get("auto_solutions") and len(st.session_state.auto_solutions) > 0:
                    st.markdown("### 🎯 בחר אופציה לייצוא")
                    selected_index = st.selectbox(
                        "בחר אופציה:",
                        options=list(range(len(st.session_state.auto_solutions))),
                        format_func=lambda i: f"אופציה {i + 1}"
                    )
                    selected_solution = st.session_state.auto_solutions[selected_index]
                    st.info(" ⬅️ ".join(selected_solution))

                    excel_data_auto = generate_excel_download(selected_solution, group_students)
                    st.download_button(
                        label="📥 יצא אקסל לפי האופציה שנבחרה",
                        data=excel_data_auto,
                        file_name=f"סדר_הופעות_אופציה_{selected_index + 1}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="download_auto_excel"
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
                            st.warning(f"שים לב: הריקוד '{chosen_dance}' מפר את אילוץ המרווח שהגדרת! (רקדניות מסוימות לא יקבלו מספיק מנוחה).")

                        if st.button("➕ הוסף לסדר ההופעות"):
                            st.session_state.manual_order.append(chosen_dance)
                            st.rerun()
                    else:
                        st.error("😭 אין קבוצות זמינות העומדות באילוצי המרווח! סמן את התיבה למעלה לעקיפת האילוצים והצגת קבוצות אסורות.")
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
