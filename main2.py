import streamlit as st
import pandas as pd
import io
import json

# הגדרת תצורת עמוד - תמיכה ב-RTL לעברית
st.set_page_config(page_title="מנהל סדר הופעות - אולפן למחול", layout="wide", initial_sidebar_state="expanded")

# יצירת סגנון עיצוב בסיסי לעברית וישור לימין - ה-CSS המקורי והמהיר שלך
st.markdown("""
<style>
/* כל האפליקציה */
html, body, [class*="css"]  {
    direction: rtl;
    text-align: right;
}
/* אזור ראשי */
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
/* Sidebar */
section[data-testid="stSidebar"] {
    direction: rtl;
    text-align: right;
}
/* כותרות וטקסט */
h1, h2, h3, h4, h5, h6, p, label, span {
    direction: rtl !important;
    text-align: right !important;
}
/* selectbox ו-input */
div[data-baseweb="select"] {
    direction: rtl;
    text-align: right;
}
/* שדה בחירה */
input {
    direction: rtl;
    text-align: right;
}
/* כפתורים */
button {
    direction: rtl;
    text-align: right;
}
/* dataframe */
thead tr th {
    text-align: right !important;
}
tbody tr td {
    text-align: right !important;
}
/* fix ל-code blocks */
pre, code {
    direction: rtl !important;
    text-align: right !important;
}
/* fix ל-scroll אופקי */
div[style*="overflow-x"] {
    direction: rtl;
}
</style>
""", unsafe_allow_html=True)

st.title("מופע סוף שנה - אופטימיזציית סדר עלייה 🩰")

# --- ניהול State של האפליקציה ---
if 'manual_order' not in st.session_state:
    st.session_state.manual_order = []

# --- פונקציות עזר ללוגיקה ---
def validate_excel(df):
    required_cols = ['שם תלמידה', 'שם משפחה', 'גיל', 'קבוצה']
    missing_cols = [col for col in required_cols if col not in df.columns]
    return missing_cols

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

# אלגוריתם Backtracking לאפשרות 1
def find_schedules(remaining, current, gap, conflicts, end_groups, max_solutions, fixed_positions):
    pos = len(current)
    if not remaining:
        if not end_groups or current[-1] in end_groups:
            return [current.copy()]
        return []

    solutions = []

    if pos in fixed_positions:
        g = fixed_positions[pos]
        if g not in remaining: return []
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

            # --- מנגנון טעינת קובץ מתקדם ובטוח (מונע את נעילת המסך) ---
            st.sidebar.subheader("💾 טעינת מצב עבודה קודם")
            uploaded_state = st.sidebar.file_uploader("📤 העלה קובץ JSON של מצב שמור", type=["json"])
            
            if uploaded_state is not None:
                if st.sidebar.button("🔄 לחץ כאן לטעינת הנתונים מהקובץ שהועלה"):
                    data = json.load(uploaded_state)
                    # העתקת הנתונים ל-Session State
                    st.session_state.manual_order = data.get("manual_order", [])
                    st.session_state['k_gap'] = data.get("gap_size", 2)
                    st.session_state['k_max_sol'] = data.get("max_solutions", 100)
                    st.session_state['k_sel'] = [g for g in data.get("selected_groups", all_groups) if g in all_groups]
                    st.session_state['k_starts'] = [g for g in data.get("start_groups", []) if g in all_groups]
                    st.session_state['k_ends'] = [g for g in data.get("end_groups", []) if g in all_groups]
                    st.session_state['k_num_fixed'] = data.get("num_fixed", 0)
                    st.session_state['loaded_fixed'] = {int(k): v for k, v in data.get("fixed_positions", {}).items() if v in all_groups}
                    st.sidebar.success("✅ ההגדרות נטענו! מרענן את העמוד...")
                    st.rerun()
            st.sidebar.markdown("---")

            # --- ווידג'טים בסרגל הצד (מחוברים לזיכרון) ---
            gap_size = st.sidebar.number_input("מרווח מינימלי נדרש (מספר ריקודים באמצע)", min_value=1, max_value=5, key='k_gap', value=2 if 'k_gap' not in st.session_state else None)
            max_solutions = st.sidebar.number_input("מספר פתרונות מקסימלי להצגה", min_value=1, max_value=500, key='k_max_sol', value=100 if 'k_max_sol' not in st.session_state else None)

            st.sidebar.subheader("🎭 בחירת ריקודים למופע")
            if 'k_sel' not in st.session_state: st.session_state['k_sel'] = all_groups
            selected_groups = st.sidebar.multiselect("בחר אילו קבוצות ישתתפו:", options=all_groups, key='k_sel')
            active_groups = selected_groups if selected_groups else all_groups

            st.sidebar.subheader("🎯 אילוצי קבוצות מיוחדות")
            start_groups = st.sidebar.multiselect("קבוצות שחייבות לפתוח את המופע:", options=active_groups, key='k_starts')
            end_groups = st.sidebar.multiselect("קבוצות שחייבות לסיים את המופע:", options=active_groups, key='k_ends')

            st.sidebar.subheader("📌 שריון מיקומים ספציפיים")
            num_fixed = st.sidebar.number_input("כמה מיקומים קבועים להגדיר?", min_value=0, max_value=len(active_groups), key='k_num_fixed')

            fixed_positions = {}
            loaded_fixed = st.session_state.get('loaded_fixed', {})

            for i in range(num_fixed):
                col1, col2 = st.sidebar.columns(2)
                g_key = f"fixed_g_{i}"
                p_key = f"fixed_p_{i}"

                # הזנת נתונים מטעינה (רק פעם אחת)
                if loaded_fixed and i < len(loaded_fixed):
                    pos_idx = list(loaded_fixed.keys())[i]
                    st.session_state[g_key] = loaded_fixed[pos_idx]
                    st.session_state[p_key] = pos_idx + 1

                with col1:
                    group = st.selectbox(f"קבוצה {i + 1}", options=active_groups, key=g_key)
                with col2:
                    position = st.number_input(f"מיקום {i + 1}", min_value=1, max_value=len(active_groups), key=p_key)

                fixed_positions[position - 1] = group

            if 'loaded_fixed' in st.session_state:
                del st.session_state['loaded_fixed'] # מנקים אחרי הטעינה

            st.session_state.invalid_fixed = False
            if start_groups and 0 in fixed_positions:
                fixed_first = fixed_positions[0]
                if fixed_first not in start_groups:
                    st.sidebar.error(f"❌ קונפליקט: '{fixed_first}' במקום ה-1, אבל אינה ברשימת הפתיחה")
                    st.session_state.invalid_fixed = True

            for pos1, group1 in fixed_positions.items():
                for pos2, group2 in fixed_positions.items():
                    if pos1 >= pos2: continue
                    if abs(pos1 - pos2) - 1 < gap_size and group2 in conflict_matrix.get(group1, set()):
                        st.sidebar.error(f"❌ קונפליקט בין מיקומים שוריינו: '{group1}' קרובה ל '{group2}'")
                        st.session_state.invalid_fixed = True

            # --- מנגנון השמירה החדש ---
            st.sidebar.markdown("---")
            st.sidebar.subheader("💾 שמירת עבודה נוכחית")
            current_state_dict = {
                "manual_order": st.session_state.manual_order,
                "gap_size": gap_size,
                "max_solutions": max_solutions,
                "selected_groups": selected_groups,
                "start_groups": start_groups,
                "end_groups": end_groups,
                "num_fixed": num_fixed,
                "fixed_positions": fixed_positions
            }
            save_data = json.dumps(current_state_dict, ensure_ascii=False).encode("utf-8")
            st.sidebar.download_button(
                label="📥 לחץ לשמירת קובץ הגיבוי",
                data=save_data,
                file_name="dance_state.json",
                mime="application/json"
            )

            # --- טאבים לחלוקת התצוגה ---
            tab_report, tab_auto, tab_manual = st.tabs([
                "📊 דוח צימודים אסורים",
                "🤖 אופציה 1: שיבוץ אוטומטי חכם",
                "✍️ אופציה 2: שיבוץ ידני חכם"
            ])

            # --- טאב 1: דוח חפיפות מתעדכן ---
            with tab_report:
                st.subheader("ריקודים שלא יכולים להיות חופפים (חולקים רקדניות):")
                conflict_data = []
                active_set = set(active_groups) # הפילטר שביקשת
                
                for group, item in conflict_matrix.items():
                    if group in active_set:
                        # מציג קונפליקטים רק מול קבוצות שמשתתפות במופע
                        active_conflicts = item.intersection(active_set)
                        if active_conflicts:
                            conflict_data.append({"ריקוד / קבוצה": group, "ריקודים מתנגשים": ", ".join(sorted(list(active_conflicts)))})

                if conflict_data:
                    df_conflicts = pd.DataFrame(conflict_data)
                    df_conflicts = df_conflicts[df_conflicts.columns[::-1]]
                    st.dataframe(df_conflicts, use_container_width=True)
                else:
                    st.write("אין אף חפיפה בין הקבוצות שנבחרו במופע! 🎉")

            # --- טאב 2: גנרציה אוטומטית ---
            with tab_auto:
                st.subheader("ייצור אוטומטי של סדרי עלייה אפשריים")
                st.write("האלגוריתם ינסה למצוא סידורים שעומדים בכל האילוצים שהגדרת.")

                generate_clicked = st.button("🚀 סדר אוטומטית (יחושב רק בלחיצה)")

                if generate_clicked:
                    if st.session_state.get("invalid_fixed"):
                        st.error("❌ יש קונפליקט בהגדרות — תקן לפני הרצה")
                    else:
                        solutions = []
                        starts_to_try = start_groups if start_groups else active_groups
                        if 0 in fixed_positions: starts_to_try = [fixed_positions[0]]

                        with st.spinner("מחשב פתרונות אופטימליים..."):
                            for start_g in starts_to_try:
                                remaining = set(active_groups) - {start_g}
                                current = [start_g]
                                res = find_schedules(remaining, current, gap_size, conflict_matrix, set(end_groups), max_solutions, fixed_positions)
                                solutions.extend(res)
                                if len(solutions) >= max_solutions: break

                        if solutions:
                            st.session_state.auto_solutions = solutions[:max_solutions]
                            st.success(f"נמצאו {len(st.session_state.auto_solutions)} סדרי עלייה אפשריים:")
                        else:
                            st.session_state.auto_solutions = []
                            st.error("❌ לא נמצא סדר חוקי שמקיים את כל התנאים...")

                if st.session_state.get("auto_solutions"):
                    for idx, sol in enumerate(st.session_state.auto_solutions):
                        st.markdown(f"**אופציה {idx + 1}:**")
                        # היחס השתנה! 8 חלקים לטקסט, 1 חלק לכפתור (פותר את הבעיה שבתמונה)
                        col_txt, col_btn = st.columns([8, 1])
                        with col_btn:
                            excel_data = generate_excel_download(sol, group_students)
                            st.download_button(label="⬇️ אקסל", data=excel_data, file_name=f"סדר_הופעות_{idx + 1}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dl_{idx}")
                        with col_txt:
                            st.markdown(f"""<div dir="rtl" style="overflow-x: auto; white-space: nowrap; border: 1px solid #ddd; padding: 8px; border-radius: 6px; background-color: #f6f8fa; font-family: monospace;">{" ⬅️ ".join(sol)}</div>""", unsafe_allow_html=True)

            # --- טאב 3: שיבוץ ידני (מקורי לגמרי, אין שינוי) ---
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
                    st.download_button(label="📥 יצא לאקסל ושמור מקומית", data=excel_data, file_name="סדר_הופעות_סופי.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_final")
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
                    st.markdown("### 👥 פירוט הרקדניות בכל ריקוד:")
                    for pos, dance in enumerate(st.session_state.manual_order, 1):
                        students_list = sorted(list(group_students[dance]))
                        with st.expander(f"ריקוד {pos}: {dance} ({len(students_list)} רקדניות)"):
                            cols = st.columns(3)
                            for s_idx, student in enumerate(students_list):
                                cols[s_idx % 3].write(f"• {student}")

    except Exception as e:
        st.error(f"שגיאה: {e}")
else:
    st.info("👋 אנא העלה קובץ אקסל בסרגל הצד כדי להתחיל לעבוד.")
