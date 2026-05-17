import streamlit as st
import pandas as pd
import io

# הגדרת תצורת עמוד - תמיכה ב-RTL לעברית
st.set_page_config(page_title="מנהל סדר הופעות - אולפן למחול", layout="wide", initial_sidebar_state="expanded")

# יצירת סגנון עיצוב בסיסי לעברית וישור לימין
st.markdown("""
    <style>
    .reportview-container .main .block-container { direction: RTL; text-align: right; }
    div[data-testid="stSidebarUserContent"] { direction: RTL; text-align: right; }
    .stHeading, .stText, .stMarkdown, p, h1, h2, h3, label { text-align: right; direction: RTL; }
    </style>
    """, unsafe_allow_html=True)

st.title("מופע סוף שנה - אופטימיזציית סדר עלייה 🩰")

# --- ניהול State של האפליקציה ---
if 'manual_order' not in st.session_state:
    st.session_state.manual_order = []

# --- סרגל צדדי (Sidebar) להגדרות והעלאת קובץ ---
st.sidebar.header("⚙️ הגדרות והעלאת נתונים")

uploaded_file = st.sidebar.file_uploader("העלאת קובץ אקסל (XLSX)", type=["xlsx"])

# משתני הגדרה דינמיים
gap_size = st.sidebar.number_input("מרווח מינימלי נדרש (מספר ריקודים באמצע)", min_value=1, max_value=5, value=2)


# --- פונקציות עזר ללוגיקה ---
def validate_excel(df):
    required_cols = ['שם תלמידה', 'שם משפחה', 'גיל', 'קבוצה']
    missing_cols = [col for col in required_cols if col not in df.columns]
    return missing_cols


def build_data_structures(df):
    # מיפוי קבוצה -> סט רקדניות (שם מלא)
    group_students = {}
    for _, row in df.iterrows():
        student = f"{row['שם תלמידה']} {row['שם משפחה']}".strip()
        group = str(row['קבוצה']).strip()
        if group not in group_students:
            group_students[group] = set()
        group_students[group].add(student)

    # בניית מטריצת חפיפה/קונפליקטים
    conflict_matrix = {}
    groups = list(group_students.keys())
    for g1 in groups:
        conflict_matrix[g1] = set()
        for g2 in groups:
            if g1 != g2:
                # אם יש רקדנית משותפת - יש קונפליקט
                if group_students[g1].intersection(group_students[g2]):
                    conflict_matrix[g1].add(g2)

    return group_students, conflict_matrix


# אלגוריתם Backtracking לאפשרות 1 (חיפוש פתרונות אוטומטיים)
def find_schedules(remaining, current, gap, conflicts, end_groups, max_solutions=100):
    if not remaining:
        if not end_groups or current[-1] in end_groups:
            return [current.copy()]
        return []

    solutions = []
    for g in list(remaining):
        # בדיקת אילוץ מרווח
        valid = True
        lookback = min(len(current), gap)
        for i in range(1, lookback + 1):
            if g in conflicts.get(current[-i], set()):
                valid = False
                break

        # בדיקת אילוץ קבוצת סיום (אם זה האיבר האחרון שנשאר)
        if valid and len(remaining) == 1 and end_groups and g not in end_groups:
            valid = False

        if valid:
            current.append(g)
            remaining.remove(g)

            res = find_schedules(remaining, current, gap, conflicts, end_groups, max_solutions)
            solutions.extend(res)

            remaining.add(g)
            current.pop()

            if len(solutions) >= max_solutions:
                return solutions[:max_solutions]
    return solutions


# פונקציה לייצוא סדר ההופעות לקובץ אקסל במבנה המבוקש
def generate_excel_download(order, group_students):
    # יצירת מילון שבו המפתח הוא שם הריקוד והערכים הם רשימת התלמידות
    export_dict = {}

    # נמצא את מספר התלמידות המקסימלי בריקוד כלשהו כדי לאזן את אורכי הרשימות
    max_students = 0
    for dance in order:
        students = sorted(list(group_students[dance]))
        export_dict[dance] = students
        if len(students) > max_students:
            max_students = len(students)

    # השלמת רשימות קצרות עם ערכים ריקים כדי שפנדאס יוכל לייצר DataFrame בצורה תקינה
    for dance in export_dict:
        actual_len = len(export_dict[dance])
        if actual_len < max_students:
            export_dict[dance].extend([""] * (max_students - actual_len))

    # יצירת ה-DataFrame (שמות הריקודים יהיו כותרות העמודות - שורה ראשונה באקסל)
    export_df = pd.DataFrame(export_dict)

    # כתיבה לזיכרון כקובץ אקסל
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        export_df.to_excel(writer, index=False, sheet_name="סדר מופע")

    return buffer.getvalue()


# --- המשך זרימת האפליקציה ---
if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)

        # 1. אימות תקינות הקובץ
        missing = validate_excel(df)
        if missing:
            st.error(f"❌ הקובץ אינו תקין! העמודות הבאות חסרות: {', '.join(missing)}")
            st.info("אנא ודא שהעמודות באקסל הן בדיוק: 'שם תלמידה', 'שם משפחה', 'גיל', 'קבוצה'")
        else:
            st.success("✅ הקובץ נטען ונבדק בהצלחה!")

            # בניית מבני הנתונים
            group_students, conflict_matrix = build_data_structures(df)
            all_groups = sorted(list(group_students.keys()))

            # הגדרות מתקדמות בסרגל הצד (מבוססות על הקבוצות שנמצאו באקסל)
            st.sidebar.subheader("🎯 אילוצי קבוצות מיוחדות")
            start_groups = st.sidebar.multiselect("קבוצות שחייבות לפתוח את המופע:", options=all_groups)
            end_groups = st.sidebar.multiselect("קבוצות שחייבות לסיים את המופע:", options=all_groups)

            # טאבים לחלוקת התצוגה
            tab_report, tab_auto, tab_manual = st.tabs([
                "📊 דוח חפיפות ונתונים",
                "🤖 אופציה 1: גנרציה אוטומטית",
                "✍️ אופציה 2: שיבוץ ידני חכם"
            ])

            # --- טאב 1: דוח חפיפות ---
            with tab_report:
                st.subheader("ריקודים שלא יכולים להיות חופפים (חולקים רקדניות):")
                conflict_data = []
                for group, item in conflict_matrix.items():
                    if item:
                        conflict_data.append({"ריקוד / קבוצה": group, "ריקודים מתנגשים": ", ".join(sorted(list(item)))})

                if conflict_data:
                    st.dataframe(pd.DataFrame(conflict_data), use_container_width=True)
                else:
                    st.write("אין אף חפיפה בין הקבוצות! (כל תלמידה רוקדת רק בריקוד אחד)")

            # --- טאב 2: גנרציה אוטומטית ---
            with tab_auto:
                st.subheader("ייצור אוטומטי של סדרי עלייה אפשריים")
                st.write("האלגוריתם ינסה למצוא סידורים שעומדים בכל האילוצים שהגדרת (מרווחים, פתיחה וסיום).")

                if st.button("🚀 ג'נרס סדרי עלייה אפשריים"):
                    solutions = []
                    starts_to_try = start_groups if start_groups else all_groups

                    with st.spinner("מחשב פתרונות אופטימליים..."):
                        for start_g in starts_to_try:
                            remaining = set(all_groups) - {start_g}
                            current = [start_g]
                            res = find_schedules(remaining, current, gap_size, conflict_matrix, set(end_groups))
                            solutions.extend(res)
                            if len(solutions) >= 100:
                                break

                    if solutions:
                        st.success(f"נמצאו {len(solutions[:100])} סדרי עלייה אפשריים העונים על האילוצים:")
                        for idx, sol in enumerate(solutions[:100]):
                            st.markdown(f"**אופציה {idx + 1}:**")
                            st.code(" ⬅️ ".join(sol))
                    else:
                        st.error(
                            "❌ לא נמצא סדר עלייה חוקי שעונה על כל האילוצים במלואם. מומלץ להשתמש בשיבוץ הידני החכם כדי לעקוף אילוצים במידת הצורך.")

            # --- טאב 3: שיבוץ ידני חכם ---
            with tab_manual:
                st.subheader("בניית סדר הופעות אינטראקטיבי")

                # כפתורי ניהול המערך הידני
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("🗑️ אפס סדר הופעות", key="reset_manual"):
                        st.session_state.manual_order = []
                        st.rerun()
                with col_btn2:
                    if st.button("↩️ מחק ריקוד אחרון", key="pop_manual") and st.session_state.manual_order:
                        st.session_state.manual_order.pop()
                        st.rerun()

                # הצגת המצב הנוכחי של המופע
                if st.session_state.manual_order:
                    st.markdown("### 🎬 סדר המופע הנוכחי:")
                    st.info(" ⬅️ ".join(st.session_state.manual_order))

                    # ------------------ כפתור ייצוא לאקסל החדש ------------------
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

                # חישוב אילוצים בזמן אמת לריקוד הבא
                used_groups = set(st.session_state.manual_order)
                remaining_groups = [g for g in all_groups if g not in used_groups]

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
                        chosen_dance = st.selectbox("בחר את הריקוד הבא להוספה:", options=final_options_to_show,
                                                    key="next_dance_select")

                        if chosen_dance in invalid_by_gap:
                            st.warning(
                                f"שים לב: הריקוד '{chosen_dance}' מפר את אילוץ המרווח שהגדרת! (רקדניות מסוימות לא יקבלו מספיק מנוחה).")

                        if st.button("➕ הוסף לסדר ההופעות"):
                            st.session_state.manual_order.append(chosen_dance)
                            st.rerun()
                    else:
                        st.error(
                            "😭 אין קבוצות זמינות העומדות באילוצי המרווח! סמן את התיבה למעלה לעקיפת האילוצים והצגת קבוצות אסורות.")
                else:
                    st.success("🎉 כל הריקודים שובצו בהצלחה בסדר המופע!")

                # הצגת רשימת התלמידות מתחת לכל ריקוד ששובץ
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
