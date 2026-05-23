import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="Uma Club Tracker",
    layout="wide"
)

st.title("Uma Club Tracker")
st.caption("Upload uma.moe / Chronogenesis-style club stats CSV to track club activity.")


# -----------------------------
# Helper functions
# -----------------------------

def parse_num(x):
    """
    Convert values like:
    - 1.2M
    - 500K
    - 1,234,567
    - +123,456
    into numeric values.
    """
    if pd.isna(x):
        return 0.0

    s = str(x).strip().replace(",", "").replace("+", "")

    if s == "" or s.lower() in ["nan", "none", "-"]:
        return 0.0

    multiplier = 1.0

    if s[-1:].upper() == "M":
        multiplier = 1_000_000
        s = s[:-1]
    elif s[-1:].upper() == "K":
        multiplier = 1_000
        s = s[:-1]

    try:
        return float(s) * multiplier
    except ValueError:
        return 0.0


def find_col(df, keywords):
    """
    Find first column containing all keywords.
    Example:
    find_col(df, ["daily", "gain"])
    """
    for col in df.columns:
        col_lower = str(col).lower()
        if all(k.lower() in col_lower for k in keywords):
            return col
    return None


def format_millions(x):
    return f"{x / 1_000_000:.2f}M"


def classify_member(row):
    """
    Simple internal watchlist classifier.
    This should be treated as a suggestion, not an auto-kick rule.
    """
    avg_7d = row.get("avg_7d", 0)
    monthly_gain = row.get("monthly_gain", 0)

    if avg_7d <= 0 and monthly_gain < 1_000_000:
        return "Replace / inactive risk"

    if avg_7d < 100_000:
        return "High watch"

    if avg_7d < 200_000:
        return "Watch"

    if monthly_gain < 5_000_000:
        return "Low monthly"

    if monthly_gain < 10_000_000:
        return "Below 10M benchmark"

    return "OK"


# -----------------------------
# Upload
# -----------------------------

uploaded_file = st.file_uploader("Upload club stats CSV", type=["csv"])

if uploaded_file is None:
    st.info("Upload a club CSV to start.")
    st.stop()

df = pd.read_csv(uploaded_file)

st.subheader("Raw columns")
st.write(list(df.columns))


# -----------------------------
# Column mapping
# -----------------------------

st.subheader("Column mapping")

default_name_col = find_col(df, ["name"]) or df.columns[0]
default_daily_col = find_col(df, ["daily", "gain"]) or find_col(df, ["today"])
default_avg_col = (
    find_col(df, ["7", "avg"])
    or find_col(df, ["7", "average"])
    or find_col(df, ["avg"])
    or find_col(df, ["average"])
)
default_monthly_col = (
    find_col(df, ["monthly", "gain"])
    or find_col(df, ["month", "gain"])
    or find_col(df, ["monthly"])
)
default_status_col = find_col(df, ["status"]) or find_col(df, ["active"])

columns = list(df.columns)

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    name_col = st.selectbox(
        "Member name",
        columns,
        index=columns.index(default_name_col) if default_name_col in columns else 0
    )

with col2:
    daily_col = st.selectbox(
        "Daily gain",
        [None] + columns,
        index=([None] + columns).index(default_daily_col)
        if default_daily_col in columns
        else 0
    )

with col3:
    avg_col = st.selectbox(
        "7-day avg",
        [None] + columns,
        index=([None] + columns).index(default_avg_col)
        if default_avg_col in columns
        else 0
    )

with col4:
    monthly_col = st.selectbox(
        "Monthly gain",
        [None] + columns,
        index=([None] + columns).index(default_monthly_col)
        if default_monthly_col in columns
        else 0
    )

with col5:
    status_col = st.selectbox(
        "Status / active column",
        [None] + columns,
        index=([None] + columns).index(default_status_col)
        if default_status_col in columns
        else 0
    )


# -----------------------------
# Prepare data
# -----------------------------

data = df.copy()


def make_num_col(source_col):
    """
    Create numeric version of selected source column.
    Returns the numeric column name, or None if no source column is selected.
    """
    if source_col is None:
        return None

    num_col = f"{source_col}_num"
    data[num_col] = data[source_col].apply(parse_num)
    return num_col


daily_num_col = make_num_col(daily_col)
avg_num_col = make_num_col(avg_col)
monthly_num_col = make_num_col(monthly_col)


# -----------------------------
# Active roster filtering
# -----------------------------

st.subheader("Roster filter")

if status_col is not None:
    active_values = data[status_col].dropna().astype(str).unique().tolist()

    default_active_statuses = [
        x for x in active_values
        if x.strip().lower() in [
            "active",
            "current",
            "member",
            "true",
            "yes",
            "1"
        ]
    ]

    if not default_active_statuses:
        default_active_statuses = active_values

    active_statuses = st.multiselect(
        "Select statuses to include as active/current roster",
        options=active_values,
        default=default_active_statuses
    )

    active_data = data[data[status_col].astype(str).isin(active_statuses)].copy()

else:
    st.warning("No status column selected. Using all rows as active members.")
    active_data = data.copy()

st.write(f"Rows in uploaded file: **{len(data)}**")
st.write(f"Rows treated as active/current roster: **{len(active_data)}**")

if len(active_data) == 0:
    st.error("No active rows selected. Check your status filter.")
    st.stop()


# -----------------------------
# Summary metrics
# -----------------------------

st.divider()
st.subheader("Club Summary")

daily_total = active_data[daily_num_col].sum() if daily_num_col else 0
avg_total = active_data[avg_num_col].sum() if avg_num_col else 0
monthly_total = active_data[monthly_num_col].sum() if monthly_num_col else 0

c0, c1, c2, c3 = st.columns(4)

c0.metric("Active members", f"{len(active_data)}/30")
c1.metric("Daily gain", format_millions(daily_total))
c2.metric("7-day pace", f"{format_millions(avg_total)}/day")
c3.metric("Monthly gain", format_millions(monthly_total))


# Extra distribution metrics
if avg_num_col:
    below_100k = (active_data[avg_num_col] < 100_000).sum()
    below_200k = (active_data[avg_num_col] < 200_000).sum()
    below_333k = (active_data[avg_num_col] < 333_333).sum()
    below_500k = (active_data[avg_num_col] < 500_000).sum()

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Below 100k/day avg", int(below_100k))
    d2.metric("Below 200k/day avg", int(below_200k))
    d3.metric("Below 333k/day avg", int(below_333k))
    d4.metric("Below 500k/day avg", int(below_500k))

if daily_num_col:
    zero_today = (active_data[daily_num_col] == 0).sum()
    st.metric("Members with 0 gain today", int(zero_today))


# -----------------------------
# Buffer / pace simulator
# -----------------------------

st.divider()
st.subheader("Buffer / Pace Simulator")

b1, b2, b3 = st.columns(3)

with b1:
    breakpoint_m = st.number_input(
        "Estimated daily hold/climb breakpoint, M fans",
        min_value=0.0,
        value=14.0,
        step=0.1
    )

with b2:
    days_left = st.number_input(
        "Days left in cycle",
        min_value=1,
        value=12,
        step=1
    )

with b3:
    current_buffer_m = st.number_input(
        "Current buffer to B cutoff, M fans",
        min_value=0.0,
        value=26.7,
        step=0.1
    )

breakpoint = breakpoint_m * 1_000_000
current_buffer = current_buffer_m * 1_000_000

daily_surplus = daily_total - breakpoint
projected_buffer = current_buffer + daily_surplus * days_left

s1, s2, s3 = st.columns(3)

s1.metric("Today vs breakpoint", format_millions(daily_surplus))
s2.metric("Projected buffer if repeated", format_millions(projected_buffer))
s3.metric("Breakpoint", f"{breakpoint_m:.1f}M/day")


# -----------------------------
# Carry analysis
# -----------------------------

st.divider()
st.subheader("Carry Analysis")

if avg_num_col:
    members = active_data[name_col].dropna().unique().tolist()

    default_carries = [
        x for x in members
        if x in ["Naruhodo", "Soudesune"]
    ]

    selected_carries = st.multiselect(
        "Select carry accounts",
        options=members,
        default=default_carries
    )

    carry_avg = active_data.loc[
        active_data[name_col].isin(selected_carries),
        avg_num_col
    ].sum()

    carry_daily = (
        active_data.loc[
            active_data[name_col].isin(selected_carries),
            daily_num_col
        ].sum()
        if daily_num_col else 0
    )

    carry_share_avg = carry_avg / avg_total if avg_total else 0
    carry_share_daily = carry_daily / daily_total if daily_total else 0

    ca1, ca2, ca3, ca4 = st.columns(4)
    ca1.metric("Selected carry daily gain", format_millions(carry_daily))
    ca2.metric("Selected carry daily share", f"{carry_share_daily:.1%}")
    ca3.metric("Selected carry 7-day pace", f"{format_millions(carry_avg)}/day")
    ca4.metric("Selected carry 7-day share", f"{carry_share_avg:.1%}")

else:
    st.info("Select a 7-day avg column to enable carry analysis.")


# -----------------------------
# Alt phase-out test
# -----------------------------

st.divider()
st.subheader("Alt Phase-out Test")

if avg_num_col:
    phaseout_members = st.multiselect(
        "Remove these accounts from pace simulation",
        options=active_data[name_col].dropna().unique().tolist(),
        default=[
            x for x in active_data[name_col].dropna().unique().tolist()
            if x == "Soudesune"
        ]
    )

    removed_pace = active_data.loc[
        active_data[name_col].isin(phaseout_members),
        avg_num_col
    ].sum()

    adjusted_pace = avg_total - removed_pace
    adjusted_surplus = adjusted_pace - breakpoint

    p1, p2, p3 = st.columns(3)
    p1.metric("Removed 7-day pace", f"{format_millions(removed_pace)}/day")
    p2.metric("Adjusted club pace", f"{format_millions(adjusted_pace)}/day")
    p3.metric("Adjusted surplus vs breakpoint", f"{format_millions(adjusted_surplus)}/day")

else:
    st.info("Select a 7-day avg column to enable the phase-out test.")


# -----------------------------
# Replacement simulator
# -----------------------------

st.divider()
st.subheader("Replacement Simulator")

if avg_num_col:
    r1, r2 = st.columns(2)

    with r1:
        replace_member = st.selectbox(
            "Member to replace",
            [None] + active_data[name_col].dropna().unique().tolist()
        )

    with r2:
        replacement_avg_m = st.number_input(
            "Replacement expected 7-day avg, M/day",
            min_value=0.0,
            value=0.5,
            step=0.1
        )

    if replace_member is not None:
        current_member_avg = active_data.loc[
            active_data[name_col] == replace_member,
            avg_num_col
        ].sum()

        replacement_avg = replacement_avg_m * 1_000_000
        net_change = replacement_avg - current_member_avg
        new_pace = avg_total + net_change
        new_surplus = new_pace - breakpoint

        r3, r4, r5, r6 = st.columns(4)
        r3.metric("Current member pace", f"{format_millions(current_member_avg)}/day")
        r4.metric("Replacement pace", f"{format_millions(replacement_avg)}/day")
        r5.metric("Net change", f"{format_millions(net_change)}/day")
        r6.metric("New club surplus", f"{format_millions(new_surplus)}/day")

else:
    st.info("Select a 7-day avg column to enable replacement simulation.")


# -----------------------------
# Watchlist
# -----------------------------

st.divider()
st.subheader("Watchlist")

watch = active_data[[name_col]].copy()

if daily_num_col:
    watch["daily_gain"] = active_data[daily_num_col]

if avg_num_col:
    watch["avg_7d"] = active_data[avg_num_col]

if monthly_num_col:
    watch["monthly_gain"] = active_data[monthly_num_col]
    watch["on_pace_10m"] = watch["monthly_gain"] >= 10_000_000

watch["status"] = watch.apply(classify_member, axis=1)

status_order = {
    "Replace / inactive risk": 0,
    "High watch": 1,
    "Watch": 2,
    "Low monthly": 3,
    "Below 10M benchmark": 4,
    "OK": 5
}

watch["status_order"] = watch["status"].map(status_order).fillna(99)

sort_cols = ["status_order"]
ascending = [True]

if "avg_7d" in watch.columns:
    sort_cols.append("avg_7d")
    ascending.append(True)

watch = watch.sort_values(sort_cols, ascending=ascending)
watch_display = watch.drop(columns=["status_order"])

st.dataframe(
    watch_display,
    use_container_width=True,
    hide_index=True
)


# -----------------------------
# Member contribution table
# -----------------------------

st.divider()
st.subheader("Member Table")

member_cols = [name_col]

for raw_col, num_col in [
    (daily_col, daily_num_col),
    (avg_col, avg_num_col),
    (monthly_col, monthly_num_col),
]:
    if raw_col is not None and num_col is not None:
        member_cols.append(raw_col)
        member_cols.append(num_col)

member_table = active_data[member_cols].copy()

if avg_num_col:
    member_table = member_table.sort_values(avg_num_col, ascending=False)
elif monthly_num_col:
    member_table = member_table.sort_values(monthly_num_col, ascending=False)

st.dataframe(
    member_table,
    use_container_width=True,
    hide_index=True
)


# -----------------------------
# Charts
# -----------------------------

st.divider()
st.subheader("Charts")

if avg_num_col:
    chart_df = active_data[[name_col, avg_num_col]].copy()
    chart_df = chart_df.sort_values(avg_num_col, ascending=False)

    fig = px.bar(
        chart_df,
        x=name_col,
        y=avg_num_col,
        title="7-day average by active member"
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

if daily_num_col:
    daily_chart_df = active_data[[name_col, daily_num_col]].copy()
    daily_chart_df = daily_chart_df.sort_values(daily_num_col, ascending=False)

    fig2 = px.bar(
        daily_chart_df,
        x=name_col,
        y=daily_num_col,
        title="Daily gain by active member"
    )
    fig2.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig2, use_container_width=True)
